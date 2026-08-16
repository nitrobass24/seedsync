# Copyright 2017, Inderpreet Singh, All rights reserved.

import unittest
from unittest.mock import MagicMock

from controller import commands
from controller.commands import MAX_CONCURRENT_COMMAND_PROCESSES, Command, CommandProcessWrapper
from controller.controller import Controller


class TestCommand(unittest.TestCase):
    def test_action_members_and_values(self):
        # The wire/dispatch contract depends on these exact members and values.
        self.assertEqual(0, Command.Action.QUEUE.value)
        self.assertEqual(1, Command.Action.STOP.value)
        self.assertEqual(2, Command.Action.EXTRACT.value)
        self.assertEqual(3, Command.Action.DELETE_LOCAL.value)
        self.assertEqual(4, Command.Action.DELETE_REMOTE.value)
        self.assertEqual(5, Command.Action.VALIDATE.value)
        self.assertEqual(6, Command.Action.CLEANUP_LOCAL.value)
        self.assertEqual(7, len(list(Command.Action)))

    def test_command_init_defaults(self):
        command = Command(Command.Action.QUEUE, "file.txt")
        self.assertEqual(Command.Action.QUEUE, command.action)
        self.assertEqual("file.txt", command.filename)
        self.assertIsNone(command.pair_id)
        self.assertEqual([], command.callbacks)

    def test_command_init_with_pair_id(self):
        command = Command(Command.Action.STOP, "file.txt", pair_id="abc")
        self.assertEqual("abc", command.pair_id)

    def test_add_callback_appends(self):
        command = Command(Command.Action.QUEUE, "file.txt")
        cb1 = MagicMock()
        cb2 = MagicMock()
        command.add_callback(cb1)
        command.add_callback(cb2)
        self.assertEqual([cb1, cb2], command.callbacks)

    def test_icallback_is_abstract(self):
        with self.assertRaises(TypeError):
            Command.ICallback()  # type: ignore[abstract]


class TestCommandProcessWrapper(unittest.TestCase):
    def test_stores_process_and_callback(self):
        process = MagicMock()
        post_callback = MagicMock()
        wrapper = CommandProcessWrapper(process=process, post_callback=post_callback)
        self.assertIs(process, wrapper.process)
        self.assertIs(post_callback, wrapper.post_callback)


class TestConcurrencyCap(unittest.TestCase):
    def test_max_concurrent_command_processes(self):
        self.assertEqual(8, MAX_CONCURRENT_COMMAND_PROCESSES)


class TestControllerReExportIdentity(unittest.TestCase):
    """Lock the re-export: Controller.* must be the SAME objects as commands.*.

    Every Controller.Command / .CommandProcessWrapper /
    .MAX_CONCURRENT_COMMAND_PROCESSES reference in tests, auto_queue.py, and the
    web handler resolves through these attributes — identity is the contract.
    """

    def test_controller_command_is_commands_command(self):
        self.assertIs(commands.Command, Controller.Command)

    def test_controller_process_wrapper_is_commands_wrapper(self):
        self.assertIs(commands.CommandProcessWrapper, Controller.CommandProcessWrapper)

    def test_controller_cap_matches(self):
        self.assertEqual(commands.MAX_CONCURRENT_COMMAND_PROCESSES, Controller.MAX_CONCURRENT_COMMAND_PROCESSES)

    def test_controller_action_is_commands_action(self):
        self.assertIs(commands.Command.Action, Controller.Command.Action)
