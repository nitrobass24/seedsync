# Copyright 2017, Inderpreet Singh, All rights reserved.

"""Supervisor/holder for a recreatable extract/validate worker process.

A ``multiprocessing.Process`` cannot be restarted in place, yet the live
extract/validate worker is referenced from three collaborators that all read
its result queues: the :class:`~controller.controller.Controller` (owns and
starts it), the :class:`~controller.command_pipeline.CommandPipeline`
(dispatches work to it), and the :class:`~controller.model_updater.ModelUpdater`
(drains its ``pop_*`` queues).

A dead worker's queues are gone, so "recreating" it means constructing a brand
new :class:`~common.AppProcess` and re-pointing every reader at it. To avoid
re-wiring three separate fields, all three hold the *same* supervisor instance
instead of the raw worker. The supervisor delegates the worker's method surface
to whatever live instance it currently owns, so swapping in a fresh worker
re-wires every reader at once (#535, follow-up to #511).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any, Generic, Protocol, TypeVar, cast

from common import AppProcess

W = TypeVar("W", bound=AppProcess)


class _ResultReader(Protocol):
    """The result-queue drain surface shared by the Extract/Validate workers.

    These live on the concrete workers rather than the ``AppProcess`` base (the
    completed/failed result types differ between Extract and Validate), so the
    supervisor reaches them via a cast when draining a dead worker before its
    queues are closed (#571).
    """

    def pop_completed(self) -> list[Any]: ...

    def pop_failed(self) -> list[Any]: ...


class WorkerSupervisor(Generic[W]):
    """Owns the current live worker plus a factory that builds a fresh one.

    Delegates the worker method surface (``pop_*``/``propagate_exception``/
    ``name``/``is_alive``/``exitcode``/``set_mp_log_queue``/``start``/
    ``terminate``/``join``/``close_queues`` and the request-dispatch method) to
    the current instance, and can swap in a fresh worker via
    :meth:`recreate_if_dead` when the current one has died.
    """

    def __init__(self, factory: Callable[[], W], logger: logging.Logger, feature: str):
        """
        :param factory: zero-arg callable that builds a fresh worker instance.
        :param logger: logger used for recreation messages.
        :param feature: human-readable feature name (e.g. "Extract") for logs.
        """
        self._factory = factory
        self._logger = logger
        self._feature = feature
        self._worker: W = factory()
        # Captured on set_mp_log_queue() so a recreated worker can be re-wired
        # to the same cross-process logging queue before it is started.
        self._mp_log_queue: Any = None
        self._mp_log_level: int | None = None
        # Results drained from a dead worker during recreation, surfaced on the
        # next pop_completed()/pop_failed() so finished work emitted just before
        # a crash is not silently dropped when its queues close (#571).
        self._buffered_completed: list[Any] = []
        self._buffered_failed: list[Any] = []

    @property
    def worker(self) -> W:
        """The current live worker instance (for tests/diagnostics)."""
        return self._worker

    # --- delegated process attributes ---

    @property
    def name(self) -> str:
        return self._worker.name

    @property
    def exitcode(self) -> int | None:
        return self._worker.exitcode

    def is_alive(self) -> bool:
        return self._worker.is_alive()

    def set_mp_log_queue(self, log_queue: Any, log_level: int) -> None:
        # Remember the wiring so recreate_if_dead() can reapply it to the fresh
        # worker before starting it.
        self._mp_log_queue = log_queue
        self._mp_log_level = log_level
        self._worker.set_mp_log_queue(log_queue, log_level)

    def start(self) -> None:
        self._worker.start()

    def terminate(self) -> None:
        self._worker.terminate()

    def join(self, timeout: float | None = None) -> None:
        self._worker.join(timeout)

    def close_queues(self) -> None:
        self._worker.close_queues()

    def propagate_exception(self) -> None:
        self._worker.propagate_exception()

    def pop_completed(self) -> list[Any]:
        """Drain completed results, prepended with any buffered from a dead worker.

        Readers must go through the supervisor (not ``self.worker``) so results a
        worker emitted just before crashing — captured by :meth:`_drain_dead`
        during recreation — are surfaced exactly once, ahead of the fresh
        worker's own results (#571). ModelUpdater drains this in the same
        controller cycle as recreation, so the carry-over is picked up promptly.

        The live worker is read *before* the buffer is cleared so that a failure
        reading the live worker does not drop the carry-over: the buffer is left
        intact and surfaces on a later cycle instead of being lost.
        """
        fresh = cast(_ResultReader, self._worker).pop_completed()
        buffered = self._buffered_completed
        self._buffered_completed = []
        return buffered + fresh

    def pop_failed(self) -> list[Any]:
        """Drain failed results, prepended with any buffered from a dead worker (#571).

        See :meth:`pop_completed` for the carry-over contract, including the
        read-live-before-clearing-the-buffer ordering that keeps the carry-over
        from being lost if the live read fails.
        """
        fresh = cast(_ResultReader, self._worker).pop_failed()
        buffered = self._buffered_failed
        self._buffered_failed = []
        return buffered + fresh

    # --- delegated worker methods (dynamic) ---

    def __getattr__(self, item: str) -> Any:
        """Delegate the worker's own methods to the current live instance.

        Covers the display-only status reader (``pop_latest_statuses``) and the
        request-dispatch methods (``extract``/``validate``) — the worker surface
        that differs between ExtractProcess and ValidateProcess and so cannot be
        typed on a single ``Generic[W]`` supervisor. Callers that need the
        concrete status type read it through :attr:`worker` (e.g.
        ``supervisor.worker.pop_latest_statuses()``); ModelUpdater does this. The
        completed/failed readers are *not* dynamic — they are the explicit
        :meth:`pop_completed`/:meth:`pop_failed` above so they can carry over a
        dead worker's buffered results (#571), and ModelUpdater calls those
        through the supervisor rather than via :attr:`worker`.

        Only invoked for attributes not defined on the supervisor itself, so the
        explicit delegations above always win. ``_worker`` is set in
        ``__init__``; guard against the recursion that would occur if it is ever
        accessed before assignment.
        """
        if item == "_worker":
            raise AttributeError(item)
        return getattr(self._worker, item)

    # --- recreation ---

    def recreate_if_dead(self) -> bool:
        """Recreate the worker if it has died, re-wiring all readers via ``self``.

        Detects death via ``exitcode``/``is_alive()``: a not-yet-started worker
        (exitcode is None and never alive) is left alone, while an exited worker
        is replaced with a fresh instance built from the factory, re-wired to the
        shared mp-log queue, and started. Returns True iff a new worker was
        created.
        """
        if not self._is_dead():
            return False

        dead = self._worker
        self._logger.warning(
            "%s worker process %s has died (exitcode=%s); restarting it.",
            self._feature,
            dead.name,
            dead.exitcode,
        )

        fresh = self._factory()
        if self._mp_log_queue is not None and self._mp_log_level is not None:
            fresh.set_mp_log_queue(self._mp_log_queue, self._mp_log_level)
        fresh.start()
        # Swap before reaping the old worker so a failure releasing the dead
        # worker's queues still leaves the supervisor pointing at the live one.
        self._worker = fresh
        # Capture any finished results still in the dead worker's queues before
        # _reap_dead() closes them, so they are not silently dropped (#571). The
        # finally guarantees the dead worker's queues are still closed (FDs
        # freed) even in the unlikely event draining itself raises.
        try:
            self._drain_dead(dead)
        finally:
            self._reap_dead(dead)
        self._logger.info("%s worker process restarted as %s", self._feature, fresh.name)
        return True

    def _drain_dead(self, dead: W) -> None:
        """Buffer results the dead worker emitted before crashing (#571).

        Runs before :meth:`_reap_dead` closes the dead worker's queues. Each
        queue is drained in isolation and best-effort: a worker mid-crash may
        raise on a read, and a drain failure must never block the restart. The
        results are *extended* onto the buffers (not assigned) so repeated
        restarts before a consumer drain accumulate rather than clobber. They
        surface on the next :meth:`pop_completed`/:meth:`pop_failed`.
        """
        reader = cast(_ResultReader, dead)
        try:
            self._buffered_completed.extend(reader.pop_completed())
        except Exception:
            self._logger.debug("Error draining dead %s worker completions during restart", self._feature, exc_info=True)
        try:
            self._buffered_failed.extend(reader.pop_failed())
        except Exception:
            self._logger.debug("Error draining dead %s worker failures during restart", self._feature, exc_info=True)

    def _is_dead(self) -> bool:
        """True if the worker was started and has since exited."""
        try:
            alive = self._worker.is_alive()
        except (ValueError, AssertionError):
            # Already closed — treat as not-running but also not started here.
            return False
        if alive:
            return False
        # Not alive: distinguish "never started" (exitcode is None) from "exited".
        return self._worker.exitcode is not None

    def _reap_dead(self, dead: W) -> None:
        """Best-effort join + queue close on the replaced worker to free FDs."""
        try:
            dead.join(0)
        except Exception:
            self._logger.debug("Error joining dead %s worker during restart", self._feature, exc_info=True)
        try:
            dead.close_queues()
        except Exception:
            self._logger.debug("Error closing dead %s worker queues during restart", self._feature, exc_info=True)
