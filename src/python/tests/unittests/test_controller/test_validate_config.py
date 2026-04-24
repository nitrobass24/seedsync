"""Unit tests for Controller._validate_config() startup validation."""

import logging
import unittest
from unittest.mock import MagicMock, patch

from common import Args, Config, Context, Status
from common.path_pairs_config import PathPairsConfig
from controller import Controller, ControllerPersist
from controller.controller import ControllerError
from controller.model_updater import ModelUpdater

# All required Lftp fields and their valid test values
_LFTP_REQUIRED = {
    "remote_address": "seedbox.example.com",
    "remote_username": "user",
    "remote_port": 22,
    "remote_path_to_scan_script": "/path/to/scanfs",
    "use_ssh_key": False,
    "use_temp_file": True,
    "num_max_parallel_downloads": 2,
    "num_max_parallel_files_per_download": 3,
    "num_max_connections_per_root_file": 4,
    "num_max_connections_per_dir_file": 4,
    "num_max_total_connections": 10,
}

# All required Controller fields and their valid test values
_CONTROLLER_REQUIRED = {
    "interval_ms_remote_scan": 30000,
    "interval_ms_local_scan": 30000,
    "interval_ms_downloading_scan": 2000,
}


def _make_config(skip_lftp=None, skip_controller=None, skip_general_verbose=False, skip_autoqueue=False):
    """Return a Config with required fields populated, optionally skipping some.

    Fields left at None are the ones we want to test as missing.
    Since the InnerConfig property system only allows setting None on the first
    call (before any value is set), we simply don't set values we want to remain None.
    """
    skip_lftp = skip_lftp or set()
    skip_controller = skip_controller or set()

    config = Config()

    # Lftp — always set password (not required but needed for use_ssh_key logic)
    config.lftp.remote_password = "pass"
    # Also set remote_path/local_path for backward-compat path (not validated by _validate_config)
    config.lftp.remote_path = "/remote"
    config.lftp.local_path = "/local"
    for field, value in _LFTP_REQUIRED.items():
        if field not in skip_lftp:
            setattr(config.lftp, field, value)

    # Controller
    for field, value in _CONTROLLER_REQUIRED.items():
        if field not in skip_controller:
            setattr(config.controller, field, value)
    if "use_local_path_as_extract_path" not in skip_controller:
        config.controller.use_local_path_as_extract_path = True

    # General
    if not skip_general_verbose:
        config.general.verbose = False

    # AutoQueue
    if not skip_autoqueue:
        config.autoqueue.auto_delete_remote = False

    return config


def _make_args(skip_scanfs=False):
    """Return Args with required fields populated."""
    args = Args()
    if not skip_scanfs:
        args.local_path_to_scanfs = "/path/to/scanfs"
    return args


def _make_context(config, args):
    """Build a Context suitable for Controller construction."""
    logger = logging.getLogger("test_validate_config")
    web_logger = logging.getLogger("test_validate_config.web")
    status = Status()
    path_pairs_config = PathPairsConfig()
    return Context(
        logger=logger,
        web_access_logger=web_logger,
        config=config,
        args=args,
        status=status,
        path_pairs_config=path_pairs_config,
    )


class TestValidateConfig(unittest.TestCase):
    """Tests for Controller._validate_config()."""

    @patch.object(Controller, "_build_pair_contexts", return_value=[])
    @patch.object(ModelUpdater, "sync_persist_to_all_builders")
    def test_valid_config_does_not_raise(self, _mock_sync, _mock_build):
        """A fully-populated config should not raise."""
        config = _make_config()
        args = _make_args()
        context = _make_context(config, args)
        persist = MagicMock(spec=ControllerPersist)
        # Should not raise
        Controller(context, persist)

    @patch.object(Controller, "_build_pair_contexts", return_value=[])
    @patch.object(ModelUpdater, "sync_persist_to_all_builders")
    def test_missing_single_lftp_field_raises(self, _mock_sync, _mock_build):
        """A single missing Lftp field should raise with that field name."""
        config = _make_config(skip_lftp={"remote_address"})
        args = _make_args()
        context = _make_context(config, args)
        persist = MagicMock(spec=ControllerPersist)
        with self.assertRaises(ControllerError) as cm:
            Controller(context, persist)
        self.assertIn("Lftp.remote_address", str(cm.exception))

    @patch.object(Controller, "_build_pair_contexts", return_value=[])
    @patch.object(ModelUpdater, "sync_persist_to_all_builders")
    def test_missing_multiple_fields_lists_all(self, _mock_sync, _mock_build):
        """Multiple missing fields should all appear in the error message."""
        config = _make_config(
            skip_lftp={"remote_address", "remote_port"},
            skip_controller={"interval_ms_remote_scan"},
            skip_general_verbose=True,
        )
        args = _make_args()
        context = _make_context(config, args)
        persist = MagicMock(spec=ControllerPersist)
        with self.assertRaises(ControllerError) as cm:
            Controller(context, persist)
        msg = str(cm.exception)
        self.assertIn("Lftp.remote_address", msg)
        self.assertIn("Lftp.remote_port", msg)
        self.assertIn("Controller.interval_ms_remote_scan", msg)
        self.assertIn("General.verbose", msg)

    @patch.object(Controller, "_build_pair_contexts", return_value=[])
    @patch.object(ModelUpdater, "sync_persist_to_all_builders")
    def test_missing_args_local_path_to_scanfs_raises(self, _mock_sync, _mock_build):
        """Missing Args.local_path_to_scanfs should raise."""
        config = _make_config()
        args = _make_args(skip_scanfs=True)
        context = _make_context(config, args)
        persist = MagicMock(spec=ControllerPersist)
        with self.assertRaises(ControllerError) as cm:
            Controller(context, persist)
        self.assertIn("Args.local_path_to_scanfs", str(cm.exception))

    @patch.object(Controller, "_build_pair_contexts", return_value=[])
    @patch.object(ModelUpdater, "sync_persist_to_all_builders")
    def test_missing_autoqueue_field_raises(self, _mock_sync, _mock_build):
        """Missing AutoQueue.auto_delete_remote should raise."""
        config = _make_config(skip_autoqueue=True)
        args = _make_args()
        context = _make_context(config, args)
        persist = MagicMock(spec=ControllerPersist)
        with self.assertRaises(ControllerError) as cm:
            Controller(context, persist)
        self.assertIn("AutoQueue.auto_delete_remote", str(cm.exception))

    @patch.object(Controller, "_build_pair_contexts", return_value=[])
    @patch.object(ModelUpdater, "sync_persist_to_all_builders")
    def test_missing_controller_field_raises(self, _mock_sync, _mock_build):
        """Missing Controller.interval_ms_local_scan should raise."""
        config = _make_config(skip_controller={"interval_ms_local_scan"})
        args = _make_args()
        context = _make_context(config, args)
        persist = MagicMock(spec=ControllerPersist)
        with self.assertRaises(ControllerError) as cm:
            Controller(context, persist)
        self.assertIn("Controller.interval_ms_local_scan", str(cm.exception))


class TestBackwardCompatValidation(unittest.TestCase):
    """Tests for backward-compat path pair validation in _build_pair_contexts."""

    @patch.object(Controller, "_validate_config")
    @patch.object(ModelUpdater, "sync_persist_to_all_builders")
    def test_backward_compat_missing_remote_path_raises(self, _mock_sync, _mock_validate):
        """When no path pairs exist and remote_path is None, should raise."""
        # remote_path defaults to None in Config.Lftp.__init__
        config2 = Config()
        config2.lftp.remote_password = "pass"
        # Set all the required fields that _validate_config would check (but it's mocked)
        # remote_path is left as None (default)
        config2.lftp.local_path = "/local"
        args = _make_args()
        context = _make_context(config2, args)
        persist = MagicMock(spec=ControllerPersist)
        with self.assertRaises(ControllerError) as cm:
            Controller(context, persist)
        self.assertIn("remote_path", str(cm.exception))

    @patch.object(Controller, "_build_pair_contexts", return_value=[])
    @patch.object(ModelUpdater, "sync_persist_to_all_builders")
    def test_missing_extract_path_when_not_using_local(self, _mock_sync, _mock_build):
        """When use_local_path_as_extract_path is False and extract_path is None, should raise."""
        config = _make_config(skip_controller={"use_local_path_as_extract_path"})
        config.controller.use_local_path_as_extract_path = False
        # extract_path defaults to None
        args = _make_args()
        context = _make_context(config, args)
        persist = MagicMock(spec=ControllerPersist)
        with self.assertRaises(ControllerError) as cm:
            Controller(context, persist)
        self.assertIn("Controller.extract_path", str(cm.exception))

    @patch.object(Controller, "_validate_config")
    @patch.object(ModelUpdater, "sync_persist_to_all_builders")
    def test_backward_compat_missing_local_path_raises(self, _mock_sync, _mock_validate):
        """When no path pairs exist and local_path is None, should raise."""
        config = Config()
        config.lftp.remote_password = "pass"
        config.lftp.remote_path = "/remote"
        # local_path left as None (default)
        args = _make_args()
        context = _make_context(config, args)
        persist = MagicMock(spec=ControllerPersist)
        with self.assertRaises(ControllerError) as cm:
            Controller(context, persist)
        self.assertIn("local_path", str(cm.exception))
