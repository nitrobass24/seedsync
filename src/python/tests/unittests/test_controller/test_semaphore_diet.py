# Copyright 2017, Inderpreet Singh, All rights reserved.

import logging
import multiprocessing
import os
import shutil
import tempfile
import unittest

from controller import IScanner, ScannerProcess
from controller.move.move_process import MoveProcess


class TrivialScanner(IScanner):
    """Picklable no-op scanner (survives spawn)."""

    def scan(self):
        return []

    def set_base_logger(self, base_logger: logging.Logger):
        pass


class TestSemaphoreDiet(unittest.TestCase):
    """Regression test for #654: process primitives must not consume named
    POSIX semaphores.

    musl libc (Alpine) caps named semaphores at 256 per process
    (SEM_NSEMS_MAX); each mp.Lock costs one, so with ~240 held below, any
    process class still built on mp.Queue/mp.Event (3-5 sems each) blows the
    cap with OSError "No file descriptors available". Only meaningful on musl
    -- glibc/macOS have no such cap, so this is trivially green there; CI runs
    it in the Alpine test image.
    """

    def test_processes_start_with_240_semaphores_held(self):
        locks = [multiprocessing.Lock() for _ in range(240)]
        try:
            # ScannerProcess: construct + start + terminate + join + close
            scanner_process = ScannerProcess(scanner=TrivialScanner(), interval_in_ms=50)
            scanner_process.start()
            scanner_process.terminate()
            scanner_process.join(timeout=5)
            self.assertFalse(scanner_process.is_alive())
            scanner_process.close_queues()

            # MoveProcess (one-shot): construct + start + join + close
            src_dir = tempfile.mkdtemp()
            dst_dir = tempfile.mkdtemp()
            try:
                with open(os.path.join(src_dir, "test.txt"), "w") as f:
                    f.write("payload")
                move_process = MoveProcess(source_path=src_dir, dest_path=dst_dir, file_name="test.txt")
                move_process.start()
                move_process.join(timeout=5)
                self.assertFalse(move_process.is_alive())
                move_process.close_queues()
            finally:
                shutil.rmtree(src_dir, ignore_errors=True)
                shutil.rmtree(dst_dir, ignore_errors=True)
        finally:
            del locks
