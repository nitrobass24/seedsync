# Copyright 2017, Inderpreet Singh, All rights reserved.

import logging
import multiprocessing
import sys
import threading
import time
import unittest
from logging.handlers import QueueHandler
from unittest.mock import patch

import timeout_decorator
from testfixtures import LogCapture

from common import MultiprocessingLogger


def _child_process(log_queue: multiprocessing.Queue, log_level: int, child_name: str):
    """Child process function that configures logging from a queue."""
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(QueueHandler(log_queue))
    root.setLevel(log_level)
    logger = root.getChild(child_name)
    logger.debug("Debug line")
    time.sleep(0.1)
    logger.info("Info line")
    time.sleep(0.1)
    logger.warning("Warning line")
    time.sleep(0.1)
    logger.error("Error line")


def _child_process_with_children(log_queue: multiprocessing.Queue, log_level: int, child_name: str):
    """Child process that creates child loggers."""
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(QueueHandler(log_queue))
    root.setLevel(log_level)
    logger = root.getChild(child_name)
    logger.debug("Debug line")
    logger.getChild("child_1").debug("Debug line")
    logger.getChild("child_1_1").debug("Debug line")


class TestMultiprocessingLogger(unittest.TestCase):
    def setUp(self):
        self.logger = logging.getLogger(TestMultiprocessingLogger.__name__)
        handler = logging.StreamHandler(sys.stdout)
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.DEBUG)
        formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(name)s - %(message)s")
        handler.setFormatter(formatter)

    # Must exceed the listener's 0.5s poll interval: the listener does not do a
    # final drain on shutdown, so stop() must come after at least one full poll
    # cycle or queued records are dropped.
    _DRAIN_SECS = 0.6

    def _run_child_logger(self, target=_child_process):
        """Run target in a child process wired to a fresh MultiprocessingLogger.

        Stops the logger even if the timeout-decorator exception fires
        mid-block — a leaked (non-daemon) listener thread hangs pytest at
        interpreter exit (#703).
        """
        mp_logger = MultiprocessingLogger(self.logger)
        mp_logger.start()
        try:
            p = multiprocessing.Process(target=target, args=(mp_logger.queue, mp_logger.log_level, "process_1"))
            p.start()
            p.join()
            # Wait for the listener thread to drain remaining queue items
            time.sleep(self._DRAIN_SECS)
        finally:
            mp_logger.stop()

    @timeout_decorator.timeout(10)
    def test_main_logger_receives_records(self):
        with LogCapture("TestMultiprocessingLogger.MPLogger.process_1") as log_capture:
            self._run_child_logger()

            log_capture.check(
                ("process_1", "DEBUG", "Debug line"),
                ("process_1", "INFO", "Info line"),
                ("process_1", "WARNING", "Warning line"),
                ("process_1", "ERROR", "Error line"),
            )

    @timeout_decorator.timeout(10)
    def test_children_names(self):
        with LogCapture("TestMultiprocessingLogger.MPLogger.process_1") as log_capture:
            self._run_child_logger(target=_child_process_with_children)

            log_capture.check(
                ("process_1", "DEBUG", "Debug line"),
                ("process_1.child_1", "DEBUG", "Debug line"),
                ("process_1.child_1_1", "DEBUG", "Debug line"),
            )

    @timeout_decorator.timeout(10)
    def test_listener_stopped_when_run_interrupted(self):
        # Regression for #703: an exception mid-run (e.g. the timeout decorator
        # firing under load) must not leak the non-daemon listener thread,
        # which would hang pytest at interpreter exit.
        real_sleep = time.sleep
        main_thread = threading.main_thread()

        def raise_in_main_thread(secs: float):
            # SIGALRM-driven timeouts only interrupt the main thread
            if threading.current_thread() is main_thread:
                raise RuntimeError("simulated timeout")
            real_sleep(secs)

        with patch("time.sleep", side_effect=raise_in_main_thread):
            with self.assertRaises(RuntimeError):
                self._run_child_logger()
        self.assertFalse(any(t.name == "MPLoggerListener" for t in threading.enumerate()))

    @timeout_decorator.timeout(20)
    def test_logger_levels(self):
        cases = [
            (logging.DEBUG, ["DEBUG", "INFO", "WARNING", "ERROR"]),
            (logging.INFO, ["INFO", "WARNING", "ERROR"]),
            (logging.WARNING, ["WARNING", "ERROR"]),
            (logging.ERROR, ["ERROR"]),
        ]
        lines = {"DEBUG": "Debug line", "INFO": "Info line", "WARNING": "Warning line", "ERROR": "Error line"}
        for level, expected_levels in cases:
            with self.subTest(level=logging.getLevelName(level)):
                self.logger.setLevel(level)
                with LogCapture("TestMultiprocessingLogger.MPLogger.process_1") as log_capture:
                    self._run_child_logger()

                    log_capture.check(*(("process_1", lvl, lines[lvl]) for lvl in expected_levels))
