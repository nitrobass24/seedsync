# Copyright 2017, Inderpreet Singh, All rights reserved.

import logging
import sys
import time
import unittest
from unittest.mock import patch

from controller.scan.active_scanner import ActiveScanner
from system import SystemFile, SystemScannerError


class TestActiveScanner(unittest.TestCase):
    """Tests for ActiveScanner."""

    def setUp(self):
        logger = logging.getLogger("test_active_scanner")
        handler = logging.StreamHandler(sys.stdout)
        logger.addHandler(handler)
        self.addCleanup(logger.removeHandler, handler)
        logger.setLevel(logging.DEBUG)

    @patch("controller.scan.active_scanner.SystemScanner")
    def test_empty_active_files_returns_empty(self, mock_scanner_cls):
        """With no active files set, scan returns empty."""
        scanner = ActiveScanner("/local")
        self.addCleanup(scanner.close)
        result = scanner.scan()
        self.assertEqual(result, [])

    @patch("controller.scan.active_scanner.SystemScanner")
    def test_scan_returns_files_after_set_active(self, mock_scanner_cls):
        """After set_active_files, scan returns SystemFile objects for those files."""
        mock_scanner = mock_scanner_cls.return_value
        file_a = SystemFile("fileA", 100, False)
        file_b = SystemFile("fileB", 200, True)
        mock_scanner.scan_single.side_effect = [file_a, file_b]

        scanner = ActiveScanner("/local")
        self.addCleanup(scanner.close)
        scanner.set_active_files(["fileA", "fileB"])
        # multiprocessing.Queue.put() uses a background thread; brief pause
        # ensures the data is available for the non-blocking get() in scan()
        time.sleep(0.05)
        result = scanner.scan()

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].name, "fileA")
        self.assertEqual(result[1].name, "fileB")

    @patch("controller.scan.active_scanner.SystemScanner")
    def test_latest_list_wins_when_multiple_set_before_scan(self, mock_scanner_cls):
        """Multiple set_active_files before scan: latest list wins (queue draining)."""
        mock_scanner = mock_scanner_cls.return_value
        file_c = SystemFile("fileC", 300, False)
        mock_scanner.scan_single.return_value = file_c

        scanner = ActiveScanner("/local")
        self.addCleanup(scanner.close)
        scanner.set_active_files(["fileA", "fileB"])
        scanner.set_active_files(["fileC"])
        time.sleep(0.05)
        result = scanner.scan()

        # Only the latest list should be used
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].name, "fileC")

    @patch("controller.scan.active_scanner.SystemScanner")
    def test_missing_file_logged_at_debug(self, mock_scanner_cls):
        """Missing file during download logged at DEBUG, not ERROR."""
        mock_scanner = mock_scanner_cls.return_value
        mock_scanner.scan_single.side_effect = SystemScannerError("file does not exist: /local/missing")

        scanner = ActiveScanner("/local")
        self.addCleanup(scanner.close)
        scanner.set_active_files(["missing"])
        time.sleep(0.05)

        with self.assertLogs("ActiveScanner", level="DEBUG") as log_ctx:
            result = scanner.scan()

        self.assertEqual(result, [])
        # Enforce the DEBUG level explicitly — assertLogs(level="DEBUG") only
        # captures records >= DEBUG, so a higher-level log would also satisfy
        # a plain message-text check. log_ctx.output entries are formatted
        # "LEVEL:logger:message", so the DEBUG: prefix pins the level.
        self.assertTrue(any(o.startswith("DEBUG:ActiveScanner:") and "does not exist" in o for o in log_ctx.output))

    @patch("controller.scan.active_scanner.SystemScanner")
    def test_unexpected_error_logged_at_warning(self, mock_scanner_cls):
        """Unexpected SystemScannerError logged at WARNING."""
        mock_scanner = mock_scanner_cls.return_value
        mock_scanner.scan_single.side_effect = SystemScannerError("permission denied")

        scanner = ActiveScanner("/local")
        self.addCleanup(scanner.close)
        scanner.set_active_files(["restricted"])
        time.sleep(0.05)

        with self.assertLogs("ActiveScanner", level="WARNING") as log_ctx:
            result = scanner.scan()

        self.assertEqual(result, [])
        # Pin the level explicitly via the "WARNING:ActiveScanner:" prefix —
        # mirrors the DEBUG-level check in test_missing_file_logged_at_debug.
        self.assertTrue(
            any(o.startswith("WARNING:ActiveScanner:") and "Unexpected scan error" in o for o in log_ctx.output)
        )

    @patch("controller.scan.active_scanner.SystemScanner")
    def test_set_base_logger(self, mock_scanner_cls):
        """set_base_logger creates a child logger."""
        scanner = ActiveScanner("/local")
        self.addCleanup(scanner.close)
        parent_logger = logging.getLogger("parent")
        scanner.set_base_logger(parent_logger)
        self.assertEqual(scanner.logger.name, "parent.ActiveScanner")

    @patch("controller.scan.active_scanner.SystemScanner")
    def test_lftp_temp_suffix_forwarded(self, mock_scanner_cls):
        """lftp_temp_suffix is forwarded to SystemScanner."""
        mock_scanner = mock_scanner_cls.return_value
        scanner = ActiveScanner("/local", lftp_temp_suffix=".partial")
        self.addCleanup(scanner.close)
        mock_scanner.set_lftp_temp_suffix.assert_called_once_with(".partial")
