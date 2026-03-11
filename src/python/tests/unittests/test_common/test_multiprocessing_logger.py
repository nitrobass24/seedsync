# Copyright 2017, Inderpreet Singh, All rights reserved.

import unittest
import logging
import sys
import time
import multiprocessing
from logging.handlers import QueueHandler

from testfixtures import LogCapture
import timeout_decorator

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

    @timeout_decorator.timeout(5)
    def test_main_logger_receives_records(self):
        mp_logger = MultiprocessingLogger(self.logger)
        p_1 = multiprocessing.Process(
            target=_child_process,
            args=(mp_logger.queue, mp_logger.log_level, "process_1"))

        with LogCapture("TestMultiprocessingLogger.MPLogger.process_1") as log_capture:
            p_1.start()
            mp_logger.start()
            p_1.join()
            # Brief wait for listener thread to drain remaining queue items
            time.sleep(0.2)
            mp_logger.stop()

            log_capture.check(
                ("process_1", "DEBUG", "Debug line"),
                ("process_1", "INFO", "Info line"),
                ("process_1", "WARNING", "Warning line"),
                ("process_1", "ERROR", "Error line")
            )

    @timeout_decorator.timeout(5)
    def test_children_names(self):
        mp_logger = MultiprocessingLogger(self.logger)
        p_1 = multiprocessing.Process(
            target=_child_process_with_children,
            args=(mp_logger.queue, mp_logger.log_level, "process_1"))

        with LogCapture("TestMultiprocessingLogger.MPLogger.process_1") as log_capture:
            p_1.start()
            mp_logger.start()
            p_1.join()
            time.sleep(0.5)
            mp_logger.stop()

            log_capture.check(
                ("process_1", "DEBUG", "Debug line"),
                ("process_1.child_1", "DEBUG", "Debug line"),
                ("process_1.child_1_1", "DEBUG", "Debug line"),
            )

    @timeout_decorator.timeout(5)
    def test_logger_levels(self):
        # Debug level
        self.logger.setLevel(logging.DEBUG)
        with LogCapture("TestMultiprocessingLogger.MPLogger.process_1") as log_capture:
            mp_logger = MultiprocessingLogger(self.logger)
            p_1 = multiprocessing.Process(
                target=_child_process,
                args=(mp_logger.queue, mp_logger.log_level, "process_1"))
            p_1.start()
            mp_logger.start()
            p_1.join()
            time.sleep(0.5)
            mp_logger.stop()

            log_capture.check(
                ("process_1", "DEBUG", "Debug line"),
                ("process_1", "INFO", "Info line"),
                ("process_1", "WARNING", "Warning line"),
                ("process_1", "ERROR", "Error line")
            )

        # Info level
        self.logger.setLevel(logging.INFO)
        with LogCapture("TestMultiprocessingLogger.MPLogger.process_1") as log_capture:
            mp_logger = MultiprocessingLogger(self.logger)
            p_1 = multiprocessing.Process(
                target=_child_process,
                args=(mp_logger.queue, mp_logger.log_level, "process_1"))
            p_1.start()
            mp_logger.start()
            p_1.join()
            time.sleep(0.5)
            mp_logger.stop()

            log_capture.check(
                ("process_1", "INFO", "Info line"),
                ("process_1", "WARNING", "Warning line"),
                ("process_1", "ERROR", "Error line")
            )

        # Warning level
        self.logger.setLevel(logging.WARNING)
        with LogCapture("TestMultiprocessingLogger.MPLogger.process_1") as log_capture:
            mp_logger = MultiprocessingLogger(self.logger)
            p_1 = multiprocessing.Process(
                target=_child_process,
                args=(mp_logger.queue, mp_logger.log_level, "process_1"))
            p_1.start()
            mp_logger.start()
            p_1.join()
            time.sleep(0.5)
            mp_logger.stop()

            log_capture.check(
                ("process_1", "WARNING", "Warning line"),
                ("process_1", "ERROR", "Error line")
            )

        # Error level
        self.logger.setLevel(logging.ERROR)
        with LogCapture("TestMultiprocessingLogger.MPLogger.process_1") as log_capture:
            mp_logger = MultiprocessingLogger(self.logger)
            p_1 = multiprocessing.Process(
                target=_child_process,
                args=(mp_logger.queue, mp_logger.log_level, "process_1"))
            p_1.start()
            mp_logger.start()
            p_1.join()
            time.sleep(0.5)
            mp_logger.stop()

            log_capture.check(
                ("process_1", "ERROR", "Error line")
            )
