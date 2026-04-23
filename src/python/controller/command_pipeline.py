# Copyright 2017, Inderpreet Singh, All rights reserved.

"""Command pipeline: queuing, dispatching, and lifecycle management.

Owns the command queue, active command/move processes, and related state.
Extracted from controller.py as part of the controller decomposition
(#394 Phase 2E).
"""

from __future__ import annotations

import logging
import os
from collections.abc import Callable
from queue import Queue
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .controller import Controller

from common import AppError, Context, MultiprocessingLogger
from lftp import LftpError
from model import ModelError, ModelFile

from .controller_persist import ControllerPersist
from .delete import DeleteLocalProcess, DeleteRemoteProcess
from .exclude_patterns import parse_exclude_patterns
from .extract import ExtractProcess, ExtractRequest
from .model_registry import ModelRegistry
from .move import MoveProcess
from .pair_context import PairContext
from .persist_keys import persist_key
from .validate import ValidateProcess, ValidateRequest


class CommandPipeline:
    """Owns the command queue and active command/move process lifecycle.

    All methods preserve the exact logic from their original Controller
    counterparts — this is a structural extraction, not a refactor.
    """

    def __init__(
        self,
        pair_contexts: list[PairContext],
        registry: ModelRegistry,
        persist: ControllerPersist,
        context: Context,
        password: str | None,
        mp_logger: MultiprocessingLogger,
        extract_process: ExtractProcess,
        validate_process: ValidateProcess,
        logger: logging.Logger,
        sync_persist_callback: Callable[[], None],
    ):
        self._pair_contexts = pair_contexts
        self._registry = registry
        self._persist = persist
        self._context = context
        self._password = password
        self._mp_logger = mp_logger
        self._extract_process = extract_process
        self._validate_process = validate_process
        self._logger = logger
        self._sync_persist_callback = sync_persist_callback

        # The command queue
        self.command_queue: Queue[Controller.Command] = Queue()

        # Keep track of active command processes (shared)
        self.active_command_processes: list[Controller.CommandProcessWrapper] = []

        # Keep track of active move processes (staging -> final, shared)
        self.active_move_processes: list[MoveProcess] = []
        # Use composite keys (pair_id:name) to avoid collisions across pairs
        self.moved_file_keys: set[str] = set()

        # Track files with pending validation so extraction-completion doesn't race the move
        self.pending_validation_keys: set[str] = set()

    def queue(self, command: Controller.Command) -> None:
        """Put a command on the queue for processing."""
        self.command_queue.put(command)

    def step(self):  # noqa: C901
        """Process commands from queue.

        References Controller.Command, Controller.Command.Action,
        Controller._MAX_CONCURRENT_COMMAND_PROCESSES, and
        Controller.CommandProcessWrapper which remain in Controller.
        """
        from .controller import Controller

        def _notify_failure(_command: Controller.Command, _msg: str):
            self._logger.warning(f"Command failed. {_msg}")
            for _callback in _command.callbacks:
                _callback.on_failure(_msg)

        deferred: list[Controller.Command] = []

        while not self.command_queue.empty():
            command = self.command_queue.get()
            self._logger.info(f"Received command {command.action!s} for file {command.filename}")

            pc = self._get_pair_context_for_command(command)
            if pc is None:
                _notify_failure(command, f"No pair context found for pair_id '{command.pair_id}'")
                continue

            try:
                file = self._registry.get_file(command.filename, pair_id=pc.pair_id)
            except ModelError:
                _notify_failure(command, f"File '{command.filename}' not found")
                continue

            if command.action == Controller.Command.Action.QUEUE:
                if file.remote_size is None:
                    _notify_failure(command, f"File '{command.filename}' does not exist remotely")
                    continue
                try:
                    exclude = parse_exclude_patterns(self._context.config.general.exclude_patterns)
                    pc.lftp.queue(file.name, file.is_dir, exclude_patterns=exclude)
                except LftpError as e:
                    _notify_failure(command, f"Lftp error: {e!s}")
                    continue

            elif command.action == Controller.Command.Action.STOP:
                if file.state not in (ModelFile.State.DOWNLOADING, ModelFile.State.QUEUED):
                    _notify_failure(command, f"File '{command.filename}' is not Queued or Downloading")
                    continue
                try:
                    pc.lftp.kill(file.name)
                except LftpError as e:
                    _notify_failure(command, f"Lftp error: {e!s}")
                    continue

            elif command.action == Controller.Command.Action.EXTRACT:
                if file.state not in (
                    ModelFile.State.DEFAULT,
                    ModelFile.State.DOWNLOADED,
                    ModelFile.State.EXTRACTED,
                    ModelFile.State.EXTRACT_FAILED,
                    ModelFile.State.VALIDATED,
                    ModelFile.State.CORRUPT,
                ):
                    _notify_failure(command, f"File '{command.filename}' in state {file.state!s} cannot be extracted")
                    continue
                if file.local_size is None:
                    _notify_failure(command, f"File '{command.filename}' does not exist locally")
                    continue
                pkey = persist_key(pc.pair_id, file.name)
                self._persist.extract_failed_file_names.discard(pkey)
                self._sync_persist_callback()
                req = self._build_extract_request(file, pc)
                self._extract_process.extract(req)

            elif command.action == Controller.Command.Action.DELETE_LOCAL:
                if len(self.active_command_processes) >= Controller._MAX_CONCURRENT_COMMAND_PROCESSES:
                    self._logger.debug(
                        "Deferring %s for '%s': %d active processes at cap",
                        command.action,
                        command.filename,
                        len(self.active_command_processes),
                    )
                    deferred.append(command)
                    continue
                if file.state not in (
                    ModelFile.State.DEFAULT,
                    ModelFile.State.DOWNLOADED,
                    ModelFile.State.EXTRACTED,
                    ModelFile.State.EXTRACT_FAILED,
                    ModelFile.State.VALIDATED,
                    ModelFile.State.CORRUPT,
                ):
                    _notify_failure(
                        command,
                        f"Local file '{command.filename}' cannot be deleted in state {file.state!s}",
                    )
                    continue
                if file.local_size is None:
                    _notify_failure(command, f"File '{command.filename}' does not exist locally")
                    continue
                delete_path = pc.local_path
                pair_staging = self._pair_staging_dir(pc)
                if pair_staging:
                    staging_file = os.path.join(pair_staging, file.name)
                    if os.path.exists(staging_file):
                        delete_path = pair_staging
                process = DeleteLocalProcess(local_path=delete_path, file_name=file.name)
                process.set_mp_log_queue(self._mp_logger.queue, self._mp_logger.log_level)

                def post_callback(delete_path: str = delete_path, _pc: PairContext = pc) -> None:
                    _pc.local_scan_process.force_scan()
                    if delete_path != _pc.local_path:
                        _pc.active_scan_process.force_scan()

                command_wrapper = Controller.CommandProcessWrapper(process=process, post_callback=post_callback)
                self.active_command_processes.append(command_wrapper)
                command_wrapper.process.start()

            elif command.action == Controller.Command.Action.DELETE_REMOTE:
                if len(self.active_command_processes) >= Controller._MAX_CONCURRENT_COMMAND_PROCESSES:
                    self._logger.debug(
                        "Deferring %s for '%s': %d active processes at cap",
                        command.action,
                        command.filename,
                        len(self.active_command_processes),
                    )
                    deferred.append(command)
                    continue
                if file.state not in (
                    ModelFile.State.DEFAULT,
                    ModelFile.State.DOWNLOADED,
                    ModelFile.State.EXTRACTED,
                    ModelFile.State.EXTRACT_FAILED,
                    ModelFile.State.VALIDATED,
                    ModelFile.State.CORRUPT,
                    ModelFile.State.DELETED,
                ):
                    _notify_failure(
                        command,
                        f"Remote file '{command.filename}' cannot be deleted in state {file.state!s}",
                    )
                    continue
                if file.remote_size is None:
                    _notify_failure(command, f"File '{command.filename}' does not exist remotely")
                    continue
                process = DeleteRemoteProcess(
                    remote_address=self._context.config.lftp.remote_address,  # type: ignore[arg-type]
                    remote_username=self._context.config.lftp.remote_username,  # type: ignore[arg-type]
                    remote_password=self._password,
                    remote_port=self._context.config.lftp.remote_port,  # type: ignore[arg-type]
                    remote_path=pc.remote_path,
                    file_name=file.name,
                )
                process.set_mp_log_queue(self._mp_logger.queue, self._mp_logger.log_level)
                command_wrapper = Controller.CommandProcessWrapper(
                    process=process, post_callback=pc.remote_scan_process.force_scan
                )
                self.active_command_processes.append(command_wrapper)
                command_wrapper.process.start()

            elif command.action == Controller.Command.Action.VALIDATE:
                if not self._context.config.validate.enabled:
                    _notify_failure(command, "Validation is not enabled in config")
                    continue
                if file.state not in (
                    ModelFile.State.DOWNLOADED,
                    ModelFile.State.EXTRACTED,
                    ModelFile.State.EXTRACT_FAILED,
                    ModelFile.State.VALIDATED,
                    ModelFile.State.CORRUPT,
                ):
                    _notify_failure(command, f"File '{command.filename}' in state {file.state!s} cannot be validated")
                    continue
                if file.local_size is None:
                    _notify_failure(command, f"File '{command.filename}' does not exist locally")
                    continue
                if file.remote_size is None:
                    _notify_failure(command, f"File '{command.filename}' does not exist remotely")
                    continue
                pkey = persist_key(pc.pair_id, file.name)
                self._persist.validated_file_names.discard(pkey)
                self._persist.corrupt_file_names.discard(pkey)
                self._sync_persist_callback()
                req = ValidateRequest(
                    name=file.name,
                    is_dir=file.is_dir,
                    pair_id=pc.pair_id,
                    local_path=pc.effective_local_path,
                    remote_path=pc.remote_path,
                    algorithm=self._context.config.validate.algorithm,  # type: ignore[arg-type]
                    remote_address=self._context.config.lftp.remote_address,  # type: ignore[arg-type]
                    remote_username=self._context.config.lftp.remote_username,  # type: ignore[arg-type]
                    remote_password=self._password,
                    remote_port=self._context.config.lftp.remote_port,  # type: ignore[arg-type]
                )
                self._validate_process.validate(req)
                self.pending_validation_keys.add(pkey)

            for callback in command.callbacks:
                callback.on_success()

        for cmd in deferred:
            self.command_queue.put(cmd)

    def cleanup(self):
        """
        Cleanup the list of active commands and do any callbacks
        :return:
        """
        from .controller import Controller  # noqa: F401 — used in type annotation below

        still_active_processes: list[Controller.CommandProcessWrapper] = []
        for command_process in self.active_command_processes:
            if command_process.process.is_alive():
                still_active_processes.append(command_process)
            else:
                command_process.post_callback()
                try:
                    command_process.process.propagate_exception()
                except Exception:
                    self._logger.warning("Command process failed: %s", command_process.process.name, exc_info=True)
        self.active_command_processes = still_active_processes

        still_active_moves: list[MoveProcess] = []
        for move_process in self.active_move_processes:
            if move_process.is_alive():
                still_active_moves.append(move_process)
            else:
                try:
                    move_process.propagate_exception()
                except Exception:
                    self._logger.warning("Move process failed: %s", move_process.name, exc_info=True)
                    move_key = persist_key(move_process.pair_id, move_process.file_name)
                    self.moved_file_keys.discard(move_key)
                for pc in self._pair_contexts:
                    pc.local_scan_process.force_scan()
        self.active_move_processes = still_active_moves

    def propagate_exceptions(self):
        """
        Propagate any exceptions from child processes/threads to this thread
        :return:
        """
        for pc in self._pair_contexts:
            try:
                pc.lftp.raise_pending_error()
            except LftpError as e:
                error_str = str(e)
                permanent_patterns = ["Login failed", "Access failed"]
                if any(p in error_str for p in permanent_patterns):
                    raise AppError(error_str) from e
                self._logger.warning(f"Caught lftp error: {error_str}")
            pc.active_scan_process.propagate_exception()
            pc.local_scan_process.propagate_exception()
            pc.remote_scan_process.propagate_exception()
        self._mp_logger.propagate_exception()
        self._extract_process.propagate_exception()
        self._validate_process.propagate_exception()

    def spawn_deferred_move(self, pair_id: str | None, file_name: str):
        """Spawn the staging->final move for a file whose validation just finished.

        Only acts when staging is enabled; looks up the owning pair context by pair_id.
        """
        pc = self._find_pair_by_id(pair_id)
        if pc is None:
            self._logger.warning(f"Cannot spawn deferred move for '{file_name}': pair '{pair_id}' not found")
            return
        self._spawn_move_process(file_name, pc)

    def _spawn_move_process(self, file_name: str, pc: PairContext):
        """
        Spawn a MoveProcess to move a file from staging to the final local_path
        """
        pair_id = pc.pair_id
        move_key = persist_key(pair_id, file_name)
        if move_key in self.moved_file_keys:
            self._logger.debug(f"Skipping move for {file_name} - already moved")
            return

        dest_path = pc.local_path
        staging_source = self._pair_staging_dir(pc)
        if staging_source is None:
            self._logger.warning(f"Skipping move for {file_name} - staging is not enabled")
            return

        # Skip if the file doesn't exist in staging (e.g. already moved in a prior session)
        staging_file = os.path.join(staging_source, file_name)
        if not os.path.exists(staging_file):
            self._logger.debug(f"Skipping move for {file_name} - not found in staging")
            self.moved_file_keys.add(move_key)
            return

        self.moved_file_keys.add(move_key)
        process = MoveProcess(source_path=staging_source, dest_path=dest_path, file_name=file_name, pair_id=pair_id)
        process.set_mp_log_queue(self._mp_logger.queue, self._mp_logger.log_level)
        self.active_move_processes.append(process)
        process.start()
        self._logger.info(f"Spawned move process for {file_name} (staging -> local)")

    def _get_pair_context_for_command(self, command: Controller.Command) -> PairContext | None:
        """Find the pair context for a command based on pair_id."""
        return self._find_pair_by_id(command.pair_id)

    def _get_pair_context_for_file(self, file: ModelFile) -> PairContext | None:
        """Find the pair context that owns a ModelFile based on its pair_id."""
        for pc in self._pair_contexts:
            if pc.pair_id == file.pair_id:
                return pc
        return None

    def _find_pair_by_id(self, pair_id: str | None) -> PairContext | None:
        """Find the pair context by pair_id.
        Returns default (first) pair when pair_id is None.
        Returns None when pair_id is provided but not found.
        """
        if pair_id:
            for pc in self._pair_contexts:
                if pc.pair_id == pair_id:
                    return pc
            return None
        return self._pair_contexts[0] if self._pair_contexts else None

    def _pair_staging_dir(self, pc: PairContext) -> str | None:
        """Return the per-pair staging directory, or None if staging is disabled."""
        cfg = self._context.config.controller
        if not (cfg.use_staging and cfg.staging_path):
            return None
        return os.path.join(cfg.staging_path, pc.pair_id) if pc.pair_id else cfg.staging_path  # type: ignore[arg-type]

    def _build_extract_request(self, file: ModelFile, pc: PairContext) -> ExtractRequest:
        """Build an ExtractRequest with the correct pair-specific paths."""
        # Determine output directory
        if self._context.config.controller.use_local_path_as_extract_path:
            extract_out_dir = pc.local_path
        else:
            extract_out_dir = self._context.config.controller.extract_path  # type: ignore[assignment]

        # When staging is enabled, archives live in the staging subdir
        pair_staging = self._pair_staging_dir(pc)
        if pair_staging:
            out_dir_path = pair_staging
            out_dir_path_fallback = extract_out_dir
        else:
            out_dir_path = extract_out_dir
            out_dir_path_fallback = None

        local_path_fallback = None
        if pc.effective_local_path != pc.local_path:
            local_path_fallback = pc.local_path

        return ExtractRequest(
            model_file=file,
            local_path=pc.effective_local_path,
            out_dir_path=out_dir_path,  # type: ignore[arg-type]
            pair_id=pc.pair_id,
            local_path_fallback=local_path_fallback,
            out_dir_path_fallback=out_dir_path_fallback,
        )
