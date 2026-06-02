# Copyright 2017, Inderpreet Singh, All rights reserved.

"""Tests for Controller.exit() teardown robustness.

Regression test for https://github.com/nitrobass24/seedsync/issues/508

When the lftp PTY is hung/dead (network or seedbox loss), `pc.lftp.exit()`
raises. Before the fix, that exception propagated out of `Controller.exit()`
and skipped every later teardown phase (worker terminate/join,
`__mp_logger.stop()`, and the `close_queues()` block), orphaning worker
subprocesses and leaking their multiprocessing.Queue file descriptors. On
repeated ServiceRestart this eventually exhausted the FD limit
(OSError: [Errno 24] No file descriptors available).

These tests build the Controller via `__new__` (no `__init__`) and inject the
name-mangled private attrs that `exit()` reads, using MagicMock children. They
verify that a hung lftp no longer aborts teardown and that all reaping/queue
cleanup still runs.
"""

import unittest
from unittest.mock import MagicMock

import timeout_decorator

from controller.controller import Controller


def _make_worker_process():
    """A worker AppProcess-like mock with terminate/join/close_queues."""
    proc = MagicMock()
    proc.terminate = MagicMock()
    proc.join = MagicMock()
    proc.close_queues = MagicMock()
    return proc


def _make_pair_context(pair_id):
    pc = MagicMock()
    pc.pair_id = pair_id
    pc.lftp = MagicMock()
    pc.lftp.exit = MagicMock()
    pc.active_scan_process = _make_worker_process()
    pc.local_scan_process = _make_worker_process()
    pc.remote_scan_process = _make_worker_process()
    pc.active_scanner = MagicMock()
    pc.active_scanner.close = MagicMock()
    return pc


def _make_command_wrapper():
    """Mirrors active_command_processes entries: wrapper.process is the proc."""
    wrapper = MagicMock()
    wrapper.process = _make_worker_process()
    return wrapper


class TestControllerExit(unittest.TestCase):
    def setUp(self):
        self.controller = Controller.__new__(Controller)
        self.controller.logger = MagicMock()
        self.controller._Controller__started = True

        self.pc1 = _make_pair_context("pair1")
        self.pc2 = _make_pair_context("pair2")
        self.controller._Controller__pair_contexts = [self.pc1, self.pc2]

        self.extract_process = _make_worker_process()
        self.validate_process = _make_worker_process()
        self.controller._Controller__extract_process = self.extract_process
        self.controller._Controller__validate_process = self.validate_process

        self.mp_logger = MagicMock()
        self.mp_logger.stop = MagicMock()
        self.controller._Controller__mp_logger = self.mp_logger

        self.command_wrapper = _make_command_wrapper()
        self.move_process = _make_worker_process()
        self.pipeline = MagicMock()
        self.pipeline.active_command_processes = [self.command_wrapper]
        self.pipeline.active_move_processes = [self.move_process]
        self.controller._Controller__pipeline = self.pipeline

    def _all_pair_processes(self):
        for pc in (self.pc1, self.pc2):
            yield pc.active_scan_process
            yield pc.local_scan_process
            yield pc.remote_scan_process

    def _assert_full_teardown(self):
        """Every worker was terminated, joined, and had its queues closed,
        the mp logger stopped, and pipeline process lists were cleared."""
        for proc in self._all_pair_processes():
            proc.terminate.assert_called_once()
            proc.join.assert_called_once()
            proc.close_queues.assert_called_once()
        for proc in (self.extract_process, self.validate_process):
            proc.terminate.assert_called_once()
            proc.join.assert_called_once()
            proc.close_queues.assert_called_once()
        for pc in (self.pc1, self.pc2):
            pc.active_scanner.close.assert_called_once()

        self.command_wrapper.process.terminate.assert_called_once()
        self.command_wrapper.process.join.assert_called_once()
        self.command_wrapper.process.close_queues.assert_called_once()
        self.move_process.terminate.assert_called_once()
        self.move_process.join.assert_called_once()
        self.move_process.close_queues.assert_called_once()

        self.mp_logger.stop.assert_called_once()
        self.assertEqual(self.pipeline.active_command_processes, [])
        self.assertEqual(self.pipeline.active_move_processes, [])

    @timeout_decorator.timeout(5)
    def test_exit_continues_teardown_when_lftp_exit_raises(self):
        """Core regression: a hung lftp must not abort teardown (AC #1/#2/#3)."""
        self.pc1.lftp.exit.side_effect = RuntimeError("hung PTY")

        # Must not raise.
        self.controller.exit()

        # The failure was logged (not silently swallowed).
        self.controller.logger.exception.assert_called()

        # All reaping and queue-cleanup phases still ran.
        self._assert_full_teardown()

        # Controller re-arms for a subsequent start().
        self.assertFalse(self.controller._Controller__started)

    @timeout_decorator.timeout(5)
    def test_exit_terminates_other_pairs_when_one_lftp_hangs(self):
        """One pair's lftp hanging must not skip the other pair's lftp.exit()
        or any pair's worker reaping (AC #4)."""
        self.pc1.lftp.exit.side_effect = RuntimeError("hung PTY")

        self.controller.exit()

        # Both pairs' lftp.exit() were attempted despite pair1 raising.
        self.pc1.lftp.exit.assert_called_once()
        self.pc2.lftp.exit.assert_called_once()

        # Both pairs' worker processes were terminated/joined/closed.
        for proc in self._all_pair_processes():
            proc.terminate.assert_called_once()
            proc.join.assert_called_once()
            proc.close_queues.assert_called_once()

    @timeout_decorator.timeout(5)
    def test_exit_happy_path_calls_all_phases(self):
        """No side effects: every phase runs and started flips to False."""
        self.controller.exit()

        self.pc1.lftp.exit.assert_called_once()
        self.pc2.lftp.exit.assert_called_once()
        self.controller.logger.exception.assert_not_called()
        self._assert_full_teardown()
        self.assertFalse(self.controller._Controller__started)

    @timeout_decorator.timeout(5)
    def test_exit_noop_when_not_started(self):
        """exit() while not started does no teardown and does not raise."""
        self.controller._Controller__started = False

        self.controller.exit()

        self.pc1.lftp.exit.assert_not_called()
        self.extract_process.terminate.assert_not_called()
        self.mp_logger.stop.assert_not_called()

    @timeout_decorator.timeout(5)
    def test_exit_closes_queues_when_worker_terminate_raises(self):
        """AC #2 (literal): a raise from a worker terminate()/join() — not just
        lftp — must not skip the remaining reaping or the FD-releasing
        close_queues phase, and must not propagate out of exit()."""
        self.extract_process.terminate.side_effect = ValueError("process already closed")
        self.move_process.join.side_effect = RuntimeError("join failed")

        # Must not raise despite the worker-phase failures.
        self.controller.exit()

        # The failures were logged, and every phase still ran for every worker
        # (close_queues in particular, so no FD leak).
        self.controller.logger.exception.assert_called()
        self._assert_full_teardown()
        self.assertFalse(self.controller._Controller__started)

    @timeout_decorator.timeout(5)
    def test_partial_start_failure_leaves_started_true_so_exit_cleans_up(self):
        """If start() fails partway, __started must be True so the job's cleanup
        path (exit()) tears down the children that did start, instead of
        early-returning on __started=False and leaking them (#537 review)."""
        self.controller._Controller__started = False
        # extract_process.start() raises after the pair scan processes started.
        self.extract_process.start.side_effect = RuntimeError("boom")

        with self.assertRaises(RuntimeError):
            self.controller.start()

        # Marked started despite the partial failure, so exit() proceeds.
        self.assertTrue(self.controller._Controller__started)
        self.controller.exit()
        for proc in self._all_pair_processes():
            proc.terminate.assert_called_once()
            proc.close_queues.assert_called_once()
        self.assertFalse(self.controller._Controller__started)

    @timeout_decorator.timeout(5)
    def test_repeated_exit_with_hung_lftp_does_not_leak(self):
        """Repeated ServiceRestart with a hung lftp must close queues every
        cycle and never raise (AC #3 / AC #6)."""
        self.pc1.lftp.exit.side_effect = RuntimeError("hung PTY")

        for cycle in range(2):
            # Re-arm and reset per-cycle worker mocks to count this cycle only.
            self.controller._Controller__started = True
            for proc in self._all_pair_processes():
                proc.reset_mock()
            for pc in (self.pc1, self.pc2):
                pc.active_scanner.close.reset_mock()
            for proc in (self.extract_process, self.validate_process):
                proc.reset_mock()
            self.command_wrapper.process.reset_mock()
            self.move_process.reset_mock()
            self.mp_logger.stop.reset_mock()
            self.pipeline.active_command_processes = [self.command_wrapper]
            self.pipeline.active_move_processes = [self.move_process]

            # Must not raise on any cycle.
            self.controller.exit()

            with self.subTest(cycle=cycle):
                self._assert_full_teardown()
                self.assertFalse(self.controller._Controller__started)


if __name__ == "__main__":
    unittest.main()
