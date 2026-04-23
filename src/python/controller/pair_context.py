# Copyright 2017, Inderpreet Singh, All rights reserved.

"""Per-pair context, config validation, and LFTP configuration.

Extracted from controller.py as part of the controller decomposition
(#394 Phase 1C).
"""

from __future__ import annotations

from common import AppError, Config, Constants, Context
from lftp import Lftp

from .model_builder import ModelBuilder
from .scan import ActiveScanner, LocalScanner, RemoteScanner, ScannerProcess, ScannerResult


class ControllerError(AppError):
    """
    Exception indicating a controller error
    """

    pass


class PairContext:
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


def validate_config(context: Context) -> None:
    """Validate that all required config fields are set (non-None) at startup.

    Collects all missing fields and raises a single ControllerError listing them.
    """
    missing: list[str] = []
    config = context.config

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
            missing.append(f"Lftp.{field}")

    # Controller required fields
    controller_fields = [
        "interval_ms_remote_scan",
        "interval_ms_local_scan",
        "interval_ms_downloading_scan",
    ]
    for field in controller_fields:
        if getattr(config.controller, field) is None:
            missing.append(f"Controller.{field}")

    # Extract path: when use_local_path_as_extract_path is False, extract_path must be set
    if config.controller.use_local_path_as_extract_path is None:
        missing.append("Controller.use_local_path_as_extract_path")
    elif not config.controller.use_local_path_as_extract_path and not config.controller.extract_path:
        missing.append("Controller.extract_path")

    # General required fields
    if config.general.verbose is None:
        missing.append("General.verbose")

    # AutoQueue required fields
    if config.autoqueue.auto_delete_remote is None:
        missing.append("AutoQueue.auto_delete_remote")

    # Args required fields
    if context.args.local_path_to_scanfs is None:
        missing.append("Args.local_path_to_scanfs")

    if missing:
        raise ControllerError(f"Required config fields are not set: {', '.join(missing)}")


def configure_lftp(lftp: Lftp, config: Config) -> None:
    """Apply shared LFTP configuration settings."""
    cfg = config.lftp
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
    validate_cfg = config.validate
    if validate_cfg.xfer_verify:
        lftp.xfer_verify = True
        lftp.xfer_verify_command = f"{validate_cfg.algorithm}sum"
    else:
        lftp.xfer_verify = False
