# Copyright 2017, Inderpreet Singh, All rights reserved.

import unittest
import logging
import sys
from unittest.mock import patch, call, ANY
import tempfile
import os
import pickle
import shutil

from controller.scan import RemoteScanner, ScannerError
from ssh import SshcpError
from common import Localization


class TestRemoteScanner(unittest.TestCase):
    temp_dir = None
    temp_scan_script = None

    def setUp(self):
        ssh_patcher = patch('controller.scan.remote_scanner.Sshcp')
        self.addCleanup(ssh_patcher.stop)
        self.mock_ssh_cls = ssh_patcher.start()
        self.mock_ssh = self.mock_ssh_cls.return_value

        # Patch time.sleep so retry delays don't slow tests
        sleep_patcher = patch('controller.scan.remote_scanner.time.sleep')
        self.addCleanup(sleep_patcher.stop)
        self.mock_sleep = sleep_patcher.start()

        logger = logging.getLogger()
        handler = logging.StreamHandler(sys.stdout)
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
        formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(name)s - %(message)s")
        handler.setFormatter(formatter)

        # Ssh to return mangled binary by default
        self.mock_ssh.shell.return_value = b'error'

    @classmethod
    def setUpClass(cls):
        TestRemoteScanner.temp_dir = tempfile.mkdtemp(prefix="test_remote_scanner")
        TestRemoteScanner.temp_scan_script = os.path.join(TestRemoteScanner.temp_dir, "script")
        with open(TestRemoteScanner.temp_scan_script, "w") as f:
            f.write("")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(TestRemoteScanner.temp_dir)

    def _make_scanner(self, remote_path="/remote/path/to/scan",
                      remote_script_path="/remote/path/to/scan/script"):
        return RemoteScanner(
            remote_address="my remote address",
            remote_username="my remote user",
            remote_password="my password",
            remote_port=1234,
            remote_path_to_scan=remote_path,
            local_path_to_scan_script=TestRemoteScanner.temp_scan_script,
            remote_path_to_scan_script=remote_script_path
        )

    def _make_shell_side_effect(self, responses):
        """
        Create a shell side_effect from a list of responses.
        Each entry is either a bytes value to return, or an Exception to raise.
        The shell call sequence on first scan is:
          1. _log_remote_diagnostics()
          2. md5sum check
          3. scanfs (possibly retried)
        """
        self._shell_call_index = 0

        def ssh_shell(*args):
            idx = self._shell_call_index
            self._shell_call_index += 1
            if idx < len(responses):
                resp = responses[idx]
            else:
                resp = pickle.dumps([])
            if isinstance(resp, Exception):
                raise resp
            return resp

        return ssh_shell

    def test_correctly_initializes_ssh(self):
        self.ssh_args = {}

        def mock_ssh_ctor(**kwargs):
            self.ssh_args = kwargs

        self.mock_ssh_cls.side_effect = mock_ssh_ctor

        scanner = RemoteScanner(
            remote_address="my remote address",
            remote_username="my remote user",
            remote_password="my password",
            remote_port=1234,
            remote_path_to_scan="/remote/path/to/scan",
            local_path_to_scan_script=TestRemoteScanner.temp_scan_script,
            remote_path_to_scan_script="/remote/path/to/scan/script"
        )

        self.assertIsNotNone(scanner)
        self.assertEqual("my remote address", self.ssh_args["host"])
        self.assertEqual(1234, self.ssh_args["port"])
        self.assertEqual("my remote user", self.ssh_args["user"])
        self.assertEqual("my password", self.ssh_args["password"])

    def test_installs_scan_script_on_first_scan(self):
        scanner = self._make_scanner()

        # Call sequence: diagnostics, md5sum (non-matching), scanfs
        self.mock_ssh.shell.side_effect = self._make_shell_side_effect([
            b'',                # diagnostics
            b'',                # md5sum - doesn't match, triggers install
            pickle.dumps([]),   # scanfs
            pickle.dumps([]),   # second scan: scanfs (no install)
        ])

        scanner.scan()
        self.mock_ssh.copy.assert_called_once_with(
            local_path=TestRemoteScanner.temp_scan_script,
            remote_path="/remote/path/to/scan/script"
        )
        self.mock_ssh.copy.reset_mock()

        # should not be called the second time
        scanner.scan()
        self.mock_ssh.copy.assert_not_called()

    def test_copy_appends_scanfs_name_to_remote_path(self):
        scanner = self._make_scanner(remote_script_path="/remote/path/to/scan")

        self.mock_ssh.shell.side_effect = self._make_shell_side_effect([
            b'',                # diagnostics
            b'',                # md5sum - doesn't match
            pickle.dumps([]),   # scanfs
        ])

        scanner.scan()
        # check for appended path ('script')
        self.mock_ssh.copy.assert_called_once_with(
            local_path=TestRemoteScanner.temp_scan_script,
            remote_path="/remote/path/to/scan/script"
        )

    def test_calls_correct_ssh_md5sum_command(self):
        scanner = self._make_scanner()

        self.mock_ssh.shell.side_effect = self._make_shell_side_effect([
            b'',                # diagnostics
            b'',                # md5sum
            pickle.dumps([]),   # scanfs
        ])

        scanner.scan()
        # 3 calls: diagnostics, md5sum, scanfs
        self.assertEqual(3, self.mock_ssh.shell.call_count)
        # Second call should be the md5sum command
        md5sum_call = self.mock_ssh.shell.call_args_list[1]
        self.assertEqual(
            call("md5sum '/remote/path/to/scan/script' | awk '{print $1}' || echo"),
            md5sum_call
        )

    def test_skips_install_on_md5sum_match(self):
        scanner = self._make_scanner()

        # md5sum of empty file
        self.mock_ssh.shell.side_effect = self._make_shell_side_effect([
            b'',                                        # diagnostics
            b'd41d8cd98f00b204e9800998ecf8427e',        # md5sum - matches
            pickle.dumps([]),                           # scanfs
            pickle.dumps([]),                           # second scan: scanfs
        ])

        scanner.scan()
        self.mock_ssh.copy.assert_not_called()
        self.mock_ssh.copy.reset_mock()

        # should not be called the second time either
        scanner.scan()
        self.mock_ssh.copy.assert_not_called()

    def test_installs_scan_script_on_any_md5sum_output(self):
        scanner = self._make_scanner()

        self.mock_ssh.shell.side_effect = self._make_shell_side_effect([
            b'',                        # diagnostics
            b'some output from md5sum',  # md5sum - doesn't match
            pickle.dumps([]),           # scanfs
        ])

        scanner.scan()
        self.mock_ssh.copy.assert_called_once_with(
            local_path=TestRemoteScanner.temp_scan_script,
            remote_path="/remote/path/to/scan/script"
        )

    def test_raises_nonrecoverable_error_on_md5sum_error(self):
        scanner = self._make_scanner()

        self.mock_ssh.shell.side_effect = self._make_shell_side_effect([
            b'',                        # diagnostics
            SshcpError("an ssh error"), # md5sum fails
        ])

        with self.assertRaises(ScannerError) as ctx:
            scanner.scan()
        self.assertEqual(Localization.Error.REMOTE_SERVER_INSTALL.format("an ssh error"), str(ctx.exception))
        self.assertFalse(ctx.exception.recoverable)

    def test_calls_correct_ssh_scan_command(self):
        scanner = self._make_scanner()

        self.mock_ssh.shell.side_effect = self._make_shell_side_effect([
            b'',                # diagnostics
            b'',                # md5sum
            pickle.dumps([]),   # scanfs
        ])

        scanner.scan()
        # 3 calls: diagnostics, md5sum, scanfs
        self.assertEqual(3, self.mock_ssh.shell.call_count)
        self.mock_ssh.shell.assert_called_with(
            "'/remote/path/to/scan/script' '/remote/path/to/scan'"
        )

    def test_handles_tilde_path_for_shell_expansion(self):
        """Test that paths starting with ~ are converted to $HOME for shell expansion"""
        scanner = self._make_scanner(remote_path="~/data/torrents")

        self.mock_ssh.shell.side_effect = self._make_shell_side_effect([
            b'',                # diagnostics
            b'',                # md5sum
            pickle.dumps([]),   # scanfs
        ])

        scanner.scan()
        self.assertEqual(3, self.mock_ssh.shell.call_count)
        # When scan path has tilde, both paths use double quotes for consistent quoting
        # Tilde is converted to $HOME for shell expansion
        self.mock_ssh.shell.assert_called_with(
            "\"/remote/path/to/scan/script\" \"$HOME/data/torrents\""
        )

    def test_raises_nonrecoverable_error_on_first_failed_ssh(self):
        """Non-transient errors on first run are non-recoverable (no retry)"""
        scanner = self._make_scanner()

        self.mock_ssh.shell.side_effect = self._make_shell_side_effect([
            b'',                        # diagnostics
            b'',                        # md5sum
            SshcpError("an ssh error"), # scanfs fails (non-transient)
        ])

        with self.assertRaises(ScannerError) as ctx:
            scanner.scan()
        self.assertEqual(Localization.Error.REMOTE_SERVER_SCAN.format("an ssh error"), str(ctx.exception))
        self.assertFalse(ctx.exception.recoverable)

    def test_raises_recoverable_error_on_subsequent_failed_ssh(self):
        """After first successful scan, errors are recoverable (after retries exhausted)"""
        scanner = self._make_scanner()

        self.mock_ssh.shell.side_effect = self._make_shell_side_effect([
            b'',                        # diagnostics
            b'',                        # md5sum
            pickle.dumps([]),           # first scanfs - success
            # second scan: 3 retry attempts all fail
            SshcpError("an ssh error"),
            SshcpError("an ssh error"),
            SshcpError("an ssh error"),
        ])

        scanner.scan()  # no error first time
        with self.assertRaises(ScannerError) as ctx:
            scanner.scan()
        self.assertEqual(Localization.Error.REMOTE_SERVER_SCAN.format("an ssh error"), str(ctx.exception))
        self.assertTrue(ctx.exception.recoverable)

    def test_recovers_from_failed_ssh(self):
        """After retries exhausted and recoverable error, next scan can succeed"""
        scanner = self._make_scanner()

        self.mock_ssh.shell.side_effect = self._make_shell_side_effect([
            b'',                        # diagnostics
            b'',                        # md5sum
            pickle.dumps([]),           # first scanfs - success
            # second scan: 3 retry attempts all fail
            SshcpError("an ssh error"),
            SshcpError("an ssh error"),
            SshcpError("an ssh error"),
            # third scan: success
            pickle.dumps([]),
        ])

        scanner.scan()  # no error first time
        with self.assertRaises(ScannerError):
            scanner.scan()
        scanner.scan()  # recovers

    def test_raises_nonrecoverable_error_on_failed_copy(self):
        scanner = self._make_scanner()

        # noinspection PyUnusedLocal
        def ssh_copy(*args, **kwargs):
            raise SshcpError("an scp error")
        self.mock_ssh.copy.side_effect = ssh_copy

        with self.assertRaises(ScannerError) as ctx:
            scanner.scan()
        self.assertEqual(Localization.Error.REMOTE_SERVER_INSTALL.format("an scp error"), str(ctx.exception))
        self.assertFalse(ctx.exception.recoverable)

    def test_raises_nonrecoverable_error_on_mangled_output(self):
        scanner = self._make_scanner()

        def ssh_shell(*args):
            return "mangled data".encode()
        self.mock_ssh.shell.side_effect = ssh_shell

        with self.assertRaises(ScannerError) as ctx:
            scanner.scan()
        self.assertEqual(Localization.Error.REMOTE_SERVER_SCAN.format("Invalid pickled data"), str(ctx.exception))
        self.assertFalse(ctx.exception.recoverable)

    def test_raises_nonrecoverable_error_on_shell_detection_failure(self):
        scanner = self._make_scanner()

        self.mock_ssh.detect_shell.side_effect = SshcpError(
            "Remote user's login shell not found. "
            "Available shells on the remote server: /usr/bin/bash. "
            "Fix by running on the remote server: sudo chsh -s /usr/bin/bash testuser"
        )

        with self.assertRaises(ScannerError) as ctx:
            scanner.scan()
        self.assertIn("login shell not found", str(ctx.exception))
        self.assertFalse(ctx.exception.recoverable)

    def test_calls_detect_shell_on_first_scan(self):
        scanner = self._make_scanner()

        self.mock_ssh.shell.side_effect = self._make_shell_side_effect([
            b'',                # diagnostics
            b'',                # md5sum
            pickle.dumps([]),   # scanfs
            pickle.dumps([]),   # second scan: scanfs
        ])

        scanner.scan()
        self.mock_ssh.detect_shell.assert_called_once()

        # Second scan should not call detect_shell again
        self.mock_ssh.detect_shell.reset_mock()
        scanner.scan()
        self.mock_ssh.detect_shell.assert_not_called()

    def test_raises_nonrecoverable_error_on_failed_scan(self):
        """SystemScannerError is always non-recoverable, even with retries"""
        scanner = self._make_scanner()

        self.mock_ssh.shell.side_effect = self._make_shell_side_effect([
            b'',                                                    # diagnostics
            b'',                                                    # md5sum
            SshcpError("SystemScannerError: something failed"),    # scanfs - no retry
        ])

        with self.assertRaises(ScannerError) as ctx:
            scanner.scan()
        self.assertEqual(
            Localization.Error.REMOTE_SERVER_SCAN.format("SystemScannerError: something failed"),
            str(ctx.exception)
        )
        self.assertFalse(ctx.exception.recoverable)

    def test_retries_transient_errors_on_first_run(self):
        """Transient errors (timeouts) are retried even on first run"""
        scanner = self._make_scanner()

        self.mock_ssh.shell.side_effect = self._make_shell_side_effect([
            b'',                                # diagnostics
            b'',                                # md5sum
            SshcpError("Timed out after 180s"), # scanfs attempt 1 - transient
            pickle.dumps([]),                   # scanfs attempt 2 - success
        ])

        scanner.scan()  # should succeed after retry
        self.mock_sleep.assert_called_once()

    def test_retries_up_to_max_attempts(self):
        """After max retries exhausted, raises recoverable error"""
        scanner = self._make_scanner()

        self.mock_ssh.shell.side_effect = self._make_shell_side_effect([
            b'',                                # diagnostics
            b'',                                # md5sum
            SshcpError("Timed out after 180s"), # attempt 1
            SshcpError("Timed out after 180s"), # attempt 2
            SshcpError("Timed out after 180s"), # attempt 3
        ])

        with self.assertRaises(ScannerError) as ctx:
            scanner.scan()
        self.assertTrue(ctx.exception.recoverable)
        # Should have slept between attempts (max_retries - 1 times)
        self.assertEqual(2, self.mock_sleep.call_count)

    def test_no_retry_on_non_transient_first_run_error(self):
        """Non-transient errors on first run fail immediately without retry"""
        scanner = self._make_scanner()

        self.mock_ssh.shell.side_effect = self._make_shell_side_effect([
            b'',                                    # diagnostics
            b'',                                    # md5sum
            SshcpError("Incorrect password"),       # scanfs - non-transient
        ])

        with self.assertRaises(ScannerError) as ctx:
            scanner.scan()
        self.assertFalse(ctx.exception.recoverable)
        self.mock_sleep.assert_not_called()
