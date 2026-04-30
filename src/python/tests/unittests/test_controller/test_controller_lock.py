# Copyright 2017, Inderpreet Singh, All rights reserved.

"""Tests for ModelRegistry lock exception-safety.

Regression test for https://github.com/nitrobass24/seedsync/issues/373

The ModelRegistry owns the model lock. These tests verify that exceptions
raised inside locked methods still release the lock (otherwise the next
caller would deadlock).
"""

import unittest
from unittest.mock import MagicMock

import timeout_decorator

from controller.model_registry import ModelRegistry
from model import IModelListener, Model


class _BoomError(Exception):
    """Custom exception used to prove the lock was released on raise."""


class TestModelRegistryLockExceptionSafety(unittest.TestCase):
    """Verify that exceptions raised inside a model-lock region still
    release the lock (otherwise the next caller would deadlock).

    Each test wraps the "recovery" call in `timeout_decorator.timeout(5)` so
    that a regression (leaked lock -> deadlock) fails fast in CI rather than
    hanging the whole test suite.
    """

    def setUp(self):
        self.mock_model = MagicMock(spec=Model)
        self.mock_model.get_all_files.return_value = []
        self.registry = ModelRegistry(self.mock_model)

    @timeout_decorator.timeout(5)
    def test_get_files_releases_lock_on_exception(self):
        calls = {"n": 0}

        def flaky():
            calls["n"] += 1
            if calls["n"] == 1:
                raise _BoomError("boom")
            return []

        self.mock_model.get_all_files.side_effect = flaky

        with self.assertRaises(_BoomError):
            self.registry.get_files()

        # Recovery call: must not deadlock.
        result = self.registry.get_files()
        self.assertEqual(result, [])

        # Sanity: lock must currently be free.
        self.assertTrue(self.registry._lock.acquire(blocking=False))
        self.registry._lock.release()

    @timeout_decorator.timeout(5)
    def test_add_listener_releases_lock_on_exception(self):
        listener = MagicMock(spec=IModelListener)
        calls = {"n": 0}

        def flaky_add(_listener):
            calls["n"] += 1
            if calls["n"] == 1:
                raise _BoomError("boom")

        self.mock_model.add_listener.side_effect = flaky_add

        with self.assertRaises(_BoomError):
            self.registry.add_listener(listener)

        # Recovery call: must not deadlock.
        self.registry.add_listener(listener)

        self.assertTrue(self.registry._lock.acquire(blocking=False))
        self.registry._lock.release()

    @timeout_decorator.timeout(5)
    def test_remove_listener_releases_lock_on_exception(self):
        listener = MagicMock(spec=IModelListener)
        calls = {"n": 0}

        def flaky_remove(_listener):
            calls["n"] += 1
            if calls["n"] == 1:
                raise _BoomError("boom")

        self.mock_model.remove_listener.side_effect = flaky_remove

        with self.assertRaises(_BoomError):
            self.registry.remove_listener(listener)

        self.registry.remove_listener(listener)

        self.assertTrue(self.registry._lock.acquire(blocking=False))
        self.registry._lock.release()

    @timeout_decorator.timeout(5)
    def test_get_files_and_add_listener_releases_lock_on_exception(self):
        listener = MagicMock(spec=IModelListener)
        calls = {"n": 0}

        def flaky_add(_listener):
            calls["n"] += 1
            if calls["n"] == 1:
                raise _BoomError("boom")

        self.mock_model.add_listener.side_effect = flaky_add

        with self.assertRaises(_BoomError):
            self.registry.get_files_and_add_listener(listener)

        result = self.registry.get_files_and_add_listener(listener)
        self.assertEqual(result, [])

        self.assertTrue(self.registry._lock.acquire(blocking=False))
        self.registry._lock.release()


if __name__ == "__main__":
    unittest.main()
