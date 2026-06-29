# Copyright 2017, Inderpreet Singh, All rights reserved.

"""Tests for WorkerSupervisor: recreating dead extract/validate workers (#535).

A ``multiprocessing.Process`` cannot be restarted in place. The supervisor holds
the current live worker plus a factory and, on detecting a dead worker, builds a
fresh one (set_mp_log_queue + start) and swaps it in. Because the Controller,
CommandPipeline, and ModelUpdater all hold the *same* supervisor, one swap
re-wires all three readers at once.

These tests use MagicMock workers and a fake factory: they assert a new instance
is created, that set_mp_log_queue + start are called on it, and that the three
readers (dispatch + the two pop_* drains) then see the fresh worker.
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from controller.command_pipeline import CommandPipeline
from controller.model_updater import ModelUpdater
from controller.worker_supervisor import WorkerSupervisor


def _make_worker(name="Worker", *, alive=True, exitcode=None):
    """A worker AppProcess-like mock with the full delegated surface."""
    worker = MagicMock()
    worker.name = name
    worker.is_alive.return_value = alive
    worker.exitcode = exitcode
    worker.pop_latest_statuses.return_value = None
    worker.pop_completed.return_value = []
    worker.pop_failed.return_value = []
    worker.propagate_exception.return_value = None
    return worker


class _FakeFactory:
    """A callable that hands out a queue of pre-built workers, recording calls."""

    def __init__(self, workers):
        self._workers = list(workers)
        self.created: list = []

    def __call__(self):
        worker = self._workers.pop(0)
        self.created.append(worker)
        return worker


class TestWorkerSupervisorRecreation(unittest.TestCase):
    def setUp(self):
        self.logger = MagicMock()
        # initial (will die) + replacement
        self.initial = _make_worker("Worker-1", alive=True, exitcode=None)
        self.replacement = _make_worker("Worker-2", alive=True, exitcode=None)
        self.factory = _FakeFactory([self.initial, self.replacement])
        self.sup: WorkerSupervisor = WorkerSupervisor(factory=self.factory, logger=self.logger, feature="Extract")

    def test_factory_builds_initial_worker(self):
        # The first factory call happens in __init__.
        self.assertIs(self.initial, self.sup.worker)
        self.assertEqual([self.initial], self.factory.created)

    def test_set_mp_log_queue_delegates_to_current_worker(self):
        self.sup.set_mp_log_queue("queue", 10)
        self.initial.set_mp_log_queue.assert_called_once_with("queue", 10)

    def test_delegates_start_terminate_join_close(self):
        self.sup.start()
        self.sup.terminate()
        self.sup.join(2)
        self.sup.close_queues()
        self.initial.start.assert_called_once()
        self.initial.terminate.assert_called_once()
        self.initial.join.assert_called_once_with(2)
        self.initial.close_queues.assert_called_once()

    def test_delegates_unknown_method_via_getattr(self):
        # extract()/validate() are forwarded through __getattr__.
        req = MagicMock()
        self.sup.extract(req)
        self.initial.extract.assert_called_once_with(req)

    def test_delegates_pop_readers(self):
        self.sup.pop_latest_statuses()
        self.sup.pop_completed()
        self.sup.pop_failed()
        self.initial.pop_latest_statuses.assert_called_once()
        self.initial.pop_completed.assert_called_once()
        self.initial.pop_failed.assert_called_once()

    def test_recreate_noop_when_alive(self):
        self.initial.is_alive.return_value = True
        created = self.sup.recreate_if_dead()
        self.assertFalse(created)
        self.assertIs(self.initial, self.sup.worker)
        self.assertEqual([self.initial], self.factory.created)

    def test_recreate_noop_when_never_started(self):
        # Not alive but exitcode is None => never started, leave it alone.
        self.initial.is_alive.return_value = False
        self.initial.exitcode = None
        created = self.sup.recreate_if_dead()
        self.assertFalse(created)
        self.assertIs(self.initial, self.sup.worker)

    def test_recreate_swaps_in_fresh_worker_with_logging_and_start(self):
        # Wire up logging so the supervisor reapplies it to the fresh worker.
        self.sup.set_mp_log_queue("log-queue", 20)
        # The worker exited (exitcode set, not alive).
        self.initial.is_alive.return_value = False
        self.initial.exitcode = 1

        created = self.sup.recreate_if_dead()

        self.assertTrue(created)
        # A NEW instance was built from the factory and swapped in.
        self.assertIs(self.replacement, self.sup.worker)
        self.assertEqual([self.initial, self.replacement], self.factory.created)
        # The fresh worker was re-wired to the shared mp-log queue and started.
        self.replacement.set_mp_log_queue.assert_called_once_with("log-queue", 20)
        self.replacement.start.assert_called_once()
        # The dead worker's queues were released to avoid FD leaks.
        self.initial.join.assert_called_once()
        self.initial.close_queues.assert_called_once()
        # Death logged at WARNING, restart confirmed at INFO.
        self.logger.warning.assert_called()
        self.logger.info.assert_called()

    def test_subsequent_dispatch_goes_to_fresh_worker(self):
        self.initial.is_alive.return_value = False
        self.initial.exitcode = 1
        self.sup.recreate_if_dead()

        # After recreation, dispatch + pop go to the fresh worker, not the dead one.
        req = MagicMock()
        self.sup.extract(req)
        self.sup.pop_completed()

        self.replacement.extract.assert_called_once_with(req)
        self.replacement.pop_completed.assert_called_once()
        self.initial.extract.assert_not_called()

    def test_recreate_drains_dead_worker_results_before_close(self):
        # #571: results the dead worker emitted just before crashing must be
        # surfaced through the supervisor, not silently dropped when its queues
        # are closed. Buffer them on the dead worker, kill it, recreate.
        c1, c2 = MagicMock(name="completed-1"), MagicMock(name="completed-2")
        f1 = MagicMock(name="failed-1")
        self.initial.pop_completed.return_value = [c1, c2]
        self.initial.pop_failed.return_value = [f1]
        self.initial.is_alive.return_value = False
        self.initial.exitcode = 1

        created = self.sup.recreate_if_dead()
        self.assertTrue(created)

        # The dead worker was drained before close_queues() closed its FDs.
        self.initial.close_queues.assert_called_once()
        # The buffered results are surfaced exactly once via the supervisor,
        # ahead of the (empty) fresh worker's results.
        self.assertEqual([c1, c2], self.sup.pop_completed())
        self.assertEqual([f1], self.sup.pop_failed())
        # And only once: a second drain yields just the fresh worker's results.
        self.assertEqual([], self.sup.pop_completed())
        self.assertEqual([], self.sup.pop_failed())

    def test_rapid_restarts_accumulate_buffered_results(self):
        # Two deaths before the consumer drains must accumulate, not clobber (#571).
        w1 = _make_worker("W-1", alive=False, exitcode=1)
        w1.pop_completed.return_value = ["a"]
        w2 = _make_worker("W-2", alive=False, exitcode=1)
        w2.pop_completed.return_value = ["b"]
        w3 = _make_worker("W-3", alive=True, exitcode=None)
        sup: WorkerSupervisor = WorkerSupervisor(
            factory=_FakeFactory([w1, w2, w3]), logger=self.logger, feature="Extract"
        )

        sup.recreate_if_dead()  # w1 dies -> buffer ["a"], swap to w2
        sup.recreate_if_dead()  # w2 dies -> buffer ["a", "b"], swap to w3

        self.assertIs(w3, sup.worker)
        self.assertEqual(["a", "b"], sup.pop_completed())

    def test_drain_failure_is_isolated_and_does_not_block_restart(self):
        # A worker mid-crash may raise on one queue read; the restart must still
        # happen and the other queue's results must still be surfaced (#571).
        self.initial.is_alive.return_value = False
        self.initial.exitcode = 1
        self.initial.pop_completed.side_effect = RuntimeError("queue broken")
        self.initial.pop_failed.return_value = ["f"]

        created = self.sup.recreate_if_dead()

        self.assertTrue(created)
        self.assertIs(self.replacement, self.sup.worker)
        self.initial.close_queues.assert_called_once()
        # The unreadable completed queue is skipped; the readable failed queue
        # is still surfaced.
        self.assertEqual([], self.sup.pop_completed())
        self.assertEqual(["f"], self.sup.pop_failed())

    def test_buffered_results_survive_a_failing_live_read(self):
        # #571: if reading the fresh worker raises (e.g. it too crashed and its
        # queue is closed), the carry-over buffer must NOT be cleared/lost — it
        # has to survive to a later cycle once a healthy worker can be read.
        self.initial.pop_completed.return_value = ["carried"]
        self.initial.is_alive.return_value = False
        self.initial.exitcode = 1
        self.sup.recreate_if_dead()  # buffers ["carried"], swaps to replacement

        # The fresh worker's own read blows up on the next drain.
        self.replacement.pop_completed.side_effect = ValueError("Queue is closed")
        with self.assertRaises(ValueError):
            self.sup.pop_completed()

        # Buffer was preserved despite the failed read; once the worker recovers,
        # the carried result is still surfaced exactly once.
        self.replacement.pop_completed.side_effect = None
        self.replacement.pop_completed.return_value = ["fresh"]
        self.assertEqual(["carried", "fresh"], self.sup.pop_completed())
        self.assertEqual(["fresh"], self.sup.pop_completed())

    def test_reap_runs_even_if_draining_raises(self):
        # Defense in depth: if draining the dead worker unexpectedly raises (e.g.
        # the logger itself fails inside _drain_dead), its queues must still be
        # closed so file descriptors are freed (#571).
        self.initial.is_alive.return_value = False
        self.initial.exitcode = 1
        self.initial.pop_completed.side_effect = RuntimeError("queue broken")
        self.logger.debug.side_effect = RuntimeError("logging down")

        with self.assertRaises(RuntimeError):
            self.sup.recreate_if_dead()

        self.initial.close_queues.assert_called_once()

    def test_recreate_survives_dead_worker_close_failure(self):
        # Releasing the dead worker's queues must not abort the swap.
        self.initial.is_alive.return_value = False
        self.initial.exitcode = 1
        self.initial.close_queues.side_effect = RuntimeError("already closed")

        created = self.sup.recreate_if_dead()

        self.assertTrue(created)
        self.assertIs(self.replacement, self.sup.worker)
        self.replacement.start.assert_called_once()


class TestSupervisorSharedByReaders(unittest.TestCase):
    """A single supervisor is shared by CommandPipeline + ModelUpdater so one
    swap re-wires both readers at once (the Controller holds the same ref)."""

    def _make_pipeline(self, supervisor, logger=None):
        return CommandPipeline(
            pair_contexts=[],
            registry=MagicMock(),
            persist=MagicMock(),
            context=MagicMock(),
            password=None,
            mp_logger=MagicMock(),
            extract_process=supervisor,
            validate_process=MagicMock(),
            logger=logger or MagicMock(),
            sync_persist_callback=MagicMock(),
        )

    def _make_updater(self, supervisor, pipeline):
        # Persist categories and the registry must be iterable for the prune
        # passes in update(); give them empty collections.
        persist = MagicMock()
        persist.downloaded_file_names = set()
        persist.extracted_file_names = set()
        persist.extract_failed_file_names = set()
        persist.validated_file_names = set()
        persist.corrupt_file_names = set()
        registry = MagicMock()
        registry.get_all_files.return_value = []
        # Validate worker pop_* must yield empty results so update() can iterate.
        validate = _make_worker("Validate", alive=True)
        return ModelUpdater(
            pair_contexts=[],
            persist=persist,
            pipeline=pipeline,
            registry=registry,
            extract_process=supervisor,
            validate_process=validate,
            context=MagicMock(),
            password=None,
            logger=MagicMock(),
            persist_sync=MagicMock(),
        )

    def test_pipeline_recreate_rewires_updater_reads(self):
        sup_logger = MagicMock()
        pipeline_logger = MagicMock()
        initial = _make_worker("Extract-1", alive=False, exitcode=2)
        replacement = _make_worker("Extract-2", alive=True, exitcode=None)
        factory = _FakeFactory([initial, replacement])
        supervisor: WorkerSupervisor = WorkerSupervisor(factory=factory, logger=sup_logger, feature="Extract")
        supervisor.set_mp_log_queue("q", 10)

        pipeline = self._make_pipeline(supervisor, logger=pipeline_logger)
        updater = self._make_updater(supervisor, pipeline)

        # The controller cycle: propagate_exceptions detects the dead worker,
        # reports it once at ERROR, then recreates it via the shared supervisor.
        pipeline.propagate_exceptions()

        # The fresh worker is live and is what the supervisor now delegates to.
        self.assertIs(replacement, supervisor.worker)
        replacement.start.assert_called_once()

        # A single ERROR-on-death was emitted (via the pipeline logger),
        # mentioning a restart (preserved from #511 while we now also recreate).
        error_messages = [c.args[0] % c.args[1:] for c in pipeline_logger.error.call_args_list]
        dead_reports = [m for m in error_messages if "has died" in m]
        self.assertEqual(1, len(dead_reports), error_messages)
        self.assertIn("restarted", dead_reports[0])
        # The supervisor logged the actual restart at WARNING/INFO.
        sup_logger.warning.assert_called()
        sup_logger.info.assert_called()

        # ModelUpdater.update() reads completed/failed through the shared
        # supervisor, so the swap re-wires it to the fresh worker; statuses are
        # read straight off the fresh worker.
        updater.update()
        replacement.pop_latest_statuses.assert_called()
        replacement.pop_completed.assert_called()
        replacement.pop_failed.assert_called()
        # The dead worker is drained exactly once during recreation (#571) so its
        # last-moment results are surfaced rather than dropped, and is not read
        # again by the updater afterward.
        initial.pop_completed.assert_called_once()
        initial.pop_failed.assert_called_once()

    def test_pipeline_dispatch_after_recreate_targets_fresh_worker(self):
        logger = MagicMock()
        initial = _make_worker("Extract-1", alive=False, exitcode=2)
        replacement = _make_worker("Extract-2", alive=True, exitcode=None)
        factory = _FakeFactory([initial, replacement])
        supervisor: WorkerSupervisor = WorkerSupervisor(factory=factory, logger=logger, feature="Extract")
        pipeline = self._make_pipeline(supervisor)
        pipeline.propagate_exceptions()

        # Dispatch an extract through the pipeline's private handler; it must go
        # to the fresh worker the supervisor swapped in.
        supervisor.extract(MagicMock())
        replacement.extract.assert_called_once()
        initial.extract.assert_not_called()


if __name__ == "__main__":
    unittest.main()
