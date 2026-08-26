# Copyright 2017, Inderpreet Singh, All rights reserved.

import unittest
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from unittest.mock import MagicMock

from common import Status, StatusComponent


@dataclass(eq=False)
class DummyStatusComponent(StatusComponent):
    a: Any = None
    b: Any = None


class TestStatusComponent(unittest.TestCase):
    def test_property_values(self):
        d = DummyStatusComponent()
        d.a = "hello"
        d.b = 33
        self.assertEqual("hello", d.a)
        self.assertEqual(33, d.b)

    def test_listeners(self):
        listener = MagicMock()
        d = DummyStatusComponent()
        d.add_listener(listener)
        d.a = "hello world"
        listener.assert_called_once_with("a")
        listener.reset_mock()
        d.b = 44
        listener.assert_called_once_with("b")

        # remove listener
        listener.reset_mock()
        d.remove_listener(listener)
        d.a = "bye world"
        listener.assert_not_called()
        d.b = 22
        listener.assert_not_called()

    def test_copy_values(self):
        d = DummyStatusComponent()
        d.a = "hello world"
        d.b = 55

        e = DummyStatusComponent()
        DummyStatusComponent.copy(d, e)
        self.assertEqual("hello world", e.a)
        self.assertEqual(55, e.b)

        # Modifying original doesn't touch copy
        d.a = "bye world"
        d.b = 66
        self.assertEqual("bye world", d.a)
        self.assertEqual(66, d.b)
        self.assertEqual("hello world", e.a)
        self.assertEqual(55, e.b)

        # Modifying copy doesn't touch original
        e.a = "copied world"
        e.b = 77
        self.assertEqual("bye world", d.a)
        self.assertEqual(66, d.b)
        self.assertEqual("copied world", e.a)
        self.assertEqual(77, e.b)

    def test_copy_doesnt_copy_listeners(self):
        d = DummyStatusComponent()
        d.a = "hello world"
        d.b = 55
        listener = MagicMock()
        d.add_listener(listener)

        e = DummyStatusComponent()
        DummyStatusComponent.copy(d, e)

        d.a = "bye world"
        listener.assert_called_once_with("a")
        listener.reset_mock()

        e.a = "copied world"
        listener.assert_not_called()


class TestStatus(unittest.TestCase):
    def test_property_values(self):
        status = Status()
        status.server.up = True
        status.server.error_msg = "Everything's good"
        self.assertEqual(True, status.server.up)
        self.assertEqual("Everything's good", status.server.error_msg)

    def test_listeners(self):
        listener = MagicMock()
        status = Status()
        status.add_listener(listener)
        status.server.up = False
        listener.assert_called_once_with()
        listener.reset_mock()
        status.server.error_msg = "Everything's good"
        listener.assert_called_once_with()

    def test_cannot_replace_component(self):
        status = Status()
        new_server = Status.ServerStatus()
        with self.assertRaises(ValueError) as e:
            status.server = new_server
        self.assertEqual("Cannot reassign component", str(e.exception))

    def test_default_values(self):
        status = Status()
        self.assertEqual(True, status.server.up)
        self.assertEqual(None, status.server.error_msg)
        self.assertEqual(None, status.controller.latest_local_scan_time)
        self.assertEqual(None, status.controller.latest_remote_scan_time)

    def test_components_registered(self):
        # Test that all components were registered
        # This is done through the copy method
        status = Status()

        status.server.up = False
        status.server.error_msg = "an error message"
        copy = status.copy()
        self.assertEqual(False, copy.server.up)
        self.assertEqual("an error message", copy.server.error_msg)

        time1 = datetime.now()
        time2 = datetime.now()
        status.controller.latest_local_scan_time = time1
        status.controller.latest_remote_scan_time = time2
        copy = status.copy()
        self.assertEqual(time1, copy.controller.latest_local_scan_time)
        self.assertEqual(time2, copy.controller.latest_remote_scan_time)

    def test_copy_values(self):
        status = Status()
        status.server.up = False
        status.server.error_msg = "Bad error"

        copy = status.copy()
        self.assertEqual(False, copy.server.up)
        self.assertEqual("Bad error", copy.server.error_msg)

        # Modifying original doesn't touch copy
        status.server.up = True
        status.server.error_msg = "No error"
        self.assertEqual(True, status.server.up)
        self.assertEqual("No error", status.server.error_msg)
        self.assertEqual(False, copy.server.up)
        self.assertEqual("Bad error", copy.server.error_msg)

        # Modifying copy doesn't touch original
        copy.server.up = False
        copy.server.error_msg = "Worse error"
        self.assertEqual(True, status.server.up)
        self.assertEqual("No error", status.server.error_msg)
        self.assertEqual(False, copy.server.up)
        self.assertEqual("Worse error", copy.server.error_msg)

    def test_copy_doesnt_copy_listeners(self):
        status = Status()
        listener = MagicMock()
        status.add_listener(listener)
        copy = status.copy()

        status.server.error_msg = "a"
        listener.assert_called_once_with()
        listener.reset_mock()

        copy.server.error_msg = "b"
        listener.assert_not_called()
