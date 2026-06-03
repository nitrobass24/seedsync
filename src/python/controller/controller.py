# Copyright 2017, Inderpreet Singh, All rights reserved.

from __future__ import annotations

import os
import threading
from collections.abc import Callable, Iterator

from common import AppProcess, Constants, Context, MultiprocessingLogger
from lftp import Lftp
from model import IModelListener, Model, ModelFile

from .command_pipeline import CommandPipeline
from .commands import MAX_CONCURRENT_COMMAND_PROCESSES, Command, CommandProcessWrapper
from .controller_persist import ControllerPersist

# my libs
from .extract import ExtractProcess
from .model_builder import ModelBuilder
from .model_registry import ModelRegistry
from .model_updater import ModelUpdater
from .pair_context import ControllerError, PairContext, configure_lftp, validate_config
from .persist_sync import PersistSync
from .scan import ActiveScanner, LocalScanner, RemoteScanner, ScannerProcess
from .validate import ValidateProcess


class Controller:
    """
    Top-level class that controls the behaviour of the app
    """

    # Re-exported from .commands so existing Controller.Command,
    # Controller.CommandProcessWrapper, and Controller.MAX_CONCURRENT_COMMAND_PROCESSES
    # references resolve to the same objects shared with CommandPipeline.
    Command = Command
    CommandProcessWrapper = CommandProcessWrapper
    MAX_CONCURRENT_COMMAND_PROCESSES = MAX_CONCURRENT_COMMAND_PROCESSES

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

        # Build pair contexts (persist state is seeded after updater creation below)
        self.__pair_contexts: list[PairContext] = self._build_pair_contexts()

        # Setup extract process (global -- extraction is local-only)
        self.__extract_process = ExtractProcess()
        self.__extract_process.set_mp_log_queue(self.__mp_logger.queue, self.__mp_logger.log_level)

        # Setup validate process (global -- validation uses SSH to remote)
        self.__validate_process = ValidateProcess()
        self.__validate_process.set_mp_log_queue(self.__mp_logger.queue, self.__mp_logger.log_level)

        # Persist sync is a standalone collaborator so the pipeline and updater
        # share the exact same instance with no construction-order placeholder.
        self.__persist_sync = PersistSync(self.__pair_contexts, self.__persist)

        # Command pipeline owns the queue, active processes, and move state.
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
            sync_persist_callback=self.__persist_sync.sync,
        )

        # Model updater owns the per-cycle update loop
        self.__updater = ModelUpdater(
            pair_contexts=self.__pair_contexts,
            persist=self.__persist,
            pipeline=self.__pipeline,
            registry=self.__registry,
            extract_process=self.__extract_process,
            validate_process=self.__validate_process,
            context=self.__context,
            password=self.__password,
            logger=self.logger,
            persist_sync=self.__persist_sync,
        )

        # Seed each builder with filtered persist state
        self.__persist_sync.sync()

        # Flag for hot-reloading LFTP tuning settings (set from REST thread)
        self.__needs_lftp_reconfigure = threading.Event()

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
        # Persist state is filtered per-pair by ModelUpdater.sync_persist_to_all_builders()
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
        # Mark started before launching children so that a partial failure here
        # still lets exit() tear down whatever did start (exit() is best-effort).
        # Otherwise exit() would early-return on __started=False and leak the
        # already-started processes and their queue FDs.
        self.__started = True
        for pc in self.__pair_contexts:
            pc.active_scan_process.start()
            pc.local_scan_process.start()
            pc.remote_scan_process.start()
        self.__extract_process.start()
        self.__validate_process.start()
        self.__mp_logger.start()

    def request_lftp_reconfigure(self) -> None:
        """Signal that LFTP tuning settings have changed and should be reapplied.

        Thread-safe: called from the REST handler thread.
        """
        self.__needs_lftp_reconfigure.set()

    def process(self):
        """
        Advance the controller state
        This method should return relatively quickly as the heavy lifting is done by concurrent tasks
        :return:
        """
        if not self.__started:
            raise ControllerError("Cannot process, controller is not started")
        if self.__needs_lftp_reconfigure.is_set():
            self.__needs_lftp_reconfigure.clear()
            for pc in self.__pair_contexts:
                self._configure_lftp(pc.lftp)
            self.logger.info("Reapplied LFTP tuning settings")
        self.__pipeline.propagate_exceptions()
        self.__pipeline.cleanup()
        self.__pipeline.step()
        self.__updater.update()

    def __shutdown_lftp_best_effort(self):
        # A hung/dead lftp PTY can raise here; guard each call so one failure
        # does not abort teardown of the remaining pairs or the worker
        # terminate/join/close_queues phases in exit() (otherwise orphaned
        # processes leak FDs on every restart).
        for pc in self.__pair_contexts:
            try:
                pc.lftp.exit()
            except Exception:
                self.logger.exception(
                    "Error shutting down lftp for pair %s; continuing teardown",
                    getattr(pc, "pair_id", None),
                )

    def __iter_worker_processes(self) -> Iterator[AppProcess]:
        """All terminable worker processes, in teardown order."""
        for pc in self.__pair_contexts:
            yield pc.active_scan_process
            yield pc.local_scan_process
            yield pc.remote_scan_process
        yield self.__extract_process
        yield self.__validate_process
        for cp in self.__pipeline.active_command_processes:
            yield cp.process
        yield from self.__pipeline.active_move_processes

    # Bound each worker join during teardown: a worker stuck in uninterruptible
    # I/O (e.g. a dead NAS mount that ignores the SIGTERM from terminate()) would
    # otherwise hang join() — and thus exit() — forever, wedging ServiceRestart.
    __JOIN_TIMEOUT_IN_SECS = 2

    def __safe_teardown(self, description: str, action: Callable[[], object]) -> None:
        # Teardown is best-effort: a raise from any single terminate/join/
        # close_queues call (a hung or already-closed worker) must not skip the
        # remaining reaping or the FD-releasing close_queues phase, nor propagate
        # out of exit(). Otherwise each restart leaks queue FDs until the OS
        # limit (OSError: [Errno 24] No file descriptors available) is hit.
        try:
            action()
        except Exception:
            self.logger.exception("Error during controller teardown: %s", description)

    def __bounded_join(self, p: AppProcess) -> None:
        self.__safe_teardown("join", lambda: p.join(self.__JOIN_TIMEOUT_IN_SECS))
        try:
            still_alive = p.is_alive()
        except (ValueError, AssertionError):
            still_alive = False
        if still_alive:
            self.logger.warning(
                "Worker %s did not exit within %ss; continuing teardown",
                getattr(p, "name", "?"),
                self.__JOIN_TIMEOUT_IN_SECS,
            )

    def exit(self):
        self.logger.debug("Exiting controller")
        if not self.__started:
            return

        self.__shutdown_lftp_best_effort()
        processes = list(self.__iter_worker_processes())
        for p in processes:
            self.__safe_teardown("terminate", p.terminate)
        for p in processes:
            self.__bounded_join(p)
        self.__safe_teardown("stop mp_logger", self.__mp_logger.stop)

        # Close multiprocessing queues to release file descriptors; this must run
        # even if a terminate()/join() above failed, or each restart cycle leaks
        # FDs until the OS limit is exhausted.
        for p in processes:
            self.__safe_teardown("close_queues", p.close_queues)
        for pc in self.__pair_contexts:
            self.__safe_teardown("close active_scanner", pc.active_scanner.close)
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
