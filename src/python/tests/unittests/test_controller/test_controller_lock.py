# Copyright 2017, Inderpreet Singh, All rights reserved.

"""Tests for Controller's __model_lock exception-safety.

Regression test for https://github.com/nitrobass24/seedsync/issues/373

Previously the short model-lock regions used raw acquire()/release() pairs
with no try/finally.  An exception raised inside the locked body would leak
the lock forever and every subsequent caller would deadlock.  After
converting those regions to `with self.__model_lock:` blocks, the lock is
guaranteed to release on exception.
"""

import unittest
from threading import Lock
from unittest.mock import MagicMock

import timeout_decorator

from controller import Controller
from model import IModelListener


class _BoomError(Exception):
    """Custom exception used to prove the lock was released on raise."""


class TestControllerModelLockExceptionSafety(unittest.TestCase):
    """Verify that exceptions raised inside a model-lock region still
    release the lock (otherwise the next caller would deadlock).

    Each test wraps the "recovery" call in `timeout_decorator.timeout(5)` so
    that a regression (leaked lock -> deadlock) fails fast in CI rather than
    hanging the whole test suite.
    """

    def setUp(self):
        # Build a Controller instance without running __init__ — we only need
        # the private attributes the methods under test actually touch.
        self.controller = Controller.__new__(Controller)
        # Name-mangled private attributes:
        self.controller._Controller__model_lock = Lock()
        self.controller._Controller__model = MagicMock()

    @timeout_decorator.timeout(5)
    def test_get_model_files_releases_lock_on_exception(self):
        # Replace the private helper with one that raises on first call, then
        # returns normally.
        calls = {"n": 0}

        def flaky():
            calls["n"] += 1
            if calls["n"] == 1:
                raise _BoomError("boom")
            return []

        # Patch the name-mangled method.
        self.controller._Controller__get_model_files = flaky  # type: ignore[attr-defined]

        # First call raises — this is the scenario that previously leaked
        # the lock (acquire, raise, release never called).
        with self.assertRaises(_BoomError):
            self.controller.get_model_files()

        # Second call must complete.  Before the fix this deadlocked
        # forever because the lock was still held.
        result = self.controller.get_model_files()
        self.assertEqual(result, [])

        # Sanity: lock must currently be free.
        self.assertTrue(self.controller._Controller__model_lock.acquire(blocking=False))
        self.controller._Controller__model_lock.release()

    @timeout_decorator.timeout(5)
    def test_add_model_listener_releases_lock_on_exception(self):
        listener = MagicMock(spec=IModelListener)
        calls = {"n": 0}

        def flaky_add(_listener):
            calls["n"] += 1
            if calls["n"] == 1:
                raise _BoomError("boom")

        self.controller._Controller__model.add_listener.side_effect = flaky_add

        with self.assertRaises(_BoomError):
            self.controller.add_model_listener(listener)

        # Recovery call: must not deadlock.
        self.controller.add_model_listener(listener)

        self.assertTrue(self.controller._Controller__model_lock.acquire(blocking=False))
        self.controller._Controller__model_lock.release()

    @timeout_decorator.timeout(5)
    def test_remove_model_listener_releases_lock_on_exception(self):
        listener = MagicMock(spec=IModelListener)
        calls = {"n": 0}

        def flaky_remove(_listener):
            calls["n"] += 1
            if calls["n"] == 1:
                raise _BoomError("boom")

        self.controller._Controller__model.remove_listener.side_effect = flaky_remove

        with self.assertRaises(_BoomError):
            self.controller.remove_model_listener(listener)

        self.controller.remove_model_listener(listener)

        self.assertTrue(self.controller._Controller__model_lock.acquire(blocking=False))
        self.controller._Controller__model_lock.release()

    @timeout_decorator.timeout(5)
    def test_get_model_files_and_add_listener_releases_lock_on_exception(self):
        listener = MagicMock(spec=IModelListener)
        calls = {"n": 0}

        def flaky_add(_listener):
            calls["n"] += 1
            if calls["n"] == 1:
                raise _BoomError("boom")

        self.controller._Controller__model.add_listener.side_effect = flaky_add
        # __get_model_files must exist — provide a trivial stub.
        self.controller._Controller__get_model_files = lambda: []  # type: ignore[attr-defined]

        with self.assertRaises(_BoomError):
            self.controller.get_model_files_and_add_listener(listener)

        result = self.controller.get_model_files_and_add_listener(listener)
        self.assertEqual(result, [])

        self.assertTrue(self.controller._Controller__model_lock.acquire(blocking=False))
        self.controller._Controller__model_lock.release()


if __name__ == "__main__":
    unittest.main()
