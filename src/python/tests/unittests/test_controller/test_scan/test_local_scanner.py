# Copyright 2017, Inderpreet Singh, All rights reserved.

import logging
import unittest
from unittest.mock import patch

from controller.scan.local_scanner import LocalScanner
from controller.scan.scanner_process import ScannerError
from system import SystemFile, SystemScannerError


class TestLocalScanner(unittest.TestCase):
    """Tests for LocalScanner."""

    @patch("controller.scan.local_scanner.os.path.isdir", return_value=False)
    @patch("controller.scan.local_scanner.SystemScanner")
    def test_missing_path_returns_empty_with_warning(self, mock_scanner_cls, mock_isdir):
        """Missing scan path returns empty list + warning log."""
        scanner = LocalScanner("/nonexistent", use_temp_file=False)

        with self.assertLogs("LocalScanner", level="WARNING") as log_ctx:
            result = scanner.scan()

        self.assertEqual(result, [])
        self.assertTrue(any("does not exist" in msg for msg in log_ctx.output))

    @patch("controller.scan.local_scanner.os.path.isdir", return_value=True)
    @patch("controller.scan.local_scanner.SystemScanner")
    def test_successful_scan_returns_results(self, mock_scanner_cls, mock_isdir):
        """Successful scan returns SystemScanner results."""
        mock_scanner = mock_scanner_cls.return_value
        files = [SystemFile("a", 10, False), SystemFile("b", 20, True)]
        mock_scanner.scan.return_value = files

        scanner = LocalScanner("/exists", use_temp_file=False)
        result = scanner.scan()

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].name, "a")
        self.assertEqual(result[1].name, "b")

    @patch("controller.scan.local_scanner.os.path.isdir", return_value=True)
    @patch("controller.scan.local_scanner.SystemScanner")
    def test_scanner_error_raises_localized(self, mock_scanner_cls, mock_isdir):
        """SystemScannerError raises ScannerError with localized message."""
        mock_scanner = mock_scanner_cls.return_value
        mock_scanner.scan.side_effect = SystemScannerError("disk failure")

        scanner = LocalScanner("/exists", use_temp_file=False)

        with self.assertRaises(ScannerError):
            scanner.scan()

    @patch("controller.scan.local_scanner.SystemScanner")
    def test_set_base_logger(self, mock_scanner_cls):
        """set_base_logger creates a child logger."""
        scanner = LocalScanner("/local", use_temp_file=False)
        parent_logger = logging.getLogger("parent")
        scanner.set_base_logger(parent_logger)
        self.assertEqual(scanner.logger.name, "parent.LocalScanner")

    @patch("controller.scan.local_scanner.SystemScanner")
    def test_temp_file_suffix_set(self, mock_scanner_cls):
        """When use_temp_file is True, lftp temp suffix is set on SystemScanner."""
        mock_scanner = mock_scanner_cls.return_value
        LocalScanner("/local", use_temp_file=True)
        mock_scanner.set_lftp_temp_suffix.assert_called_once()
