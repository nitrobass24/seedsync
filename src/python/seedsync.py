# Copyright 2017, Inderpreet Singh, All rights reserved.

import argparse
import logging
import multiprocessing
import os
import platform
import shutil
import signal
import sys
import time
from datetime import datetime
from logging.handlers import RotatingFileHandler
from types import FrameType
from typing import TypeVar

if sys.hexversion < 0x030C0000:
    sys.exit("Python 3.12 or newer is required to run this program.")

# my libs
import configparser

from common import (
    AppError,
    Args,
    Config,
    ConfigError,
    Constants,
    Context,
    IntegrationsConfig,
    Localization,
    PathPairsConfig,
    Persist,
    PersistError,
    ServiceExit,
    ServiceRestart,
    Status,
)
from common.json_formatter import JsonFormatter
from controller import AutoQueue, AutoQueuePersist, Controller, ControllerJob, ControllerPersist
from controller.arr_notifier import ArrNotifier
from controller.notifier import WebhookNotifier
from web import WebAppBuilder, WebAppJob

T_Persist = TypeVar("T_Persist", bound=Persist)


class Seedsync:
    """
    Implements the service for seedsync
    It is run in the main thread (no daemonization)
    """

    __FILE_CONFIG = "settings.cfg"
    __FILE_PATH_PAIRS = "path_pairs.json"
    __FILE_INTEGRATIONS = "integrations.json"
    __FILE_AUTO_QUEUE_PERSIST = "autoqueue.persist"
    __FILE_CONTROLLER_PERSIST = "controller.persist"
    __CONFIG_DUMMY_VALUE = "<replace me>"

    # This logger is used to print any exceptions caught at top module
    logger = None

    def __init__(self):
        # Parse the args
        args = self._parse_args(sys.argv[1:])

        # Create/load config
        config = None
        self.config_path = os.path.join(args.config_dir, Seedsync.__FILE_CONFIG)
        create_default_config = False
        if os.path.isfile(self.config_path):
            try:
                config = Config.from_file(self.config_path)
                if Seedsync._backfill_config_defaults(config):
                    config.to_file(self.config_path)
            except (ConfigError, PersistError) as e:
                logging.warning(f"Failed to load config ({e!s}), backing up and using defaults")
                Seedsync.__backup_file(self.config_path)
                create_default_config = True
        else:
            create_default_config = True

        if create_default_config:
            # Create default config
            config = Seedsync._create_default_config()
            config.to_file(self.config_path)

        # Determine the effective log level
        assert config is not None
        # --debug CLI flag overrides config to DEBUG for backward compatibility
        if args.debug:
            effective_log_level = "DEBUG"
        else:
            effective_log_level = config.general.log_level or "INFO"
        is_debug = effective_log_level == "DEBUG"

        # Create context args
        ctx_args = Args()
        ctx_args.local_path_to_scanfs = args.scanfs
        ctx_args.html_path = args.html
        ctx_args.debug = is_debug
        ctx_args.exit = args.exit
        ctx_args.logdir = args.logdir

        # Logger setup
        # We separate the main log from the web-access log
        log_format = config.logging.log_format or "standard"
        logger = self._create_logger(
            name=Constants.SERVICE_NAME, log_level=effective_log_level, logdir=args.logdir, log_format=log_format
        )
        Seedsync.logger = logger
        web_access_logger = self._create_logger(
            name=Constants.WEB_ACCESS_LOG_NAME, log_level=effective_log_level, logdir=args.logdir, log_format=log_format
        )
        logger.info(f"Log level: {effective_log_level}")

        # Create status
        status = Status()

        # Load or migrate path pairs config
        self.path_pairs_path = os.path.join(args.config_dir, Seedsync.__FILE_PATH_PAIRS)
        path_pairs_config = self._load_path_pairs_config(self.path_pairs_path, config)

        # Load or migrate integrations config (Sonarr/Radarr instances).
        # Migration uses the legacy [Integrations] section in settings.cfg, which
        # Config drops on next save.
        self.integrations_path = os.path.join(args.config_dir, Seedsync.__FILE_INTEGRATIONS)
        integrations_config = self._load_integrations_config(
            self.integrations_path, self.config_path, path_pairs_config
        )

        # Create context
        self.context = Context(
            logger=logger,
            web_access_logger=web_access_logger,
            config=config,
            args=ctx_args,
            status=status,
            path_pairs_config=path_pairs_config,
            integrations_config=integrations_config,
        )

        # Register the signal handlers
        signal.signal(signal.SIGTERM, self.signal)
        signal.signal(signal.SIGINT, self.signal)

        # Print context to log
        self.context.print_to_log()

        # Load the persists
        self.controller_persist_path = os.path.join(args.config_dir, Seedsync.__FILE_CONTROLLER_PERSIST)
        self.controller_persist = self._load_persist(ControllerPersist, self.controller_persist_path)

        self.auto_queue_persist_path = os.path.join(args.config_dir, Seedsync.__FILE_AUTO_QUEUE_PERSIST)
        self.auto_queue_persist = self._load_persist(AutoQueuePersist, self.auto_queue_persist_path)

    def run(self):
        self.context.logger.info("Starting SeedSync")
        self.context.logger.info(f"Platform: {platform.machine()}")

        # Create controller
        controller = Controller(self.context, self.controller_persist)

        # Create webhook notifier
        webhook_notifier = WebhookNotifier(self.context.config, self.context.logger)
        controller.add_model_listener(webhook_notifier)

        # Create arr notifier (Sonarr/Radarr integration)
        arr_notifier = ArrNotifier(
            self.context.integrations_config,
            self.context.path_pairs_config,
            self.context.logger,
        )
        controller.add_model_listener(arr_notifier)

        # Create auto queue
        auto_queue = AutoQueue(self.context, self.auto_queue_persist, controller)

        # Create web app
        web_app_builder = WebAppBuilder(self.context, controller, self.auto_queue_persist)
        web_app = web_app_builder.build()

        # Define child threads
        controller_job = ControllerJob(
            context=self.context.create_child_context(ControllerJob.__name__),
            controller=controller,
            auto_queue=auto_queue,
        )
        webapp_job = WebAppJob(context=self.context.create_child_context(WebAppJob.__name__), web_app=web_app)

        do_start_controller = True

        # Initial checks to see if we should bother starting the controller
        if Seedsync._detect_incomplete_config(self.context.config):
            if not self.context.args.exit:
                do_start_controller = False
                self.context.logger.error("Config is incomplete")
                self.context.status.server.up = False
                self.context.status.server.error_msg = Localization.Error.SETTINGS_INCOMPLETE
            else:
                raise AppError("Config is incomplete")

        # Start child threads here
        if do_start_controller:
            controller_job.start()
        webapp_job.start()

        try:
            prev_persist_timestamp = datetime.now()

            # Thread loop
            while True:
                # Persist to file occasionally
                now = datetime.now()
                if (now - prev_persist_timestamp).total_seconds() > Constants.MIN_PERSIST_TO_FILE_INTERVAL_IN_SECS:
                    prev_persist_timestamp = now
                    self.persist()

                # Propagate exceptions from child threads
                # Any exception here exits the main loop for clean shutdown
                webapp_job.propagate_exception()
                controller_job.propagate_exception()

                # Check if a restart is requested
                if web_app_builder.server_handler.is_restart_requested():
                    raise ServiceRestart()

                # Nothing else to do
                time.sleep(Constants.MAIN_THREAD_SLEEP_INTERVAL_IN_SECS)

        except Exception:
            self.context.logger.info("Exiting Seedsync")

            # This sleep is important to allow the jobs to finish setup before we terminate them
            # If we kill too early, the jobs may leave lingering threads around
            # Note: There might be a better way to ensure that job setup has completed, but this
            #       will do for now
            time.sleep(Constants.MAIN_THREAD_SLEEP_INTERVAL_IN_SECS)

            # Join all the threads here
            if do_start_controller:
                controller_job.terminate()
            webapp_job.terminate()

            # Wait for the threads to close
            if do_start_controller:
                controller_job.join()
            webapp_job.join()

            # Drain in-flight notifications
            webhook_notifier.shutdown()
            arr_notifier.shutdown()

            # Last persist
            self.persist()

            # Raise any exceptions so they can be logged properly
            # Note: ServiceRestart and ServiceExit will be caught and handled
            #       by outer code
            raise

    def persist(self):
        # Save the persists
        self.context.logger.debug("Persisting states to file")
        self.controller_persist.to_file(self.controller_persist_path)
        self.auto_queue_persist.to_file(self.auto_queue_persist_path)
        self.context.config.to_file(self.config_path)
        self.context.path_pairs_config.to_file(self.path_pairs_path)
        self.context.integrations_config.to_file(self.integrations_path)

    def signal(self, signum: int, _: FrameType | None) -> None:
        # noinspection PyUnresolvedReferences
        # Signals is a generated enum
        self.context.logger.info(f"Caught signal {signal.Signals(signum).name}")
        raise ServiceExit()

    @staticmethod
    def _parse_args(args: list[str]) -> argparse.Namespace:
        parser = argparse.ArgumentParser(description="Seedsync daemon")
        parser.add_argument("-c", "--config_dir", required=True, help="Path to config directory")
        parser.add_argument("--logdir", help="Directory for log files")
        parser.add_argument("-d", "--debug", action="store_true", help="Enable debug logs")
        parser.add_argument("--exit", action="store_true", help="Exit on error")

        # Whether package is frozen
        is_frozen = getattr(sys, "frozen", False)

        # Html path is only required if not running a frozen package
        # For a frozen package, set default to root/html
        # noinspection PyUnresolvedReferences
        # noinspection PyProtectedMember
        default_html_path = os.path.join(sys._MEIPASS, "html") if is_frozen else None  # type: ignore[attr-defined]
        parser.add_argument(
            "--html",
            required=not is_frozen,
            default=default_html_path,
            help="Path to directory containing html resources",
        )

        parser.add_argument("--scanfs", required=True, help="Path to scan_fs.py script")

        return parser.parse_args(args)

    @staticmethod
    def _create_logger(name: str, log_level: str, logdir: str | None, log_format: str = "standard") -> logging.Logger:
        logger = logging.getLogger(name)

        # Remove any existing handlers (needed when restarting)
        handlers = logger.handlers[:]
        for handler in handlers:
            handler.close()
            logger.removeHandler(handler)

        numeric_level = getattr(logging, log_level.upper(), logging.INFO)
        logger.setLevel(numeric_level)
        if logdir is not None:
            # Output logs to a file in the given directory
            handler = RotatingFileHandler(
                f"{logdir}/{name}.log",
                maxBytes=Constants.MAX_LOG_SIZE_IN_BYTES,
                backupCount=Constants.LOG_BACKUP_COUNT,
            )
        else:
            handler = logging.StreamHandler(sys.stdout)
        if log_format == "json":
            formatter = JsonFormatter()
        else:
            formatter = logging.Formatter(
                "%(asctime)s - %(levelname)s - %(name)s (%(processName)s/%(threadName)s) - %(message)s"
            )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        return logger

    @staticmethod
    def _create_default_config() -> Config:
        """
        Create a config with default values
        :return:
        """
        config = Config()

        config.general.log_level = "INFO"
        config.general.verbose = False

        config.lftp.remote_address = Seedsync.__CONFIG_DUMMY_VALUE
        config.lftp.remote_username = Seedsync.__CONFIG_DUMMY_VALUE
        config.lftp.remote_password = Seedsync.__CONFIG_DUMMY_VALUE
        config.lftp.remote_port = 22
        config.lftp.remote_path = Seedsync.__CONFIG_DUMMY_VALUE
        config.lftp.local_path = Seedsync.__CONFIG_DUMMY_VALUE
        config.lftp.remote_path_to_scan_script = "/tmp"
        config.lftp.use_ssh_key = False
        config.lftp.num_max_parallel_downloads = 2
        config.lftp.num_max_parallel_files_per_download = 3
        config.lftp.num_max_connections_per_root_file = 20
        config.lftp.num_max_connections_per_dir_file = 20
        config.lftp.num_max_total_connections = 0
        config.lftp.use_temp_file = False

        config.controller.interval_ms_remote_scan = 30000
        config.controller.interval_ms_local_scan = 10000
        config.controller.interval_ms_downloading_scan = 1000
        config.controller.extract_path = "/tmp"
        config.controller.use_local_path_as_extract_path = True
        config.controller.use_staging = False
        config.controller.staging_path = "/staging"

        config.web.port = 8800

        config.autoqueue.enabled = False
        config.autoqueue.patterns_only = False
        config.autoqueue.auto_extract = True
        config.autoqueue.auto_delete_remote = False

        config.logging.log_format = "standard"

        config.notifications.webhook_url = ""
        config.notifications.notify_on_download_complete = True
        config.notifications.notify_on_extraction_complete = True
        config.notifications.notify_on_extraction_failed = True
        config.notifications.notify_on_delete_complete = True

        config.lftp.net_limit_rate = ""
        config.lftp.net_socket_buffer = "8M"
        config.lftp.pget_min_chunk_size = "100M"
        config.lftp.mirror_parallel_directories = True
        config.lftp.net_timeout = 20
        config.lftp.net_max_retries = 2
        config.lftp.net_reconnect_interval_base = 3
        config.lftp.net_reconnect_interval_multiplier = 1

        return config

    @staticmethod
    def _backfill_config_defaults(config: Config) -> bool:
        """
        Fill in default values for any config properties that are None.
        Uses _create_default_config() as the single source of truth.
        Returns True if any properties were backfilled.
        """
        defaults = Seedsync._create_default_config()
        changed = False
        for section_attr in [
            "general",
            "lftp",
            "controller",
            "web",
            "autoqueue",
            "logging",
            "notifications",
            "validate",
        ]:
            section = getattr(config, section_attr)
            default_section = getattr(defaults, section_attr)
            for key in section.as_dict():
                if getattr(section, key) is None:
                    default_value = getattr(default_section, key)
                    if default_value is not None:
                        setattr(section, key, default_value)
                        changed = True
        return changed

    @staticmethod
    def _load_integrations_config(
        file_path: str, config_path: str, path_pairs_config: PathPairsConfig
    ) -> IntegrationsConfig:
        """Load integrations.json, falling back to migration from the legacy
        [Integrations] section in settings.cfg the first time we see it.

        On migration, every existing path pair has the new instance(s) attached
        so behavior is preserved.
        """
        if os.path.isfile(file_path):
            try:
                return IntegrationsConfig.from_file(file_path)
            except PersistError:
                if Seedsync.logger:
                    Seedsync.logger.exception("Failed to load integrations.json")
                Seedsync.__backup_file(file_path)

        ic = Seedsync.__migrate_legacy_integrations(config_path)
        if ic is None:
            return IntegrationsConfig()

        if ic.instances:
            instance_ids = [i.id for i in ic.instances]
            for pair in path_pairs_config.pairs:
                pair.arr_target_ids = list(instance_ids)
                path_pairs_config.update_pair(pair)
            if Seedsync.logger:
                Seedsync.logger.info(
                    "Migrated %d *arr instance(s) from settings.cfg; attached to %d path pair(s)",
                    len(ic.instances),
                    len(path_pairs_config.pairs),
                )

        ic.to_file(file_path)
        return ic

    @staticmethod
    def __migrate_legacy_integrations(config_path: str) -> IntegrationsConfig | None:
        """Read the [Integrations] section directly from settings.cfg (Config has
        dropped it) and build an IntegrationsConfig from the legacy fields.

        Returns None if no migration is needed.
        """
        if not os.path.isfile(config_path):
            return None
        parser = configparser.RawConfigParser()
        try:
            parser.read(config_path)
        except configparser.Error:
            return None
        if not parser.has_section("Integrations"):
            return None

        def _get_str(option: str) -> str:
            return parser.get("Integrations", option, fallback="").strip()

        def _get_bool(option: str) -> bool:
            try:
                return parser.getboolean("Integrations", option, fallback=False)
            except ValueError:
                return False

        return IntegrationsConfig.migrate_from_legacy(
            sonarr_url=_get_str("sonarr_url"),
            sonarr_api_key=_get_str("sonarr_api_key"),
            sonarr_enabled=_get_bool("sonarr_enabled"),
            radarr_url=_get_str("radarr_url"),
            radarr_api_key=_get_str("radarr_api_key"),
            radarr_enabled=_get_bool("radarr_enabled"),
        )

    @staticmethod
    def _load_path_pairs_config(file_path: str, config: Config) -> PathPairsConfig:
        if os.path.isfile(file_path):
            try:
                return PathPairsConfig.from_file(file_path)
            except PersistError:
                if Seedsync.logger:
                    Seedsync.logger.exception("Failed to load path_pairs.json")
                Seedsync.__backup_file(file_path)
        # Migrate from legacy single remote_path/local_path
        dummy = Seedsync.__CONFIG_DUMMY_VALUE
        remote_path = config.lftp.remote_path if config.lftp.remote_path != dummy else ""
        local_path = config.lftp.local_path if config.lftp.local_path != dummy else ""
        if remote_path and local_path:
            ppc = PathPairsConfig.migrate_from_legacy(remote_path, local_path)
            ppc.to_file(file_path)
            return ppc
        return PathPairsConfig()

    @staticmethod
    def _detect_incomplete_config(config: Config) -> bool:
        config_dict = config.as_dict()
        for sec_name in config_dict:
            for key in config_dict[sec_name]:
                if config_dict[sec_name][key] == Seedsync.__CONFIG_DUMMY_VALUE:
                    return True
        return False

    @staticmethod
    def _load_persist(persist_cls: type[T_Persist], file_path: str) -> T_Persist:
        """
        Loads a persist from file.
        Backs up existing persist if it's corrupted. Returns a new blank
        persist in its place.
        :param persist_cls:
        :param file_path:
        :return:
        """
        if os.path.isfile(file_path):
            try:
                return persist_cls.from_file(file_path)
            except PersistError:
                if Seedsync.logger:
                    Seedsync.logger.exception("Caught exception")

                # backup file
                Seedsync.__backup_file(file_path)

                # noinspection PyCallingNonCallable
                return persist_cls()
        else:
            # noinspection PyCallingNonCallable
            return persist_cls()

    @staticmethod
    def __backup_file(file_path: str):
        file_name = os.path.basename(file_path)
        file_dir = os.path.dirname(file_path)
        i = 1
        while True:
            backup_path = os.path.join(file_dir, f"{file_name}.{i}.bak")
            if not os.path.exists(backup_path):
                break
            i += 1
        if Seedsync.logger:
            Seedsync.logger.info(f"Backing up {file_path} to {backup_path}")
        shutil.copy(file_path, backup_path)


if __name__ == "__main__":
    multiprocessing.set_start_method("spawn")

    # Apply UMASK env var before spawning any child processes (e.g. lftp via pexpect).
    # The shell umask set in entrypoint.sh is not reliably inherited through the
    # setpriv exec chain in all container environments, so we set it explicitly here.
    # Note: regular files are created with base mode 0666, so umask 000 → 0666 (rw-rw-rw-).
    # Directories use base mode 0777, so umask 000 → 0777 (rwxrwxrwx).
    _umask_str = os.environ.get("UMASK", "").strip()
    if _umask_str:
        try:
            _prev_umask = os.umask(int(_umask_str, 8))
            print(f"Applied umask {_umask_str} (previous: {_prev_umask:04o})", file=sys.stderr)
        except ValueError:
            print(f"WARNING: Invalid UMASK value {_umask_str!r}, ignoring", file=sys.stderr)

    while True:
        try:
            seedsync = Seedsync()
            seedsync.run()
        except ServiceExit:
            break
        except ServiceRestart:
            if Seedsync.logger:
                Seedsync.logger.info("Restarting...")
            continue
        except Exception:
            if Seedsync.logger:
                Seedsync.logger.exception("Caught exception")
            raise

        if Seedsync.logger:
            Seedsync.logger.info("Exited successfully")
