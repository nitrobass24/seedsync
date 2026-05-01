# Copyright 2017, Inderpreet Singh, All rights reserved.

import unittest
from unittest.mock import MagicMock

from common import Args, Config, Constants, Context, Status
from controller.pair_context import (
    ControllerError,
    PairContext,
    configure_lftp,
    validate_config,
)


class TestPairContextInit(unittest.TestCase):
    """PairContext initializes with empty tracking state."""

    def test_tracking_state_initialized_empty(self):
        pc = PairContext(
            pair_id="test-id",
            name="test-pair",
            remote_path="/remote",
            local_path="/local",
            effective_local_path="/local",
            lftp=MagicMock(),
            active_scanner=MagicMock(),
            local_scanner=MagicMock(),
            remote_scanner=MagicMock(),
            active_scan_process=MagicMock(),
            local_scan_process=MagicMock(),
            remote_scan_process=MagicMock(),
            model_builder=MagicMock(),
        )
        self.assertEqual(pc.active_downloading_file_names, [])
        self.assertEqual(pc.active_extracting_file_names, [])
        self.assertEqual(pc.prev_downloading_file_names, set())
        self.assertEqual(pc.pending_completion, set())
        self.assertFalse(pc.remote_scan_received)
        self.assertFalse(pc.local_scan_received)
        self.assertIsNone(pc.latest_remote_scan)
        self.assertIsNone(pc.latest_local_scan)

    def test_stores_constructor_args(self):
        mock_lftp = MagicMock()
        pc = PairContext(
            pair_id="id-1",
            name="my-pair",
            remote_path="/r",
            local_path="/l",
            effective_local_path="/eff",
            lftp=mock_lftp,
            active_scanner=MagicMock(),
            local_scanner=MagicMock(),
            remote_scanner=MagicMock(),
            active_scan_process=MagicMock(),
            local_scan_process=MagicMock(),
            remote_scan_process=MagicMock(),
            model_builder=MagicMock(),
        )
        self.assertEqual(pc.pair_id, "id-1")
        self.assertEqual(pc.name, "my-pair")
        self.assertEqual(pc.remote_path, "/r")
        self.assertEqual(pc.local_path, "/l")
        self.assertEqual(pc.effective_local_path, "/eff")
        self.assertIs(pc.lftp, mock_lftp)


def _make_valid_context() -> Context:
    """Create a Context with all required fields populated."""
    config = Config()
    # Lftp required
    config.lftp.remote_address = "host"
    config.lftp.remote_username = "user"
    config.lftp.remote_port = 22
    config.lftp.remote_path_to_scan_script = "/scan"
    config.lftp.use_ssh_key = True
    config.lftp.use_temp_file = True
    config.lftp.num_max_parallel_downloads = 2
    config.lftp.num_max_parallel_files_per_download = 3
    config.lftp.num_max_connections_per_root_file = 4
    config.lftp.num_max_connections_per_dir_file = 5
    config.lftp.num_max_total_connections = 10
    # Controller required
    config.controller.interval_ms_remote_scan = 5000
    config.controller.interval_ms_local_scan = 3000
    config.controller.interval_ms_downloading_scan = 1000
    config.controller.use_local_path_as_extract_path = True
    # General
    config.general.verbose = True
    # AutoQueue
    config.autoqueue.auto_delete_remote = False

    args = Args()
    args.local_path_to_scanfs = "/scanfs"

    import logging

    logger = logging.getLogger("test")
    web_logger = logging.getLogger("test.web")
    status = Status()
    return Context(logger=logger, web_access_logger=web_logger, config=config, args=args, status=status)


class TestValidateConfig(unittest.TestCase):
    """Tests for validate_config."""

    def test_fully_populated_config_passes(self):
        ctx = _make_valid_context()
        # Should not raise
        validate_config(ctx)

    def test_missing_lftp_field_raises(self):
        ctx = _make_valid_context()
        # Bypass property checker by setting internal attribute directly
        setattr(ctx.config.lftp, "__remote_address", None)
        with self.assertRaises(ControllerError) as cm:
            validate_config(ctx)
        self.assertIn("Lftp.remote_address", str(cm.exception))

    def test_missing_multiple_fields_lists_all(self):
        ctx = _make_valid_context()
        setattr(ctx.config.lftp, "__remote_address", None)
        setattr(ctx.config.lftp, "__remote_port", None)
        setattr(ctx.config.controller, "__interval_ms_remote_scan", None)
        with self.assertRaises(ControllerError) as cm:
            validate_config(ctx)
        msg = str(cm.exception)
        self.assertIn("Lftp.remote_address", msg)
        self.assertIn("Lftp.remote_port", msg)
        self.assertIn("Controller.interval_ms_remote_scan", msg)

    def test_extract_path_required_when_not_using_local(self):
        ctx = _make_valid_context()
        ctx.config.controller.use_local_path_as_extract_path = False
        ctx.config.controller.extract_path = None
        with self.assertRaises(ControllerError) as cm:
            validate_config(ctx)
        self.assertIn("Controller.extract_path", str(cm.exception))

    def test_extract_path_not_required_when_using_local(self):
        ctx = _make_valid_context()
        ctx.config.controller.use_local_path_as_extract_path = True
        ctx.config.controller.extract_path = None
        # Should not raise
        validate_config(ctx)

    def test_missing_scanfs_arg_raises(self):
        ctx = _make_valid_context()
        ctx.args.local_path_to_scanfs = None
        with self.assertRaises(ControllerError) as cm:
            validate_config(ctx)
        self.assertIn("Args.local_path_to_scanfs", str(cm.exception))

    def test_missing_verbose_raises(self):
        ctx = _make_valid_context()
        ctx.config.general.verbose = None
        with self.assertRaises(ControllerError) as cm:
            validate_config(ctx)
        self.assertIn("General.verbose", str(cm.exception))

    def test_missing_auto_delete_remote_raises(self):
        ctx = _make_valid_context()
        ctx.config.autoqueue.auto_delete_remote = None
        with self.assertRaises(ControllerError) as cm:
            validate_config(ctx)
        self.assertIn("AutoQueue.auto_delete_remote", str(cm.exception))


class TestConfigureLftp(unittest.TestCase):
    """Tests for configure_lftp."""

    def test_mandatory_settings_applied(self):
        lftp = MagicMock()
        config = Config()
        config.lftp.num_max_parallel_downloads = 2
        config.lftp.num_max_parallel_files_per_download = 3
        config.lftp.num_max_connections_per_root_file = 4
        config.lftp.num_max_connections_per_dir_file = 5
        config.lftp.num_max_total_connections = 10
        config.lftp.use_temp_file = True

        configure_lftp(lftp, config)

        self.assertEqual(lftp.num_parallel_jobs, 2)
        self.assertEqual(lftp.num_parallel_files, 3)
        self.assertEqual(lftp.num_connections_per_root_file, 4)
        self.assertEqual(lftp.num_connections_per_dir_file, 5)
        self.assertEqual(lftp.num_max_total_connections, 10)
        self.assertTrue(lftp.use_temp_file)
        self.assertEqual(lftp.temp_file_name, "*" + Constants.LFTP_TEMP_FILE_SUFFIX)

    def test_optional_settings_applied_when_truthy(self):
        lftp = MagicMock()
        config = Config()
        config.lftp.num_max_parallel_downloads = 1
        config.lftp.num_max_parallel_files_per_download = 1
        config.lftp.num_max_connections_per_root_file = 1
        config.lftp.num_max_connections_per_dir_file = 1
        config.lftp.num_max_total_connections = 1
        config.lftp.use_temp_file = True
        config.lftp.net_limit_rate = "1M"
        config.lftp.net_socket_buffer = "65536"
        config.lftp.pget_min_chunk_size = "100k"

        configure_lftp(lftp, config)

        self.assertEqual(lftp.rate_limit, "1M")
        self.assertEqual(lftp.net_socket_buffer, "65536")
        self.assertEqual(lftp.min_chunk_size, "100k")

    def test_optional_settings_skipped_when_falsy(self):
        """Optional LFTP settings are not applied when their config values are falsy."""

        class TrackingMock:
            """Mock that tracks which attributes were set."""

            def __init__(self):
                self._set_attrs: list[str] = []

            def __setattr__(self, name, value):
                if not name.startswith("_"):
                    self._set_attrs.append(name)
                super().__setattr__(name, value)

        lftp = TrackingMock()
        config = Config()
        config.lftp.num_max_parallel_downloads = 1
        config.lftp.num_max_parallel_files_per_download = 1
        config.lftp.num_max_connections_per_root_file = 1
        config.lftp.num_max_connections_per_dir_file = 1
        config.lftp.num_max_total_connections = 1
        config.lftp.use_temp_file = True
        config.lftp.net_limit_rate = ""
        # net_socket_buffer and pget_min_chunk_size are None by default

        configure_lftp(lftp, config)

        self.assertNotIn("rate_limit", lftp._set_attrs)
        self.assertNotIn("net_socket_buffer", lftp._set_attrs)
        self.assertNotIn("min_chunk_size", lftp._set_attrs)

    def test_xfer_verify_enabled(self):
        lftp = MagicMock()
        config = Config()
        config.lftp.num_max_parallel_downloads = 1
        config.lftp.num_max_parallel_files_per_download = 1
        config.lftp.num_max_connections_per_root_file = 1
        config.lftp.num_max_connections_per_dir_file = 1
        config.lftp.num_max_total_connections = 1
        config.lftp.use_temp_file = True
        config.validate.xfer_verify = True
        config.validate.algorithm = "sha256"

        configure_lftp(lftp, config)

        self.assertTrue(lftp.xfer_verify)
        self.assertEqual(lftp.xfer_verify_command, "sha256sum")

    def test_xfer_verify_disabled(self):
        lftp = MagicMock()
        config = Config()
        config.lftp.num_max_parallel_downloads = 1
        config.lftp.num_max_parallel_files_per_download = 1
        config.lftp.num_max_connections_per_root_file = 1
        config.lftp.num_max_connections_per_dir_file = 1
        config.lftp.num_max_total_connections = 1
        config.lftp.use_temp_file = True
        config.validate.xfer_verify = False

        configure_lftp(lftp, config)

        self.assertFalse(lftp.xfer_verify)
