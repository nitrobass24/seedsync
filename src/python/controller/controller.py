# Copyright 2017, Inderpreet Singh, All rights reserved.

from __future__ import annotations

import copy
import fnmatch
import logging
import os
from abc import ABC, abstractmethod
from collections.abc import Callable
from enum import Enum
from queue import Queue
from threading import Lock
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from system import SystemFile

from common import AppError, AppOneShotProcess, Constants, Context, MultiprocessingLogger
from lftp import Lftp, LftpError, LftpJobStatus
from model import IModelListener, Model, ModelDiff, ModelDiffUtil, ModelError, ModelFile

from .controller_persist import ControllerPersist
from .delete import DeleteLocalProcess, DeleteRemoteProcess
from .extract import ExtractProcess, ExtractRequest, ExtractStatus, ExtractStatusResult
from .model_builder import ModelBuilder
from .move import MoveProcess

# my libs
from .scan import ActiveScanner, LocalScanner, RemoteScanner, ScannerProcess, ScannerResult
from .validate import ValidateProcess, ValidateRequest, ValidateStatusResult


def _matches_exclude(name: str, is_dir: bool, patterns: list[tuple[str, bool]]) -> bool:
    """Return True if *name* matches any of the exclude patterns (case-insensitive).

    Each pattern is a (glob, dir_only) tuple.  When dir_only is True the
    pattern only matches directories.
    """
    name_lower = name.lower()
    return any(fnmatch.fnmatch(name_lower, p.lower()) and (not dir_only or is_dir) for p, dir_only in patterns)


def _filter_children(file: SystemFile, patterns: list[tuple[str, bool]]) -> SystemFile:
    """Return a copy of *file* with excluded children (and their subtrees) removed.

    If a directory child matches a pattern the entire subtree is dropped.
    Non-matching directory children are recursed into so their own children
    are filtered as well.  Directory sizes are preserved from the original file.
    """
    from system import SystemFile  # avoid circular import at module level

    kept_children: list[SystemFile] = []
    for child in file.children:
        if _matches_exclude(child.name, child.is_dir, patterns):
            continue  # drop matched child (and its subtree)
        if child.is_dir:
            child = _filter_children(child, patterns)
        kept_children.append(child)

    filtered = SystemFile(
        name=file.name,
        size=file.size,
        is_dir=file.is_dir,
        time_created=file.timestamp_created,
        time_modified=file.timestamp_modified,
    )
    for child in kept_children:
        filtered.add_child(child)
    return filtered


def parse_exclude_patterns(exclude_patterns_str: str) -> list[str]:
    """Parse a comma-separated exclude pattern string into a list of individual patterns.

    Trailing slashes are preserved so callers can distinguish directory-only
    patterns from file patterns when needed.
    """
    if not exclude_patterns_str or not exclude_patterns_str.strip():
        return []
    patterns: list[str] = []
    for p in exclude_patterns_str.split(","):
        p = p.strip()
        if p:
            patterns.append(p)
    return patterns


def filter_excluded_files(files: list[SystemFile], exclude_patterns_str: str) -> list[SystemFile]:
    parsed = parse_exclude_patterns(exclude_patterns_str)
    if not parsed:
        return files
    patterns = [(p.rstrip("/"), p.endswith("/")) for p in parsed]
    result: list[SystemFile] = []
    for f in files:
        if _matches_exclude(f.name, f.is_dir, patterns):
            continue
        if f.is_dir:
            f = _filter_children(f, patterns)
        result.append(f)
    return result


class ControllerError(AppError):
    """
    Exception indicating a controller error
    """

    pass


# ASCII Unit Separator – safe composite-key delimiter that cannot appear in filenames
_KEY_SEP = "\x1f"


def _persist_key(pair_id: str | None, name: str) -> str:
    """Build a namespaced persist key: 'pair_id<US>name' or plain 'name' for default pair."""
    return "{}{}{}".format(pair_id, _KEY_SEP, name) if pair_id else name


def _strip_persist_key(key: str, pair_id: str | None) -> str:
    """Strip pair_id prefix from a persist key to get the bare file name.

    Handles both the current unit-separator (\\x1f) and the legacy colon (':')
    delimiter so that old persisted keys are still correctly parsed.
    """
    if not pair_id:
        return key
    # Try the current separator first, then legacy colon
    for sep in (_KEY_SEP, ":"):
        prefix = "{}{}".format(pair_id, sep)
        if key.startswith(prefix):
            return key[len(prefix) :]
    return key


class _PairContext:
    """
    Holds all per-pair state: LFTP instance, scanners, scanner processes,
    model builder, and download tracking.
    """

    def __init__(
        self,
        pair_id: str | None,
        name: str,
        remote_path: str,
        local_path: str,
        effective_local_path: str,
        lftp: Lftp,
        active_scanner: ActiveScanner,
        local_scanner: LocalScanner,
        remote_scanner: RemoteScanner,
        active_scan_process: ScannerProcess,
        local_scan_process: ScannerProcess,
        remote_scan_process: ScannerProcess,
        model_builder: ModelBuilder,
    ):
        self.pair_id = pair_id
        self.name = name
        self.remote_path = remote_path
        self.local_path = local_path
        self.effective_local_path = effective_local_path
        self.lftp = lftp
        self.active_scanner = active_scanner
        self.local_scanner = local_scanner
        self.remote_scanner = remote_scanner
        self.active_scan_process = active_scan_process
        self.local_scan_process = local_scan_process
        self.remote_scan_process = remote_scan_process
        self.model_builder = model_builder

        # Per-pair tracking state
        self.active_downloading_file_names: list[str] = []
        self.active_extracting_file_names: list[str] = []
        self.prev_downloading_file_names: set[str] = set()
        self.pending_completion: set[str] = set()
        self.remote_scan_received: bool = False
        self.local_scan_received: bool = False

        # Temporary storage for latest scan results (set during _update_pair_model_state)
        self._latest_remote_scan: ScannerResult | None = None
        self._latest_local_scan: ScannerResult | None = None


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

    _MAX_CONCURRENT_COMMAND_PROCESSES = 8

    def __init__(self, context: Context, persist: ControllerPersist):
        self.__context = context
        self.__persist = persist
        self.logger = context.logger.getChild("Controller")

        # Decide the password here
        self.__password = context.config.lftp.remote_password if not context.config.lftp.use_ssh_key else None

        # Validate required config fields before building anything
        self._validate_config()

        # The command queue
        self.__command_queue: Queue[Controller.Command] = Queue()

        # The model (shared across all pairs)
        self.__model = Model()
        self.__model.set_base_logger(self.logger)
        # Lock for the model
        # Note: While the scanners are in a separate process, the rest of the application
        #       is threaded in a single process. (The webserver is bottle+wsgiref which is
        #       multi-threaded). Therefore it is safe to use a threading Lock for the model
        #       (the scanner processes never try to access the model)
        self.__model_lock = Lock()

        # Setup multiprocess logging (shared)
        self.__mp_logger = MultiprocessingLogger(self.logger)

        # Build pair contexts, then seed each builder with filtered persist state
        self.__pair_contexts: list[_PairContext] = self._build_pair_contexts()
        self._sync_persist_to_all_builders()

        # Setup extract process (global -- extraction is local-only)
        self.__extract_process = ExtractProcess()
        self.__extract_process.set_mp_log_queue(self.__mp_logger.queue, self.__mp_logger.log_level)

        # Setup validate process (global -- validation uses SSH to remote)
        self.__validate_process = ValidateProcess()
        self.__validate_process.set_mp_log_queue(self.__mp_logger.queue, self.__mp_logger.log_level)

        # Keep track of active command processes (shared)
        self.__active_command_processes: list[Controller.CommandProcessWrapper] = []

        # Keep track of active move processes (staging -> final, shared)
        self.__active_move_processes: list[MoveProcess] = []
        # Use composite keys (pair_id:name) to avoid collisions across pairs
        self.__moved_file_keys: set[str] = set()

        # Track files with pending validation so extraction-completion doesn't race the move
        self.__pending_validation_keys: set[str] = set()

        # Track extraction retry counts by composite key (in-memory, resets on restart)

        self.__started = False

    def _validate_config(self) -> None:
        """Validate that all required config fields are set (non-None) at startup.

        Collects all missing fields and raises a single ControllerError listing them.
        """
        missing: list[str] = []
        config = self.__context.config

        # Lftp required fields
        lftp_fields = [
            "remote_address",
            "remote_username",
            "remote_port",
            "remote_path_to_scan_script",
            "use_ssh_key",
            "use_temp_file",
            "num_max_parallel_downloads",
            "num_max_parallel_files_per_download",
            "num_max_connections_per_root_file",
            "num_max_connections_per_dir_file",
            "num_max_total_connections",
        ]
        for field in lftp_fields:
            if getattr(config.lftp, field) is None:
                missing.append("Lftp.{}".format(field))

        # Controller required fields
        controller_fields = [
            "interval_ms_remote_scan",
            "interval_ms_local_scan",
            "interval_ms_downloading_scan",
        ]
        for field in controller_fields:
            if getattr(config.controller, field) is None:
                missing.append("Controller.{}".format(field))

        # General required fields
        if config.general.verbose is None:
            missing.append("General.verbose")

        # AutoQueue required fields
        if config.autoqueue.auto_delete_remote is None:
            missing.append("AutoQueue.auto_delete_remote")

        # Args required fields
        if self.__context.args.local_path_to_scanfs is None:
            missing.append("Args.local_path_to_scanfs")

        if missing:
            raise ControllerError("Required config fields are not set: {}".format(", ".join(missing)))

    def _build_pair_contexts(self) -> list[_PairContext]:
        """
        Build a _PairContext for each configured path pair.
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
                    "No path pairs configured and {} not set. "
                    "Configure at least one path pair in Settings, or set {}.".format(fields, fields)
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
        contexts: list[_PairContext] = []
        for pair in enabled_pairs:
            contexts.append(
                self._create_pair_context(
                    pair_id=pair.id, name=pair.name, remote_path=pair.remote_path, local_path=pair.local_path
                )
            )
        return contexts

    def _create_pair_context(self, pair_id: str | None, name: str, remote_path: str, local_path: str) -> _PairContext:
        """
        Create a fully wired _PairContext with its own LFTP, scanners, and model builder.
        """
        pair_label = name or pair_id or "default"
        pair_logger = self.logger.getChild("Pair[{}]".format(pair_label))

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

        return _PairContext(
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
        """Apply shared LFTP configuration settings."""
        cfg = self.__context.config.lftp
        lftp.num_parallel_jobs = cfg.num_max_parallel_downloads  # type: ignore[assignment]
        lftp.num_parallel_files = cfg.num_max_parallel_files_per_download  # type: ignore[assignment]
        lftp.num_connections_per_root_file = cfg.num_max_connections_per_root_file  # type: ignore[assignment]
        lftp.num_connections_per_dir_file = cfg.num_max_connections_per_dir_file  # type: ignore[assignment]
        lftp.num_max_total_connections = cfg.num_max_total_connections  # type: ignore[assignment]
        lftp.use_temp_file = cfg.use_temp_file  # type: ignore[assignment]
        lftp.temp_file_name = "*" + Constants.LFTP_TEMP_FILE_SUFFIX
        if cfg.net_limit_rate:
            lftp.rate_limit = cfg.net_limit_rate
        if cfg.net_socket_buffer:
            lftp.net_socket_buffer = cfg.net_socket_buffer
        if cfg.pget_min_chunk_size:
            lftp.min_chunk_size = cfg.pget_min_chunk_size
        if cfg.mirror_parallel_directories is not None:
            lftp.mirror_parallel_directories = cfg.mirror_parallel_directories
        if cfg.net_timeout is not None:
            lftp.net_timeout = cfg.net_timeout
        if cfg.net_max_retries is not None:
            lftp.net_max_retries = cfg.net_max_retries
        if cfg.net_reconnect_interval_base is not None:
            lftp.net_reconnect_interval_base = cfg.net_reconnect_interval_base
        if cfg.net_reconnect_interval_multiplier is not None:
            lftp.net_reconnect_interval_multiplier = cfg.net_reconnect_interval_multiplier
        # Configure inline transfer verification
        validate_cfg = self.__context.config.validate
        if validate_cfg.xfer_verify:
            lftp.xfer_verify = True
            lftp.xfer_verify_command = "{}sum".format(validate_cfg.algorithm)
        else:
            lftp.xfer_verify = False
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
        self.__propagate_exceptions()
        self.__cleanup_commands()
        self.__process_commands()
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
            for cp in self.__active_command_processes:
                cp.process.terminate()
            for mp in self.__active_move_processes:
                mp.terminate()
            for pc in self.__pair_contexts:
                pc.active_scan_process.join()
                pc.local_scan_process.join()
                pc.remote_scan_process.join()
            self.__extract_process.join()
            self.__validate_process.join()
            for cp in self.__active_command_processes:
                cp.process.join()
            for mp in self.__active_move_processes:
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
            for cp in self.__active_command_processes:
                cp.process.close_queues()
            for mp in self.__active_move_processes:
                mp.close_queues()
            self.__active_command_processes.clear()
            self.__active_move_processes.clear()

            self.__started = False
            self.logger.info("Exited controller")

    def get_model_files(self) -> list[ModelFile]:
        """
        Returns a copy of all the model files
        :return:
        """
        self.__model_lock.acquire()
        model_files = self.__get_model_files()
        self.__model_lock.release()
        return model_files

    def add_model_listener(self, listener: IModelListener):
        """
        Adds a listener to the controller's model
        :param listener:
        :return:
        """
        self.__model_lock.acquire()
        self.__model.add_listener(listener)
        self.__model_lock.release()

    def remove_model_listener(self, listener: IModelListener):
        """
        Removes a listener from the controller's model
        :param listener:
        :return:
        """
        self.__model_lock.acquire()
        self.__model.remove_listener(listener)
        self.__model_lock.release()

    def get_model_files_and_add_listener(self, listener: IModelListener):
        """
        Adds a listener and returns the current state of model files in one atomic operation
        :param listener:
        :return:
        """
        self.__model_lock.acquire()
        self.__model.add_listener(listener)
        model_files = self.__get_model_files()
        self.__model_lock.release()
        return model_files

    def queue_command(self, command: Command):
        self.__command_queue.put(command)

    def __get_model_files(self) -> list[ModelFile]:
        model_files: list[ModelFile] = []
        for file in self.__model.get_all_files():
            model_files.append(copy.deepcopy(file))
        return model_files

    def _get_pair_context_for_command(self, command: Command) -> _PairContext | None:
        """Find the pair context for a command based on pair_id."""
        if command.pair_id:
            for pc in self.__pair_contexts:
                if pc.pair_id == command.pair_id:
                    return pc
            return None
        return self.__pair_contexts[0] if self.__pair_contexts else None

    def _get_pair_context_for_file(self, file: ModelFile) -> _PairContext | None:
        """Find the pair context that owns a ModelFile based on its pair_id."""
        for pc in self.__pair_contexts:
            if pc.pair_id == file.pair_id:
                return pc
        return None

    def _find_pair_by_id(self, pair_id: str | None) -> _PairContext | None:
        """Find the pair context by pair_id.
        Returns default (first) pair when pair_id is None.
        Returns None when pair_id is provided but not found.
        """
        if pair_id:
            for pc in self.__pair_contexts:
                if pc.pair_id == pair_id:
                    return pc
            return None
        return self.__pair_contexts[0] if self.__pair_contexts else None

    def _build_extract_request(self, file: ModelFile, pc: _PairContext) -> ExtractRequest:
        """Build an ExtractRequest with the correct pair-specific paths."""
        # Determine output directory
        if self.__context.config.controller.use_local_path_as_extract_path:
            extract_out_dir = pc.local_path
        else:
            extract_out_dir = self.__context.config.controller.extract_path  # type: ignore[assignment]

        # When staging is enabled, archives live in the staging subdir
        if self.__context.config.controller.use_staging and self.__context.config.controller.staging_path:
            pair_staging = (
                os.path.join(self.__context.config.controller.staging_path, pc.pair_id)  # type: ignore[arg-type]
                if pc.pair_id
                else self.__context.config.controller.staging_path  # type: ignore[arg-type]
            )
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

    def __update_model(self):
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
                owner_pc = self._find_pair_by_id(result.pair_id)
                if owner_pc is None:
                    self.logger.warning(
                        "Ignoring extract completion for '{}': pair '{}' no longer exists".format(
                            result.name, result.pair_id
                        )
                    )
                    continue
                pkey = _persist_key(result.pair_id, result.name)
                self.__persist.extracted_file_names.add(pkey)
                if self.__context.config.controller.use_staging and self.__context.config.controller.staging_path:
                    if pkey not in self.__pending_validation_keys:
                        self.__spawn_move_process(result.name, owner_pc)
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

            self.__model_lock.acquire()
            try:
                model_diff = ModelDiffUtil.diff_models(self.__model, new_model)

                for diff in model_diff:
                    if diff.change == ModelDiff.Change.ADDED:
                        assert diff.new_file is not None
                        self.__model.add_file(diff.new_file)
                    elif diff.change == ModelDiff.Change.REMOVED:
                        assert diff.old_file is not None
                        self.__model.remove_file(diff.old_file.name, pair_id=diff.old_file.pair_id)
                    elif diff.change == ModelDiff.Change.UPDATED:
                        assert diff.new_file is not None
                        self.__model.update_file(diff.new_file)

                    diff_file = diff.new_file or diff.old_file
                    assert diff_file is not None
                    pc = self._get_pair_context_for_file(diff_file)

                    if diff.new_file is not None and diff.new_file.state in (
                        ModelFile.State.QUEUED,
                        ModelFile.State.DOWNLOADING,
                    ):
                        pkey = _persist_key(diff.new_file.pair_id, diff.new_file.name)
                        self.__moved_file_keys.discard(pkey)
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
                    ):
                        downloaded = True
                    elif (
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
                        pkey = _persist_key(diff.new_file.pair_id, diff.new_file.name)
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
                            self.__pending_validation_keys.add(_persist_key(pc.pair_id, diff.new_file.name))
                            self.logger.info("Auto-queued validation for '{}'".format(diff.new_file.name))

                        if (
                            self.__context.config.controller.use_staging
                            and self.__context.config.controller.staging_path
                        ):
                            will_auto_extract = (
                                self.__context.config.autoqueue.auto_extract and diff.new_file.is_extractable
                            )
                            will_auto_validate = (
                                self.__context.config.validate.enabled
                                and self.__context.config.validate.auto_validate
                                and diff.new_file.remote_size is not None
                            )
                            if not will_auto_extract and not will_auto_validate:
                                self.__spawn_move_process(diff.new_file.name, pc)

                    if diff.new_file is not None and pc is not None and diff.new_file.name in pc.pending_completion:
                        use_staging = (
                            self.__context.config.controller.use_staging
                            and self.__context.config.controller.staging_path
                        )
                        # A file with no local presence and DEFAULT state means
                        # it was deleted locally (e.g. stopped download whose files
                        # were removed). Nothing left to track.
                        if diff.new_file.state == ModelFile.State.DEFAULT and diff.new_file.local_size is None:
                            pc.pending_completion.discard(diff.new_file.name)
                        elif use_staging:
                            move_key = _persist_key(diff.new_file.pair_id, diff.new_file.name)
                            if move_key in self.__moved_file_keys:
                                pc.pending_completion.discard(diff.new_file.name)
                            elif diff.new_file.state in (
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
                        bare_name = _strip_persist_key(pkey, _pc.pair_id)
                        if bare_name != pkey or _pc.pair_id is None:
                            try:
                                file = self.__model.get_file(bare_name, pair_id=_pc.pair_id)
                                if file.state == ModelFile.State.DELETED:
                                    remove_extracted_keys.add(pkey)
                            except ModelError:
                                pass
                if remove_extracted_keys:
                    self.logger.info("Removing from extracted list: {}".format(remove_extracted_keys))
                    self.__persist.extracted_file_names.difference_update(remove_extracted_keys)
                    self._sync_persist_to_all_builders()

                # Persist cleanup: remove entries for files absent from all sources
                all_scans_received = all(
                    _pc.remote_scan_received and _pc.local_scan_received for _pc in self.__pair_contexts
                )
                if all_scans_received:
                    # Build a set of all composite keys present in the model
                    model_keys: set[str] = set()
                    for f in self.__model.get_all_files():
                        model_keys.add(_persist_key(f.pair_id, f.name))
                    absent_keys: set[str] = set()
                    for pkey in self.__persist.downloaded_file_names:
                        if pkey not in model_keys and pkey not in self.__moved_file_keys:
                            absent_keys.add(pkey)
                    if absent_keys:
                        self.logger.info("Persist cleanup (both absent): {}".format(absent_keys))
                        self.__persist.downloaded_file_names.difference_update(absent_keys)
                        self.__persist.extracted_file_names.difference_update(absent_keys)
                        self.__persist.extract_failed_file_names.difference_update(absent_keys)
                        self.__persist.validated_file_names.difference_update(absent_keys)
                        self.__persist.corrupt_file_names.difference_update(absent_keys)
                        self._sync_persist_to_all_builders()

            finally:
                self.__model_lock.release()

        # Process extraction failures — mark as failed immediately
        for result in latest_failed_extractions:
            self.logger.error("Extraction failed for '{}'".format(result.name))
            fail_key = _persist_key(result.pair_id, result.name)
            self.__persist.extract_failed_file_names.add(fail_key)
            self._sync_persist_to_all_builders()

        # Process validation completions — mark as validated
        for result in latest_validated_results:
            self.logger.info("Validation passed for '{}'".format(result.name))
            pkey = _persist_key(result.pair_id, result.name)
            self.__pending_validation_keys.discard(pkey)
            self.__persist.validated_file_names.add(pkey)
            self.__persist.corrupt_file_names.discard(pkey)
            self._sync_persist_to_all_builders()
            # If staging is active, spawn the move process now that validation finished
            self._spawn_deferred_move(result.pair_id, result.name)

        # Process validation failures
        for result in latest_failed_validations:
            self.logger.error("Validation failed for '{}': {}".format(result.name, result.error_message))
            pkey = _persist_key(result.pair_id, result.name)
            self.__pending_validation_keys.discard(pkey)
            if result.is_checksum_mismatch:
                # Checksum mismatch — mark as corrupt
                self.__persist.corrupt_file_names.add(pkey)
                self.__persist.validated_file_names.discard(pkey)
                self._sync_persist_to_all_builders()
            else:
                # Non-mismatch failure (SSH error, etc.) — don't mark corrupt,
                # just log so the user can retry
                self.logger.warning(
                    "Validation error for '{}' (not marking corrupt): {}".format(result.name, result.error_message)
                )
            # Spawn deferred move regardless of failure type — validation is done
            self._spawn_deferred_move(result.pair_id, result.name)

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

    def _update_pair_model_state(
        self,
        pc: _PairContext,
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
            self.logger.warning("Caught lftp error (pair {}): {}".format(pc.name, str(e)))

        if latest_remote_scan is not None:
            pc.remote_scan_received = True
        if latest_local_scan is not None:
            pc.local_scan_received = True

        if lftp_statuses is not None:
            current_downloading = set(s.name for s in lftp_statuses if s.state == LftpJobStatus.State.RUNNING)
            just_completed = pc.prev_downloading_file_names - current_downloading
            if just_completed:
                for name in just_completed:
                    self.logger.info("Download completed (LFTP job finished): {}".format(name))
                self.__persist.downloaded_file_names.update(_persist_key(pc.pair_id, n) for n in just_completed)
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
                and _persist_key(pc.pair_id, s.name) in self.__persist.downloaded_file_names
            ]

        active_files = pc.active_downloading_file_names + pc.active_extracting_file_names
        active_files += list(pc.pending_completion)
        pc.active_scanner.set_active_files(active_files)

        pc.model_builder.set_auto_delete_remote(bool(self.__context.config.autoqueue.auto_delete_remote))

        if latest_remote_scan is not None:
            remote_files = self._apply_exclude_patterns(latest_remote_scan.files)
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

    def _sync_persist_to_all_builders(self):
        """Push current persist state to all pair model builders, filtered by pair_id."""
        namespaced_prefixes = tuple(
            f"{other_pc.pair_id}{sep}"
            for other_pc in self.__pair_contexts
            if other_pc.pair_id
            for sep in (_KEY_SEP, ":")
        )
        for pc in self.__pair_contexts:
            prefix = f"{pc.pair_id}{_KEY_SEP}" if pc.pair_id else ""
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

    def __process_commands(self):
        def _notify_failure(_command: Controller.Command, _msg: str):
            self.logger.warning("Command failed. {}".format(_msg))
            for _callback in _command.callbacks:
                _callback.on_failure(_msg)

        deferred: list[Controller.Command] = []

        while not self.__command_queue.empty():
            command = self.__command_queue.get()
            self.logger.info("Received command {} for file {}".format(str(command.action), command.filename))

            pc = self._get_pair_context_for_command(command)
            if pc is None:
                _notify_failure(command, "No pair context found for pair_id '{}'".format(command.pair_id))
                continue

            try:
                file = self.__model.get_file(command.filename, pair_id=pc.pair_id)
            except ModelError:
                _notify_failure(command, "File '{}' not found".format(command.filename))
                continue

            if command.action == Controller.Command.Action.QUEUE:
                if file.remote_size is None:
                    _notify_failure(command, "File '{}' does not exist remotely".format(command.filename))
                    continue
                try:
                    exclude = parse_exclude_patterns(self.__context.config.general.exclude_patterns)
                    pc.lftp.queue(file.name, file.is_dir, exclude_patterns=exclude)
                except LftpError as e:
                    _notify_failure(command, "Lftp error: {}".format(str(e)))
                    continue

            elif command.action == Controller.Command.Action.STOP:
                if file.state not in (ModelFile.State.DOWNLOADING, ModelFile.State.QUEUED):
                    _notify_failure(command, "File '{}' is not Queued or Downloading".format(command.filename))
                    continue
                try:
                    pc.lftp.kill(file.name)
                except LftpError as e:
                    _notify_failure(command, "Lftp error: {}".format(str(e)))
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
                    _notify_failure(
                        command, "File '{}' in state {} cannot be extracted".format(command.filename, str(file.state))
                    )
                    continue
                elif file.local_size is None:
                    _notify_failure(command, "File '{}' does not exist locally".format(command.filename))
                    continue
                else:
                    pkey = _persist_key(pc.pair_id, file.name)
                    self.__persist.extract_failed_file_names.discard(pkey)
                    self._sync_persist_to_all_builders()
                    req = self._build_extract_request(file, pc)
                    self.__extract_process.extract(req)

            elif command.action == Controller.Command.Action.DELETE_LOCAL:
                if len(self.__active_command_processes) >= Controller._MAX_CONCURRENT_COMMAND_PROCESSES:
                    self.logger.debug(
                        "Deferring %s for '%s': %d active processes at cap",
                        command.action,
                        command.filename,
                        len(self.__active_command_processes),
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
                        "Local file '{}' cannot be deleted in state {}".format(command.filename, str(file.state)),
                    )
                    continue
                elif file.local_size is None:
                    _notify_failure(command, "File '{}' does not exist locally".format(command.filename))
                    continue
                else:
                    delete_path = pc.local_path
                    if self.__context.config.controller.use_staging and self.__context.config.controller.staging_path:
                        pair_staging = (
                            os.path.join(self.__context.config.controller.staging_path, pc.pair_id)  # type: ignore[arg-type]
                            if pc.pair_id
                            else self.__context.config.controller.staging_path  # type: ignore[arg-type]
                        )
                        staging_file = os.path.join(pair_staging, file.name)  # type: ignore[arg-type]
                        if os.path.exists(staging_file):
                            delete_path = pair_staging
                    process = DeleteLocalProcess(local_path=delete_path, file_name=file.name)
                    process.set_mp_log_queue(self.__mp_logger.queue, self.__mp_logger.log_level)

                    def post_callback(delete_path: str = delete_path, _pc: _PairContext = pc) -> None:
                        _pc.local_scan_process.force_scan()
                        if delete_path != _pc.local_path:
                            _pc.active_scan_process.force_scan()

                    command_wrapper = Controller.CommandProcessWrapper(process=process, post_callback=post_callback)
                    self.__active_command_processes.append(command_wrapper)
                    command_wrapper.process.start()

            elif command.action == Controller.Command.Action.DELETE_REMOTE:
                if len(self.__active_command_processes) >= Controller._MAX_CONCURRENT_COMMAND_PROCESSES:
                    self.logger.debug(
                        "Deferring %s for '%s': %d active processes at cap",
                        command.action,
                        command.filename,
                        len(self.__active_command_processes),
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
                        "Remote file '{}' cannot be deleted in state {}".format(command.filename, str(file.state)),
                    )
                    continue
                elif file.remote_size is None:
                    _notify_failure(command, "File '{}' does not exist remotely".format(command.filename))
                    continue
                else:
                    process = DeleteRemoteProcess(
                        remote_address=self.__context.config.lftp.remote_address,  # type: ignore[arg-type]
                        remote_username=self.__context.config.lftp.remote_username,  # type: ignore[arg-type]
                        remote_password=self.__password,
                        remote_port=self.__context.config.lftp.remote_port,  # type: ignore[arg-type]
                        remote_path=pc.remote_path,
                        file_name=file.name,
                    )
                    process.set_mp_log_queue(self.__mp_logger.queue, self.__mp_logger.log_level)
                    command_wrapper = Controller.CommandProcessWrapper(
                        process=process, post_callback=pc.remote_scan_process.force_scan
                    )
                    self.__active_command_processes.append(command_wrapper)
                    command_wrapper.process.start()

            elif command.action == Controller.Command.Action.VALIDATE:
                if not self.__context.config.validate.enabled:
                    _notify_failure(command, "Validation is not enabled in config")
                    continue
                if file.state not in (
                    ModelFile.State.DOWNLOADED,
                    ModelFile.State.EXTRACTED,
                    ModelFile.State.EXTRACT_FAILED,
                    ModelFile.State.VALIDATED,
                    ModelFile.State.CORRUPT,
                ):
                    _notify_failure(
                        command, "File '{}' in state {} cannot be validated".format(command.filename, str(file.state))
                    )
                    continue
                elif file.local_size is None:
                    _notify_failure(command, "File '{}' does not exist locally".format(command.filename))
                    continue
                elif file.remote_size is None:
                    _notify_failure(command, "File '{}' does not exist remotely".format(command.filename))
                    continue
                else:
                    pkey = _persist_key(pc.pair_id, file.name)
                    self.__persist.validated_file_names.discard(pkey)
                    self.__persist.corrupt_file_names.discard(pkey)
                    self._sync_persist_to_all_builders()
                    req = ValidateRequest(
                        name=file.name,
                        is_dir=file.is_dir,
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
                    self.__pending_validation_keys.add(pkey)

            for callback in command.callbacks:
                callback.on_success()

        for cmd in deferred:
            self.__command_queue.put(cmd)

    def __propagate_exceptions(self):
        """
        Propagate any exceptions from child processes/threads to this thread
        :return:
        """
        for pc in self.__pair_contexts:
            try:
                pc.lftp.raise_pending_error()
            except LftpError as e:
                error_str = str(e)
                permanent_patterns = ["Login failed", "Access failed"]
                if any(p in error_str for p in permanent_patterns):
                    raise AppError(error_str) from e
                self.logger.warning("Caught lftp error: {}".format(error_str))
            pc.active_scan_process.propagate_exception()
            pc.local_scan_process.propagate_exception()
            pc.remote_scan_process.propagate_exception()
        self.__mp_logger.propagate_exception()
        self.__extract_process.propagate_exception()
        self.__validate_process.propagate_exception()

    def _spawn_deferred_move(self, pair_id: str | None, file_name: str):
        """Spawn the staging→final move for a file whose validation just finished.

        Only acts when staging is enabled; looks up the owning pair context by pair_id.
        """
        if not (self.__context.config.controller.use_staging and self.__context.config.controller.staging_path):
            return
        pc = self._find_pair_by_id(pair_id)
        if pc is None:
            self.logger.warning("Cannot spawn deferred move for '{}': pair '{}' not found".format(file_name, pair_id))
            return
        self.__spawn_move_process(file_name, pc)

    def __spawn_move_process(self, file_name: str, pc: _PairContext):
        """
        Spawn a MoveProcess to move a file from staging to the final local_path
        """
        pair_id = pc.pair_id
        move_key = _persist_key(pair_id, file_name)
        if move_key in self.__moved_file_keys:
            self.logger.debug("Skipping move for {} - already moved".format(file_name))
            return

        dest_path = pc.local_path
        # Use per-pair staging subdirectory
        # All callers guard with `use_staging and staging_path` so this is safe
        staging_path = self.__context.config.controller.staging_path
        assert isinstance(staging_path, str)
        staging_source: str = os.path.join(staging_path, pair_id) if pair_id else staging_path

        # Skip if the file doesn't exist in staging (e.g. already moved in a prior session)
        staging_file = os.path.join(staging_source, file_name)
        if not os.path.exists(staging_file):
            self.logger.debug("Skipping move for {} - not found in staging".format(file_name))
            self.__moved_file_keys.add(move_key)
            return

        self.__moved_file_keys.add(move_key)
        process = MoveProcess(source_path=staging_source, dest_path=dest_path, file_name=file_name, pair_id=pair_id)
        process.set_mp_log_queue(self.__mp_logger.queue, self.__mp_logger.log_level)
        self.__active_move_processes.append(process)
        process.start()
        self.logger.info("Spawned move process for {} (staging -> local)".format(file_name))

    def __cleanup_commands(self):
        """
        Cleanup the list of active commands and do any callbacks
        :return:
        """
        still_active_processes: list[Controller.CommandProcessWrapper] = []
        for command_process in self.__active_command_processes:
            if command_process.process.is_alive():
                still_active_processes.append(command_process)
            else:
                command_process.post_callback()
                try:
                    command_process.process.propagate_exception()
                except Exception:
                    self.logger.warning("Command process failed: %s", command_process.process.name, exc_info=True)
        self.__active_command_processes = still_active_processes

        still_active_moves: list[MoveProcess] = []
        for move_process in self.__active_move_processes:
            if move_process.is_alive():
                still_active_moves.append(move_process)
            else:
                try:
                    move_process.propagate_exception()
                except Exception:
                    self.logger.warning("Move process failed: %s", move_process.name, exc_info=True)
                    move_key = _persist_key(move_process.pair_id, move_process.file_name)
                    self.__moved_file_keys.discard(move_key)
                for pc in self.__pair_contexts:
                    pc.local_scan_process.force_scan()
        self.__active_move_processes = still_active_moves

    def _apply_exclude_patterns(self, files: list[SystemFile]) -> list[SystemFile]:
        raw = self.__context.config.general.exclude_patterns
        return filter_excluded_files(files, raw)
