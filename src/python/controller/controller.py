# Copyright 2017, Inderpreet Singh, All rights reserved.

from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod
from collections.abc import Callable
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

from common import AppOneShotProcess, Constants, Context, MultiprocessingLogger
from lftp import Lftp, LftpError, LftpJobStatus
from model import IModelListener, Model, ModelDiff, ModelError, ModelFile

from .command_pipeline import CommandPipeline
from .controller_persist import ControllerPersist

# my libs
from .exclude_patterns import filter_excluded_files
from .extract import ExtractProcess, ExtractStatus, ExtractStatusResult
from .model_builder import ModelBuilder
from .model_registry import ModelRegistry
from .pair_context import ControllerError, PairContext, configure_lftp, validate_config
from .persist_keys import KEY_SEP, persist_key, strip_persist_key
from .scan import ActiveScanner, LocalScanner, RemoteScanner, ScannerProcess
from .validate import ValidateProcess, ValidateRequest, ValidateStatusResult


class Controller:
    """
    Top-level class that controls the behaviour of the app
    """

    class Command:
        """
        Class by which clients of Controller can request Actions to be executed
        Supports callbacks by which clients can be notified of action success/failure
        Note: callbacks will be executed in Controller thread, so any heavy computation
              should be moved out of the callback
        """

        class Action(Enum):
            QUEUE = 0
            STOP = 1
            EXTRACT = 2
            DELETE_LOCAL = 3
            DELETE_REMOTE = 4
            VALIDATE = 5

        class ICallback(ABC):
            """Command callback interface"""

            @abstractmethod
            def on_success(self):
                """Called on successful completion of action"""
                pass

            @abstractmethod
            def on_failure(self, error: str):
                """Called on action failure"""
                pass

        def __init__(self, action: Action, filename: str, pair_id: str | None = None):
            self.action = action
            self.filename = filename
            self.pair_id = pair_id
            self.callbacks: list[Controller.Command.ICallback] = []

        def add_callback(self, callback: ICallback):
            self.callbacks.append(callback)

    class CommandProcessWrapper:
        """
        Wraps any one-shot command processes launched by the controller
        """

        def __init__(self, process: AppOneShotProcess, post_callback: Callable[[], None]):
            self.process = process
            self.post_callback = post_callback

    MAX_CONCURRENT_COMMAND_PROCESSES = 8

    def __init__(self, context: Context, persist: ControllerPersist):
        self.__context = context
        self.__persist = persist
        self.logger = context.logger.getChild("Controller")

        # Decide the password here
        self.__password = context.config.lftp.remote_password if not context.config.lftp.use_ssh_key else None

        # Validate required config fields before building anything
        self._validate_config()

        # The model registry (shared across all pairs, thread-safe)
        _model = Model()
        _model.set_base_logger(self.logger)
        self.__registry = ModelRegistry(_model)

        # Setup multiprocess logging (shared)
        self.__mp_logger = MultiprocessingLogger(self.logger)

        # Build pair contexts, then seed each builder with filtered persist state
        self.__pair_contexts: list[PairContext] = self._build_pair_contexts()
        self._sync_persist_to_all_builders()

        # Setup extract process (global -- extraction is local-only)
        self.__extract_process = ExtractProcess()
        self.__extract_process.set_mp_log_queue(self.__mp_logger.queue, self.__mp_logger.log_level)

        # Setup validate process (global -- validation uses SSH to remote)
        self.__validate_process = ValidateProcess()
        self.__validate_process.set_mp_log_queue(self.__mp_logger.queue, self.__mp_logger.log_level)

        # Command pipeline owns the queue, active processes, and move state
        self.__pipeline = CommandPipeline(
            pair_contexts=self.__pair_contexts,
            registry=self.__registry,
            persist=self.__persist,
            context=self.__context,
            password=self.__password,
            mp_logger=self.__mp_logger,
            extract_process=self.__extract_process,
            validate_process=self.__validate_process,
            logger=self.logger,
            sync_persist_callback=self._sync_persist_to_all_builders,
        )

        self.__started = False

    def _validate_config(self) -> None:
        validate_config(self.__context)

    def _build_pair_contexts(self) -> list[PairContext]:
        """
        Build a PairContext for each configured path pair.
        If no path pairs are configured, create a single default pair from config.lftp
        for backward compatibility.
        """
        pairs = self.__context.path_pairs_config.pairs
        enabled_pairs = [p for p in pairs if p.enabled]

        if not enabled_pairs:
            if pairs:
                # All configured pairs are disabled — signal idle state
                self.__context.status.controller.no_enabled_pairs = True
                self.logger.warning("All path pairs are disabled. Enable a pair in Settings to start syncing.")
                return []
            # Backward compatibility: no path pairs configured, use config.lftp
            remote_path = self.__context.config.lftp.remote_path
            local_path = self.__context.config.lftp.local_path
            if remote_path is None or local_path is None:
                missing = [
                    name
                    for name, val in [("Lftp.remote_path", remote_path), ("Lftp.local_path", local_path)]
                    if val is None
                ]
                fields = ", ".join(missing)
                raise ControllerError(
                    f"No path pairs configured and {fields} not set. "
                    f"Configure at least one path pair in Settings, or set {fields}."
                )
            return [
                self._create_pair_context(
                    pair_id=None,
                    name="Default",
                    remote_path=remote_path,
                    local_path=local_path,
                )
            ]

        self.__context.status.controller.no_enabled_pairs = False
        contexts: list[PairContext] = []
        for pair in enabled_pairs:
            contexts.append(
                self._create_pair_context(
                    pair_id=pair.id, name=pair.name, remote_path=pair.remote_path, local_path=pair.local_path
                )
            )
        return contexts

    def _create_pair_context(self, pair_id: str | None, name: str, remote_path: str, local_path: str) -> PairContext:
        """
        Create a fully wired PairContext with its own LFTP, scanners, and model builder.
        """
        pair_label = name or pair_id or "default"
        pair_logger = self.logger.getChild(f"Pair[{pair_label}]")

        # Determine effective local path: use staging_path when staging is enabled
        # Each pair gets its own staging subdirectory to prevent cross-pair collisions
        if self.__context.config.controller.use_staging and self.__context.config.controller.staging_path:
            if pair_id:
                effective_local_path = os.path.join(self.__context.config.controller.staging_path, pair_id)  # type: ignore[arg-type]
            else:
                effective_local_path = self.__context.config.controller.staging_path  # type: ignore[arg-type]
            os.makedirs(effective_local_path, exist_ok=True)
        else:
            effective_local_path = local_path

        # LFTP instance
        lftp = Lftp(
            address=self.__context.config.lftp.remote_address,  # type: ignore[arg-type]
            port=self.__context.config.lftp.remote_port,  # type: ignore[arg-type]
            user=self.__context.config.lftp.remote_username,  # type: ignore[arg-type]
            password=self.__password,
        )
        lftp.set_base_logger(pair_logger)
        lftp.set_base_remote_dir_path(remote_path)
        lftp.set_base_local_dir_path(effective_local_path)
        self._configure_lftp(lftp)

        # Scanners
        active_scanner = ActiveScanner(
            effective_local_path,
            lftp_temp_suffix=Constants.LFTP_TEMP_FILE_SUFFIX if self.__context.config.lftp.use_temp_file else None,
        )
        local_scanner = LocalScanner(local_path=local_path, use_temp_file=self.__context.config.lftp.use_temp_file)  # type: ignore[arg-type]
        remote_scanner = RemoteScanner(
            remote_address=self.__context.config.lftp.remote_address,  # type: ignore[arg-type]
            remote_username=self.__context.config.lftp.remote_username,  # type: ignore[arg-type]
            remote_password=self.__password,
            remote_port=self.__context.config.lftp.remote_port,  # type: ignore[arg-type]
            remote_path_to_scan=remote_path,
            local_path_to_scan_script=self.__context.args.local_path_to_scanfs,  # type: ignore[arg-type]
            remote_path_to_scan_script=self.__context.config.lftp.remote_path_to_scan_script,  # type: ignore[arg-type]
            remote_python_path=self.__context.config.lftp.remote_python_path,  # type: ignore[arg-type]
        )

        # Scanner processes
        active_scan_process = ScannerProcess(
            scanner=active_scanner,
            interval_in_ms=self.__context.config.controller.interval_ms_downloading_scan,  # type: ignore[arg-type]
            verbose=False,
        )
        local_scan_process = ScannerProcess(
            scanner=local_scanner,
            interval_in_ms=self.__context.config.controller.interval_ms_local_scan,  # type: ignore[arg-type]
        )
        remote_scan_process = ScannerProcess(
            scanner=remote_scanner,
            interval_in_ms=self.__context.config.controller.interval_ms_remote_scan,  # type: ignore[arg-type]
        )

        # Wire multiprocess logging
        active_scan_process.set_mp_log_queue(self.__mp_logger.queue, self.__mp_logger.log_level)
        local_scan_process.set_mp_log_queue(self.__mp_logger.queue, self.__mp_logger.log_level)
        remote_scan_process.set_mp_log_queue(self.__mp_logger.queue, self.__mp_logger.log_level)

        # Model builder
        model_builder = ModelBuilder(pair_id=pair_id)
        model_builder.set_base_logger(pair_logger)
        # Persist state is filtered per-pair by _sync_persist_to_all_builders()
        # called after all pair contexts are built. Initialize with empty sets.
        model_builder.set_downloaded_files(set())
        model_builder.set_extracted_files(set())
        model_builder.set_extract_failed_files(set())
        model_builder.set_validated_files(set())
        model_builder.set_corrupt_files(set())
        model_builder.set_auto_delete_remote(bool(self.__context.config.autoqueue.auto_delete_remote))  # type: ignore[arg-type]

        return PairContext(
            pair_id=pair_id,
            name=name,
            remote_path=remote_path,
            local_path=local_path,
            effective_local_path=effective_local_path,
            lftp=lftp,
            active_scanner=active_scanner,
            local_scanner=local_scanner,
            remote_scanner=remote_scanner,
            active_scan_process=active_scan_process,
            local_scan_process=local_scan_process,
            remote_scan_process=remote_scan_process,
            model_builder=model_builder,
        )

    def _configure_lftp(self, lftp: Lftp):
        configure_lftp(lftp, self.__context.config)
        lftp.set_verbose_logging(self.__context.config.general.verbose)  # type: ignore[arg-type]

    def start(self):
        """
        Start the controller
        Must be called after ctor and before process()
        :return:
        """
        self.logger.debug("Starting controller")
        for pc in self.__pair_contexts:
            pc.active_scan_process.start()
            pc.local_scan_process.start()
            pc.remote_scan_process.start()
        self.__extract_process.start()
        self.__validate_process.start()
        self.__mp_logger.start()
        self.__started = True

    def process(self):
        """
        Advance the controller state
        This method should return relatively quickly as the heavy lifting is done by concurrent tasks
        :return:
        """
        if not self.__started:
            raise ControllerError("Cannot process, controller is not started")
        self.__pipeline.propagate_exceptions()
        self.__pipeline.cleanup()
        self.__pipeline.step()
        self.__update_model()

    def exit(self):
        self.logger.debug("Exiting controller")
        if self.__started:
            for pc in self.__pair_contexts:
                pc.lftp.exit()
                pc.active_scan_process.terminate()
                pc.local_scan_process.terminate()
                pc.remote_scan_process.terminate()
            self.__extract_process.terminate()
            self.__validate_process.terminate()
            for cp in self.__pipeline.active_command_processes:
                cp.process.terminate()
            for mp in self.__pipeline.active_move_processes:
                mp.terminate()
            for pc in self.__pair_contexts:
                pc.active_scan_process.join()
                pc.local_scan_process.join()
                pc.remote_scan_process.join()
            self.__extract_process.join()
            self.__validate_process.join()
            for cp in self.__pipeline.active_command_processes:
                cp.process.join()
            for mp in self.__pipeline.active_move_processes:
                mp.join()
            self.__mp_logger.stop()

            # Close multiprocessing queues to release file descriptors.
            # Without this, each restart cycle leaks FDs until the OS limit
            # is exhausted (OSError: [Errno 24] No file descriptors available).
            for pc in self.__pair_contexts:
                pc.active_scan_process.close_queues()
                pc.local_scan_process.close_queues()
                pc.remote_scan_process.close_queues()
                pc.active_scanner.close()
            self.__extract_process.close_queues()
            self.__validate_process.close_queues()
            for cp in self.__pipeline.active_command_processes:
                cp.process.close_queues()
            for mp in self.__pipeline.active_move_processes:
                mp.close_queues()
            self.__pipeline.active_command_processes.clear()
            self.__pipeline.active_move_processes.clear()

            self.__started = False
            self.logger.info("Exited controller")

    def get_model_files(self) -> list[ModelFile]:
        return self.__registry.get_files()

    def add_model_listener(self, listener: IModelListener):
        self.__registry.add_listener(listener)

    def remove_model_listener(self, listener: IModelListener):
        self.__registry.remove_listener(listener)

    def get_model_files_and_add_listener(self, listener: IModelListener):
        return self.__registry.get_files_and_add_listener(listener)

    def queue_command(self, command: Command):
        self.__pipeline.queue(command)

    def __update_model(self):  # noqa: C901 — will be decomposed in #394
        # Grab the latest extract results (shared)
        latest_extract_statuses = self.__extract_process.pop_latest_statuses()
        latest_extracted_results = self.__extract_process.pop_completed()
        latest_failed_extractions = self.__extract_process.pop_failed()

        # Grab the latest validate results (shared)
        latest_validate_statuses = self.__validate_process.pop_latest_statuses()
        latest_validated_results = self.__validate_process.pop_completed()
        latest_failed_validations = self.__validate_process.pop_failed()

        # Process each pair context's scan results and LFTP status
        for pc in self.__pair_contexts:
            self._update_pair_model_state(pc, latest_extract_statuses, latest_validate_statuses)

        # Process extraction completions once (shared across all pairs)
        if latest_extracted_results:
            for result in latest_extracted_results:
                owner_pc = self.__pipeline.find_pair_by_id(result.pair_id)
                if owner_pc is None:
                    self.logger.warning(
                        f"Ignoring extract completion for '{result.name}': pair '{result.pair_id}' no longer exists"
                    )
                    continue
                pkey = persist_key(result.pair_id, result.name)
                self.__persist.extracted_file_names.add(pkey)
                if self.__context.config.controller.use_staging and self.__context.config.controller.staging_path:
                    if pkey not in self.__pipeline.pending_validation_keys:
                        self.__pipeline.spawn_move_process(result.name, owner_pc)
            self._sync_persist_to_all_builders()

        # Build an aggregate new model from all pairs
        any_pair_has_changes = any(pc.model_builder.has_changes() for pc in self.__pair_contexts)

        if any_pair_has_changes:
            new_model = Model()
            _dummy = logging.getLogger("dummy")
            _dummy.propagate = False
            new_model.set_base_logger(_dummy)  # silence logs for temp model

            # When multiple pairs share the same local directory, a file that
            # exists only locally (no remote counterpart) would appear in every
            # pair's model.  Deduplicate by scoping per normalized local path:
            #   1) adding all "managed" files first (have a remote, or non-DEFAULT state),
            #   2) then adding local-only files only if no other pair with the
            #      same local directory already claims a file with that name.
            seen_names_by_path: dict[str, set[str]] = {}
            deferred_local_only: list[tuple[ModelFile, str]] = []
            for pc in self.__pair_contexts:
                norm_path = os.path.normpath(os.path.abspath(pc.local_path))
                if norm_path not in seen_names_by_path:
                    seen_names_by_path[norm_path] = set()
                pair_model = pc.model_builder.build_model()
                for file in pair_model.get_all_files():
                    is_local_only = file.remote_size is None and file.state == ModelFile.State.DEFAULT
                    if is_local_only:
                        deferred_local_only.append((file, norm_path))
                    else:
                        new_model.add_file(file)
                        seen_names_by_path[norm_path].add(file.name)

            for file, norm_path in deferred_local_only:
                if file.name not in seen_names_by_path[norm_path]:
                    new_model.add_file(file)
                    seen_names_by_path[norm_path].add(file.name)

            model_diff = self.__registry.apply_diff(new_model)

            for diff in model_diff:
                diff_file = diff.new_file or diff.old_file
                assert diff_file is not None
                pc = self.__pipeline.get_pair_context_for_file(diff_file)

                if diff.new_file is not None and diff.new_file.state in (
                    ModelFile.State.QUEUED,
                    ModelFile.State.DOWNLOADING,
                ):
                    pkey = persist_key(diff.new_file.pair_id, diff.new_file.name)
                    self.__pipeline.moved_file_keys.discard(pkey)
                    self.__persist.downloaded_file_names.discard(pkey)
                    self.__persist.extracted_file_names.discard(pkey)
                    self.__persist.extract_failed_file_names.discard(pkey)
                    self.__persist.validated_file_names.discard(pkey)
                    self.__persist.corrupt_file_names.discard(pkey)
                    self._sync_persist_to_all_builders()

                downloaded = False
                if (
                    diff.change == ModelDiff.Change.ADDED
                    and diff.new_file is not None
                    and diff.new_file.state == ModelFile.State.DOWNLOADED
                ) or (
                    diff.change == ModelDiff.Change.UPDATED
                    and diff.new_file is not None
                    and diff.new_file.state == ModelFile.State.DOWNLOADED
                    and diff.old_file is not None
                    and diff.old_file.state != ModelFile.State.DOWNLOADED
                ):
                    downloaded = True
                if downloaded:
                    assert diff.new_file is not None
                    assert pc is not None
                    pkey = persist_key(diff.new_file.pair_id, diff.new_file.name)
                    self.__persist.downloaded_file_names.add(pkey)
                    self._sync_persist_to_all_builders()

                    # Auto-validate if enabled
                    if (
                        self.__context.config.validate.enabled
                        and self.__context.config.validate.auto_validate
                        and diff.new_file.remote_size is not None
                    ):
                        req = ValidateRequest(
                            name=diff.new_file.name,
                            is_dir=diff.new_file.is_dir,
                            pair_id=pc.pair_id,
                            local_path=pc.effective_local_path,
                            remote_path=pc.remote_path,
                            algorithm=self.__context.config.validate.algorithm,  # type: ignore[arg-type]
                            remote_address=self.__context.config.lftp.remote_address,  # type: ignore[arg-type]
                            remote_username=self.__context.config.lftp.remote_username,  # type: ignore[arg-type]
                            remote_password=self.__password,
                            remote_port=self.__context.config.lftp.remote_port,  # type: ignore[arg-type]
                        )
                        self.__validate_process.validate(req)
                        self.__pipeline.pending_validation_keys.add(persist_key(pc.pair_id, diff.new_file.name))
                        self.logger.info(f"Auto-queued validation for '{diff.new_file.name}'")

                    if self.__context.config.controller.use_staging and self.__context.config.controller.staging_path:
                        will_auto_extract = (
                            self.__context.config.autoqueue.auto_extract and diff.new_file.is_extractable
                        )
                        will_auto_validate = (
                            self.__context.config.validate.enabled
                            and self.__context.config.validate.auto_validate
                            and diff.new_file.remote_size is not None
                        )
                        if not will_auto_extract and not will_auto_validate:
                            self.__pipeline.spawn_move_process(diff.new_file.name, pc)

                if diff.new_file is not None and pc is not None and diff.new_file.name in pc.pending_completion:
                    use_staging = (
                        self.__context.config.controller.use_staging and self.__context.config.controller.staging_path
                    )
                    # A file with no local presence and DEFAULT state means
                    # it was deleted locally (e.g. stopped download whose files
                    # were removed). Nothing left to track.
                    if diff.new_file.state == ModelFile.State.DEFAULT and diff.new_file.local_size is None:
                        pc.pending_completion.discard(diff.new_file.name)
                    elif use_staging:
                        move_key = persist_key(diff.new_file.pair_id, diff.new_file.name)
                        if move_key in self.__pipeline.moved_file_keys or diff.new_file.state in (
                            ModelFile.State.DELETED,
                            ModelFile.State.EXTRACTED,
                            ModelFile.State.EXTRACT_FAILED,
                            ModelFile.State.VALIDATED,
                            ModelFile.State.CORRUPT,
                        ):
                            pc.pending_completion.discard(diff.new_file.name)
                    else:
                        if diff.new_file.state in (
                            ModelFile.State.DOWNLOADED,
                            ModelFile.State.EXTRACTED,
                            ModelFile.State.EXTRACT_FAILED,
                            ModelFile.State.VALIDATED,
                            ModelFile.State.CORRUPT,
                            ModelFile.State.DELETED,
                        ):
                            pc.pending_completion.discard(diff.new_file.name)

        # Prune the extracted files list of any files that were deleted locally
        remove_extracted_keys: set[str] = set()
        for pkey in self.__persist.extracted_file_names:
            # Find the file in the model by checking each pair
            for _pc in self.__pair_contexts:
                bare_name = strip_persist_key(pkey, _pc.pair_id)
                if bare_name != pkey or _pc.pair_id is None:
                    try:
                        file = self.__registry.get_file(bare_name, pair_id=_pc.pair_id)
                        if file.state == ModelFile.State.DELETED:
                            remove_extracted_keys.add(pkey)
                    except ModelError:
                        pass
        if remove_extracted_keys:
            self.logger.info(f"Removing from extracted list: {remove_extracted_keys}")
            self.__persist.extracted_file_names.difference_update(remove_extracted_keys)
            self._sync_persist_to_all_builders()

        # Persist cleanup: remove entries for files absent from all sources
        all_scans_received = all(_pc.remote_scan_received and _pc.local_scan_received for _pc in self.__pair_contexts)
        if all_scans_received:
            # Build a set of all composite keys present in the model
            model_keys: set[str] = set()
            for f in self.__registry.get_all_files():
                model_keys.add(persist_key(f.pair_id, f.name))
            absent_keys: set[str] = set()
            for pkey in self.__persist.downloaded_file_names:
                if pkey not in model_keys and pkey not in self.__pipeline.moved_file_keys:
                    absent_keys.add(pkey)
            if absent_keys:
                self.logger.info(f"Persist cleanup (both absent): {absent_keys}")
                self.__persist.downloaded_file_names.difference_update(absent_keys)
                self.__persist.extracted_file_names.difference_update(absent_keys)
                self.__persist.extract_failed_file_names.difference_update(absent_keys)
                self.__persist.validated_file_names.difference_update(absent_keys)
                self.__persist.corrupt_file_names.difference_update(absent_keys)
                self._sync_persist_to_all_builders()

        # Process extraction failures — mark as failed immediately
        for result in latest_failed_extractions:
            self.logger.error(f"Extraction failed for '{result.name}'")
            fail_key = persist_key(result.pair_id, result.name)
            self.__persist.extract_failed_file_names.add(fail_key)
            self._sync_persist_to_all_builders()

        # Process validation completions — mark as validated
        for result in latest_validated_results:
            self.logger.info(f"Validation passed for '{result.name}'")
            pkey = persist_key(result.pair_id, result.name)
            self.__pipeline.pending_validation_keys.discard(pkey)
            self.__persist.validated_file_names.add(pkey)
            self.__persist.corrupt_file_names.discard(pkey)
            self._sync_persist_to_all_builders()
            # If staging is active, spawn the move process now that validation finished
            self.__pipeline.spawn_deferred_move(result.pair_id, result.name)

        # Process validation failures
        for result in latest_failed_validations:
            self.logger.error(f"Validation failed for '{result.name}': {result.error_message}")
            pkey = persist_key(result.pair_id, result.name)
            self.__pipeline.pending_validation_keys.discard(pkey)
            if result.is_checksum_mismatch:
                # Checksum mismatch — mark as corrupt
                self.__persist.corrupt_file_names.add(pkey)
                self.__persist.validated_file_names.discard(pkey)
                self._sync_persist_to_all_builders()
            else:
                # Non-mismatch failure (SSH error, etc.) — don't mark corrupt,
                # just log so the user can retry
                self.logger.warning(
                    f"Validation error for '{result.name}' (not marking corrupt): {result.error_message}"
                )
            # Spawn deferred move regardless of failure type — validation is done
            self.__pipeline.spawn_deferred_move(result.pair_id, result.name)

        # Update the controller status (use most recent across all pairs)
        for pc in self.__pair_contexts:
            if pc._latest_remote_scan is not None:  # type: ignore[reportPrivateUsage]
                current = self.__context.status.controller.latest_remote_scan_time
                if current is None or pc._latest_remote_scan.timestamp > current:  # type: ignore[reportPrivateUsage]
                    self.__context.status.controller.latest_remote_scan_time = pc._latest_remote_scan.timestamp  # type: ignore[reportPrivateUsage]
                    self.__context.status.controller.latest_remote_scan_failed = pc._latest_remote_scan.failed  # type: ignore[reportPrivateUsage]
                    self.__context.status.controller.latest_remote_scan_error = pc._latest_remote_scan.error_message  # type: ignore[reportPrivateUsage]
            if pc._latest_local_scan is not None:  # type: ignore[reportPrivateUsage]
                current = self.__context.status.controller.latest_local_scan_time
                if current is None or pc._latest_local_scan.timestamp > current:  # type: ignore[reportPrivateUsage]
                    self.__context.status.controller.latest_local_scan_time = pc._latest_local_scan.timestamp  # type: ignore[reportPrivateUsage]

    def _update_pair_model_state(  # noqa: C901 — will be decomposed in #394
        self,
        pc: PairContext,
        latest_extract_statuses: ExtractStatusResult | None,
        latest_validate_statuses: ValidateStatusResult | None,
    ) -> None:
        """
        Update a single pair context's scan results, LFTP status, and model builder state.
        """
        latest_remote_scan = pc.remote_scan_process.pop_latest_result()
        latest_local_scan = pc.local_scan_process.pop_latest_result()
        latest_active_scan = pc.active_scan_process.pop_latest_result()

        pc._latest_remote_scan = latest_remote_scan  # type: ignore[reportPrivateUsage]
        pc._latest_local_scan = latest_local_scan  # type: ignore[reportPrivateUsage]

        lftp_statuses = None
        try:
            lftp_statuses = pc.lftp.status()
        except LftpError as e:
            self.logger.warning(f"Caught lftp error (pair {pc.name}): {e!s}")

        if latest_remote_scan is not None:
            pc.remote_scan_received = True
        if latest_local_scan is not None:
            pc.local_scan_received = True

        if lftp_statuses is not None:
            current_downloading = {s.name for s in lftp_statuses if s.state == LftpJobStatus.State.RUNNING}
            just_completed = pc.prev_downloading_file_names - current_downloading
            if just_completed:
                for name in just_completed:
                    self.logger.info(f"Download completed (LFTP job finished): {name}")
                self.__persist.downloaded_file_names.update(persist_key(pc.pair_id, n) for n in just_completed)
                self._sync_persist_to_all_builders()
                pc.pending_completion.update(just_completed)
                pc.local_scan_process.force_scan()

            pc.active_downloading_file_names = list(current_downloading)
            pc.prev_downloading_file_names = current_downloading

        if latest_extract_statuses is not None:
            # Only include extract statuses for files that belong to this pair
            pc.active_extracting_file_names = [
                s.name
                for s in latest_extract_statuses.statuses
                if s.pair_id == pc.pair_id
                and s.state == ExtractStatus.State.EXTRACTING
                and persist_key(pc.pair_id, s.name) in self.__persist.downloaded_file_names
            ]

        active_files = pc.active_downloading_file_names + pc.active_extracting_file_names
        active_files += list(pc.pending_completion)
        pc.active_scanner.set_active_files(active_files)

        pc.model_builder.set_auto_delete_remote(bool(self.__context.config.autoqueue.auto_delete_remote))

        if latest_remote_scan is not None:
            remote_files = filter_excluded_files(
                latest_remote_scan.files, self.__context.config.general.exclude_patterns
            )
            pc.model_builder.set_remote_files(remote_files)
        if latest_local_scan is not None:
            pc.model_builder.set_local_files(latest_local_scan.files)
        if latest_active_scan is not None:
            pc.model_builder.set_active_files(latest_active_scan.files)
        if lftp_statuses is not None:
            pc.model_builder.set_lftp_statuses(lftp_statuses)
        if latest_extract_statuses is not None:
            pair_statuses = [s for s in latest_extract_statuses.statuses if s.pair_id == pc.pair_id]
            pc.model_builder.set_extract_statuses(pair_statuses)
        if latest_validate_statuses is not None:
            pair_validate_statuses = [s for s in latest_validate_statuses.statuses if s.pair_id == pc.pair_id]
            pc.model_builder.set_validate_statuses(pair_validate_statuses)

    def _sync_persist_to_all_builders(self):  # noqa: C901 — will be decomposed in #394
        """Push current persist state to all pair model builders, filtered by pair_id."""
        namespaced_prefixes = tuple(
            f"{other_pc.pair_id}{sep}"
            for other_pc in self.__pair_contexts
            if other_pc.pair_id
            for sep in (KEY_SEP, ":")
        )
        for pc in self.__pair_contexts:
            prefix = f"{pc.pair_id}{KEY_SEP}" if pc.pair_id else ""
            # Defense-in-depth: from_str() migrates colon keys at load time,
            # but we check both separators here in case of incomplete migration.
            legacy_prefix = f"{pc.pair_id}:" if pc.pair_id else ""
            downloaded: set[str] = set()
            extracted: set[str] = set()
            extract_failed: set[str] = set()
            validated: set[str] = set()
            corrupt: set[str] = set()
            for key in self.__persist.downloaded_file_names:
                if prefix and key.startswith(prefix):
                    downloaded.add(key[len(prefix) :])
                elif prefix and legacy_prefix and key.startswith(legacy_prefix):
                    downloaded.add(key[len(legacy_prefix) :])
                elif not prefix and not key.startswith(namespaced_prefixes):
                    downloaded.add(key)
            for key in self.__persist.extracted_file_names:
                if prefix and key.startswith(prefix):
                    extracted.add(key[len(prefix) :])
                elif prefix and legacy_prefix and key.startswith(legacy_prefix):
                    extracted.add(key[len(legacy_prefix) :])
                elif not prefix and not key.startswith(namespaced_prefixes):
                    extracted.add(key)
            for key in self.__persist.extract_failed_file_names:
                if prefix and key.startswith(prefix):
                    extract_failed.add(key[len(prefix) :])
                elif prefix and legacy_prefix and key.startswith(legacy_prefix):
                    extract_failed.add(key[len(legacy_prefix) :])
                elif not prefix and not key.startswith(namespaced_prefixes):
                    extract_failed.add(key)
            for key in self.__persist.validated_file_names:
                if prefix and key.startswith(prefix):
                    validated.add(key[len(prefix) :])
                elif prefix and legacy_prefix and key.startswith(legacy_prefix):
                    validated.add(key[len(legacy_prefix) :])
                elif not prefix and not key.startswith(namespaced_prefixes):
                    validated.add(key)
            for key in self.__persist.corrupt_file_names:
                if prefix and key.startswith(prefix):
                    corrupt.add(key[len(prefix) :])
                elif prefix and legacy_prefix and key.startswith(legacy_prefix):
                    corrupt.add(key[len(legacy_prefix) :])
                elif not prefix and not key.startswith(namespaced_prefixes):
                    corrupt.add(key)
            pc.model_builder.set_downloaded_files(downloaded)
            pc.model_builder.set_extracted_files(extracted)
            pc.model_builder.set_extract_failed_files(extract_failed)
            pc.model_builder.set_validated_files(validated)
            pc.model_builder.set_corrupt_files(corrupt)
