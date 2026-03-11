# Copyright 2017, Inderpreet Singh, All rights reserved.

import multiprocessing
import time
import unittest
import logging
import sys

from unittest.mock import MagicMock

from controller import IScanner, ScannerProcess, ScannerError
from system import SystemFile


class DummyScanner(IScanner):
    def scan(self):
        return []

    def set_base_logger(self, base_logger: logging.Logger):
        pass


class PicklableScanner(IScanner):
    """A picklable scanner that returns a fixed file list (survives spawn)."""
    def __init__(self, files=None):
        self._files = files if files is not None else []

    def scan(self):
        return list(self._files)

    def set_base_logger(self, base_logger: logging.Logger):
        pass


class FatalScanner(IScanner):
    """A picklable scanner that raises a non-recoverable ScannerError."""
    def scan(self):
        raise ScannerError("fatal-from-child", recoverable=False)

    def set_base_logger(self, base_logger: logging.Logger):
        pass


class TestScannerProcess(unittest.TestCase):
    """
    Tests for ScannerProcess logic.

    These tests call run_init()/run_loop() directly instead of spawning a
    subprocess, because unittest mocks do not survive the 'spawn' start
    method (child re-imports everything, bypassing the mock).
    """

    def setUp(self):
        logger = logging.getLogger()
        handler = logging.StreamHandler(sys.stdout)
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
        formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(name)s - %(message)s")
        handler.setFormatter(formatter)

    def test_retrieves_scan_results(self):
        a = SystemFile("a", 100, True)
        aa = SystemFile("aa", 60, False)
        a.add_child(aa)
        ab = SystemFile("ab", 40, False)
        a.add_child(ab)

        b = SystemFile("b", 10, True)
        ba = SystemFile("ba", 10, True)
        b.add_child(ba)
        baa = SystemFile("baa", 10, False)
        ba.add_child(baa)

        c = SystemFile("c", 1234, False)

        mock_scanner = DummyScanner()
        mock_scanner.scan = MagicMock()

        process = ScannerProcess(scanner=mock_scanner, interval_in_ms=0)
        process.run_init()

        # Scan #0: single file with children
        mock_scanner.scan.return_value = [a]
        process.run_loop()

        result = process.pop_latest_result()
        self.assertIsNotNone(result)
        self.assertEqual(1, len(result.files))
        self.assertEqual("a", result.files[0].name)
        self.assertEqual(True, result.files[0].is_dir)
        self.assertEqual(100, result.files[0].size)
        self.assertEqual(2, len(result.files[0].children))
        self.assertEqual("aa", result.files[0].children[0].name)
        self.assertEqual(False, result.files[0].children[0].is_dir)
        self.assertEqual(60, result.files[0].children[0].size)
        self.assertEqual("ab", result.files[0].children[1].name)
        self.assertEqual(False, result.files[0].children[1].is_dir)
        self.assertEqual(40, result.files[0].children[1].size)

        # Scan #1: two files with nested children
        mock_scanner.scan.return_value = [a, b]
        process.run_loop()

        result = process.pop_latest_result()
        self.assertIsNotNone(result)
        self.assertEqual(2, len(result.files))
        self.assertEqual("a", result.files[0].name)
        self.assertEqual("b", result.files[1].name)
        self.assertEqual(True, result.files[1].is_dir)
        self.assertEqual(10, result.files[1].size)
        self.assertEqual(1, len(result.files[1].children))
        self.assertEqual("ba", result.files[1].children[0].name)
        self.assertEqual(True, result.files[1].children[0].is_dir)
        self.assertEqual(10, result.files[1].children[0].size)
        self.assertEqual(1, len(result.files[1].children[0].children))
        self.assertEqual("baa", result.files[1].children[0].children[0].name)
        self.assertEqual(False, result.files[1].children[0].children[0].is_dir)
        self.assertEqual(10, result.files[1].children[0].children[0].size)

        # Scan #2: single file
        mock_scanner.scan.return_value = [c]
        process.run_loop()

        result = process.pop_latest_result()
        self.assertIsNotNone(result)
        self.assertEqual(1, len(result.files))
        self.assertEqual("c", result.files[0].name)
        self.assertEqual(False, result.files[0].is_dir)
        self.assertEqual(1234, result.files[0].size)

        # Scan #3: empty
        mock_scanner.scan.return_value = []
        process.run_loop()

        result = process.pop_latest_result()
        self.assertIsNotNone(result)
        self.assertEqual(0, len(result.files))

    def test_sends_error_result_on_recoverable_error(self):
        mock_scanner = DummyScanner()
        mock_scanner.scan = MagicMock()
        mock_scanner.scan.side_effect = ScannerError("recoverable error", recoverable=True)

        process = ScannerProcess(scanner=mock_scanner, interval_in_ms=0)
        process.run_init()
        process.run_loop()


        result = process.pop_latest_result()
        self.assertIsNotNone(result)
        self.assertEqual(0, len(result.files))
        self.assertTrue(result.failed)
        self.assertEqual("recoverable error", result.error_message)

    def test_sends_fatal_exception_on_nonrecoverable_error(self):
        mock_scanner = DummyScanner()
        mock_scanner.scan = MagicMock()
        mock_scanner.scan.side_effect = ScannerError("non-recoverable error", recoverable=False)

        process = ScannerProcess(scanner=mock_scanner, interval_in_ms=0)
        process.run_init()

        with self.assertRaises(ScannerError) as ctx:
            process.run_loop()
        self.assertEqual("non-recoverable error", str(ctx.exception))


class TestScannerProcessSpawned(unittest.TestCase):
    """
    End-to-end tests that spawn a real child process via AppProcess.run
    to exercise log-queue wiring, exception-queue propagation, and loop cleanup.

    Uses picklable scanners (no MagicMock) so fixtures survive the spawn boundary.
    """

    def test_spawned_process_produces_scan_result(self):
        """Spawn a ScannerProcess, let it run one scan, then terminate and read the result."""
        files = [SystemFile("spawned.txt", 42, False)]
        scanner = PicklableScanner(files=files)
        process = ScannerProcess(scanner=scanner, interval_in_ms=50)

        log_queue = multiprocessing.Queue()
        process.set_mp_log_queue(log_queue, logging.DEBUG)

        process.start()
        # Give the child time to complete at least one scan loop
        time.sleep(0.3)
        process.terminate()
        process.join(timeout=5)

        result = process.pop_latest_result()
        self.assertIsNotNone(result)
        self.assertEqual(1, len(result.files))
        self.assertEqual("spawned.txt", result.files[0].name)

        # Verify logs were forwarded via the log queue
        log_messages = []
        import queue
        while True:
            try:
                log_messages.append(log_queue.get(block=False))
            except queue.Empty:
                break
        self.assertTrue(len(log_messages) > 0, "Expected log messages forwarded via log queue")

    def test_spawned_process_propagates_fatal_error(self):
        """Spawn a ScannerProcess with a fatal scanner and verify the exception propagates."""
        scanner = FatalScanner()
        process = ScannerProcess(scanner=scanner, interval_in_ms=0)

        log_queue = multiprocessing.Queue()
        process.set_mp_log_queue(log_queue, logging.DEBUG)

        process.start()
        process.join(timeout=5)

        with self.assertRaises(ScannerError) as ctx:
            process.propagate_exception()
        self.assertEqual("fatal-from-child", str(ctx.exception))
