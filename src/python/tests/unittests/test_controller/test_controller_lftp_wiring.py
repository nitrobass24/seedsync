# Copyright 2017, Inderpreet Singh, All rights reserved.

"""Tests that Controller wires Lftp/RemoteScanner with the right transfer
protocol, port selection, and SSL params, while keeping the scanner on SSH."""

import logging
import unittest
from unittest.mock import MagicMock, patch

from common import Args, Config, Context, Status
from controller.controller import Controller


def _make_context(protocol: str, remote_port: int, remote_ftp_port: int | None, verify_cert: bool) -> Context:
    config = Config()
    config.lftp.remote_address = "host"
    config.lftp.remote_username = "user"
    config.lftp.remote_password = "secret"
    config.lftp.remote_port = remote_port
    config.lftp.remote_path_to_scan_script = "/scan"
    config.lftp.remote_python_path = ""
    config.lftp.use_ssh_key = False
    config.lftp.use_temp_file = False
    config.lftp.num_max_parallel_downloads = 2
    config.lftp.num_max_parallel_files_per_download = 3
    config.lftp.num_max_connections_per_root_file = 4
    config.lftp.num_max_connections_per_dir_file = 5
    config.lftp.num_max_total_connections = 0
    config.lftp.protocol = protocol
    config.lftp.remote_ftp_port = remote_ftp_port
    config.lftp.ftp_ssl_verify_certificate = verify_cert
    config.controller.interval_ms_remote_scan = 5000
    config.controller.interval_ms_local_scan = 3000
    config.controller.interval_ms_downloading_scan = 1000
    config.controller.use_local_path_as_extract_path = True
    config.controller.use_staging = False
    config.general.verbose = False
    config.autoqueue.auto_delete_remote = False

    args = Args()
    args.local_path_to_scanfs = "/scanfs"
    logger = logging.getLogger("test")
    return Context(
        logger=logger, web_access_logger=logging.getLogger("test.web"), config=config, args=args, status=Status()
    )


class TestControllerLftpWiring(unittest.TestCase):
    """Drives Controller._create_pair_context in isolation, patching the
    collaborators it constructs so we can inspect the kwargs passed to Lftp
    and RemoteScanner."""

    def _build_controller(self, context: Context) -> Controller:
        # Skip __init__ (which starts processes); seed only what
        # _create_pair_context reads via name-mangled attributes.
        controller = Controller.__new__(Controller)
        controller.logger = context.logger.getChild("Controller")
        controller._Controller__context = context
        controller._Controller__password = context.config.lftp.remote_password
        mp_logger = MagicMock()
        mp_logger.queue = MagicMock()
        mp_logger.log_level = logging.INFO
        controller._Controller__mp_logger = mp_logger
        return controller

    def _run(self, context: Context):
        controller = self._build_controller(context)
        with (
            patch("controller.controller.Lftp") as mock_lftp,
            patch("controller.controller.RemoteScanner") as mock_remote_scanner,
            patch("controller.controller.ActiveScanner"),
            patch("controller.controller.LocalScanner"),
            patch("controller.controller.ScannerProcess"),
            patch("controller.controller.ModelBuilder"),
            patch("controller.controller.configure_lftp"),
        ):
            controller._create_pair_context(pair_id="p1", name="pair", remote_path="/remote", local_path="/local")
        return mock_lftp, mock_remote_scanner

    def test_sftp_uses_remote_port_and_sftp_protocol(self):
        ctx = _make_context(protocol="sftp", remote_port=22, remote_ftp_port=21, verify_cert=False)
        mock_lftp, mock_remote_scanner = self._run(ctx)

        _, kwargs = mock_lftp.call_args
        self.assertEqual(kwargs["protocol"], "sftp")
        # Under sftp the transfer port is the SSH/SFTP control port
        self.assertEqual(kwargs["port"], 22)
        self.assertEqual(kwargs["remote_ftp_port"], 21)
        self.assertEqual(kwargs["ssl_verify_certificate"], False)
        self.assertEqual(kwargs["address"], "host")
        self.assertEqual(kwargs["user"], "user")

        # Scanner always uses the SSH remote_port, never the FTP port
        _, scanner_kwargs = mock_remote_scanner.call_args
        self.assertEqual(scanner_kwargs["remote_port"], 22)

    def test_ftps_uses_remote_ftp_port_and_ftps_protocol(self):
        ctx = _make_context(protocol="ftps", remote_port=22, remote_ftp_port=990, verify_cert=True)
        mock_lftp, mock_remote_scanner = self._run(ctx)

        _, kwargs = mock_lftp.call_args
        self.assertEqual(kwargs["protocol"], "ftps")
        # Under ftps the transfer port is the dedicated FTPS port
        self.assertEqual(kwargs["port"], 990)
        self.assertEqual(kwargs["remote_ftp_port"], 990)
        self.assertEqual(kwargs["ssl_verify_certificate"], True)

        # Scanner stays on SSH remote_port (22), not the FTP port (990)
        _, scanner_kwargs = mock_remote_scanner.call_args
        self.assertEqual(scanner_kwargs["remote_port"], 22)


if __name__ == "__main__":
    unittest.main()
