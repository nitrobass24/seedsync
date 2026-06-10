# Copyright 2017, Inderpreet Singh, All rights reserved.

from unittest.mock import MagicMock, patch
from urllib.parse import quote

import timeout_decorator

from controller import Controller
from tests.integration.test_web.test_web_app import BaseTestWebApp


class TestControllerHandler(BaseTestWebApp):
    def test_queue(self):
        def side_effect(cmd: Controller.Command):
            cmd.callbacks[0].on_success()

        self.controller.queue_command = MagicMock()
        self.controller.queue_command.side_effect = side_effect

        print(self.test_app.get("/server/command/queue/test1"))
        command = self.controller.queue_command.call_args[0][0]
        self.assertEqual(Controller.Command.Action.QUEUE, command.action)
        self.assertEqual("test1", command.filename)

        uri = quote(quote("value/with/slashes", safe=""), safe="")
        print(self.test_app.get("/server/command/queue/" + uri))
        command = self.controller.queue_command.call_args[0][0]
        self.assertEqual(Controller.Command.Action.QUEUE, command.action)
        self.assertEqual("value/with/slashes", command.filename)

        uri = quote(quote(" value with spaces", safe=""), safe="")
        print(self.test_app.get("/server/command/queue/" + uri))
        command = self.controller.queue_command.call_args[0][0]
        self.assertEqual(Controller.Command.Action.QUEUE, command.action)
        self.assertEqual(" value with spaces", command.filename)

        uri = quote(quote("value'with'singlequote", safe=""), safe="")
        print(self.test_app.get("/server/command/queue/" + uri))
        command = self.controller.queue_command.call_args[0][0]
        self.assertEqual(Controller.Command.Action.QUEUE, command.action)
        self.assertEqual("value'with'singlequote", command.filename)

        uri = quote(quote('value"with"doublequote', safe=""), safe="")
        print(self.test_app.get("/server/command/queue/" + uri))
        command = self.controller.queue_command.call_args[0][0]
        self.assertEqual(Controller.Command.Action.QUEUE, command.action)
        self.assertEqual('value"with"doublequote', command.filename)

    def test_stop(self):
        def side_effect(cmd: Controller.Command):
            cmd.callbacks[0].on_success()

        self.controller.queue_command = MagicMock()
        self.controller.queue_command.side_effect = side_effect

        print(self.test_app.get("/server/command/stop/test1"))
        command = self.controller.queue_command.call_args[0][0]
        self.assertEqual(Controller.Command.Action.STOP, command.action)
        self.assertEqual("test1", command.filename)

        uri = quote(quote("value/with/slashes", safe=""), safe="")
        print(self.test_app.get("/server/command/stop/" + uri))
        command = self.controller.queue_command.call_args[0][0]
        self.assertEqual(Controller.Command.Action.STOP, command.action)
        self.assertEqual("value/with/slashes", command.filename)

        uri = quote(quote(" value with spaces", safe=""), safe="")
        print(self.test_app.get("/server/command/stop/" + uri))
        command = self.controller.queue_command.call_args[0][0]
        self.assertEqual(Controller.Command.Action.STOP, command.action)
        self.assertEqual(" value with spaces", command.filename)

        uri = quote(quote("value'with'singlequote", safe=""), safe="")
        print(self.test_app.get("/server/command/stop/" + uri))
        command = self.controller.queue_command.call_args[0][0]
        self.assertEqual(Controller.Command.Action.STOP, command.action)
        self.assertEqual("value'with'singlequote", command.filename)

        uri = quote(quote('value"with"doublequote', safe=""), safe="")
        print(self.test_app.get("/server/command/stop/" + uri))
        command = self.controller.queue_command.call_args[0][0]
        self.assertEqual(Controller.Command.Action.STOP, command.action)
        self.assertEqual('value"with"doublequote', command.filename)

    def test_extract(self):
        def side_effect(cmd: Controller.Command):
            cmd.callbacks[0].on_success()

        self.controller.queue_command = MagicMock()
        self.controller.queue_command.side_effect = side_effect

        print(self.test_app.get("/server/command/extract/test1"))
        command = self.controller.queue_command.call_args[0][0]
        self.assertEqual(Controller.Command.Action.EXTRACT, command.action)
        self.assertEqual("test1", command.filename)

        uri = quote(quote("value/with/slashes", safe=""), safe="")
        print(self.test_app.get("/server/command/extract/" + uri))
        command = self.controller.queue_command.call_args[0][0]
        self.assertEqual(Controller.Command.Action.EXTRACT, command.action)
        self.assertEqual("value/with/slashes", command.filename)

        uri = quote(quote(" value with spaces", safe=""), safe="")
        print(self.test_app.get("/server/command/extract/" + uri))
        command = self.controller.queue_command.call_args[0][0]
        self.assertEqual(Controller.Command.Action.EXTRACT, command.action)
        self.assertEqual(" value with spaces", command.filename)

        uri = quote(quote("value'with'singlequote", safe=""), safe="")
        print(self.test_app.get("/server/command/extract/" + uri))
        command = self.controller.queue_command.call_args[0][0]
        self.assertEqual(Controller.Command.Action.EXTRACT, command.action)
        self.assertEqual("value'with'singlequote", command.filename)

        uri = quote(quote('value"with"doublequote', safe=""), safe="")
        print(self.test_app.get("/server/command/extract/" + uri))
        command = self.controller.queue_command.call_args[0][0]
        self.assertEqual(Controller.Command.Action.EXTRACT, command.action)
        self.assertEqual('value"with"doublequote', command.filename)

    def test_delete_local(self):
        def side_effect(cmd: Controller.Command):
            cmd.callbacks[0].on_success()

        self.controller.queue_command = MagicMock()
        self.controller.queue_command.side_effect = side_effect

        print(self.test_app.get("/server/command/delete_local/test1"))
        command = self.controller.queue_command.call_args[0][0]
        self.assertEqual(Controller.Command.Action.DELETE_LOCAL, command.action)
        self.assertEqual("test1", command.filename)

        uri = quote(quote("value/with/slashes", safe=""), safe="")
        print(self.test_app.get("/server/command/delete_local/" + uri))
        command = self.controller.queue_command.call_args[0][0]
        self.assertEqual(Controller.Command.Action.DELETE_LOCAL, command.action)
        self.assertEqual("value/with/slashes", command.filename)

        uri = quote(quote(" value with spaces", safe=""), safe="")
        print(self.test_app.get("/server/command/delete_local/" + uri))
        command = self.controller.queue_command.call_args[0][0]
        self.assertEqual(Controller.Command.Action.DELETE_LOCAL, command.action)
        self.assertEqual(" value with spaces", command.filename)

        uri = quote(quote("value'with'singlequote", safe=""), safe="")
        print(self.test_app.get("/server/command/delete_local/" + uri))
        command = self.controller.queue_command.call_args[0][0]
        self.assertEqual(Controller.Command.Action.DELETE_LOCAL, command.action)
        self.assertEqual("value'with'singlequote", command.filename)

        uri = quote(quote('value"with"doublequote', safe=""), safe="")
        print(self.test_app.get("/server/command/delete_local/" + uri))
        command = self.controller.queue_command.call_args[0][0]
        self.assertEqual(Controller.Command.Action.DELETE_LOCAL, command.action)
        self.assertEqual('value"with"doublequote', command.filename)

    def test_delete_remote(self):
        def side_effect(cmd: Controller.Command):
            cmd.callbacks[0].on_success()

        self.controller.queue_command = MagicMock()
        self.controller.queue_command.side_effect = side_effect

        print(self.test_app.get("/server/command/delete_remote/test1"))
        command = self.controller.queue_command.call_args[0][0]
        self.assertEqual(Controller.Command.Action.DELETE_REMOTE, command.action)
        self.assertEqual("test1", command.filename)

        uri = quote(quote("value/with/slashes", safe=""), safe="")
        print(self.test_app.get("/server/command/delete_remote/" + uri))
        command = self.controller.queue_command.call_args[0][0]
        self.assertEqual(Controller.Command.Action.DELETE_REMOTE, command.action)
        self.assertEqual("value/with/slashes", command.filename)

        uri = quote(quote(" value with spaces", safe=""), safe="")
        print(self.test_app.get("/server/command/delete_remote/" + uri))
        command = self.controller.queue_command.call_args[0][0]
        self.assertEqual(Controller.Command.Action.DELETE_REMOTE, command.action)
        self.assertEqual(" value with spaces", command.filename)

        uri = quote(quote("value'with'singlequote", safe=""), safe="")
        print(self.test_app.get("/server/command/delete_remote/" + uri))
        command = self.controller.queue_command.call_args[0][0]
        self.assertEqual(Controller.Command.Action.DELETE_REMOTE, command.action)
        self.assertEqual("value'with'singlequote", command.filename)

        uri = quote(quote('value"with"doublequote', safe=""), safe="")
        print(self.test_app.get("/server/command/delete_remote/" + uri))
        command = self.controller.queue_command.call_args[0][0]
        self.assertEqual(Controller.Command.Action.DELETE_REMOTE, command.action)
        self.assertEqual('value"with"doublequote', command.filename)


class TestControllerHandlerValidation(BaseTestWebApp):
    """Tests for filename validation in controller handler."""

    def test_control_char_newline_rejected(self):
        uri = quote(quote("file\nname", safe=""), safe="")
        resp = self.test_app.get("/server/command/queue/" + uri, expect_errors=True)
        self.assertEqual(400, resp.status_int)
        self.controller.queue_command.assert_not_called()

    def test_control_char_carriage_return_rejected(self):
        uri = quote(quote("file\rname", safe=""), safe="")
        resp = self.test_app.get("/server/command/queue/" + uri, expect_errors=True)
        self.assertEqual(400, resp.status_int)
        self.controller.queue_command.assert_not_called()

    def test_control_char_tab_rejected(self):
        uri = quote(quote("file\tname", safe=""), safe="")
        resp = self.test_app.get("/server/command/queue/" + uri, expect_errors=True)
        self.assertEqual(400, resp.status_int)
        self.controller.queue_command.assert_not_called()

    def test_control_char_soh_rejected(self):
        uri = quote(quote("file\x01name", safe=""), safe="")
        resp = self.test_app.get("/server/command/queue/" + uri, expect_errors=True)
        self.assertEqual(400, resp.status_int)
        self.controller.queue_command.assert_not_called()

    def test_control_char_del_rejected(self):
        uri = quote(quote("file\x7fname", safe=""), safe="")
        resp = self.test_app.get("/server/command/queue/" + uri, expect_errors=True)
        self.assertEqual(400, resp.status_int)
        self.controller.queue_command.assert_not_called()

    def test_normal_filename_accepted(self):
        def side_effect(cmd: Controller.Command):
            cmd.callbacks[0].on_success()

        self.controller.queue_command = MagicMock()
        self.controller.queue_command.side_effect = side_effect

        resp = self.test_app.get("/server/command/queue/normal_file.txt")
        self.assertEqual(200, resp.status_int)
        command = self.controller.queue_command.call_args[0][0]
        self.assertEqual("normal_file.txt", command.filename)

    def test_path_traversal_rejected(self):
        uri = quote(quote("../etc/passwd", safe=""), safe="")
        resp = self.test_app.get("/server/command/queue/" + uri, expect_errors=True)
        self.assertEqual(400, resp.status_int)
        self.controller.queue_command.assert_not_called()


class TestControllerHandlerTimeout(BaseTestWebApp):
    """Tests that a stalled controller does not hang the request thread (issue #526)."""

    # Patch the bound down so the timeout path resolves quickly and the test
    # never relies on real-time waits beyond a fraction of a second.
    @timeout_decorator.timeout(5)
    @patch("web.handler.controller._ACTION_TIMEOUT_IN_SECS", 0.05)
    def test_action_timeout_returns_504(self):
        # queue_command never invokes any callback -> event is never set
        self.controller.queue_command = MagicMock()

        resp = self.test_app.get("/server/command/queue/test1", expect_errors=True)
        self.assertEqual(504, resp.status_int)
        # The command was still dispatched to the controller
        self.controller.queue_command.assert_called_once()
        command = self.controller.queue_command.call_args[0][0]
        self.assertEqual(Controller.Command.Action.QUEUE, command.action)
        self.assertEqual("test1", command.filename)

    @timeout_decorator.timeout(5)
    @patch("web.handler.controller._ACTION_TIMEOUT_IN_SECS", 0.05)
    def test_delete_remote_timeout_returns_504(self):
        # Confirms all endpoints share the timeout behavior via __dispatch_command
        self.controller.queue_command = MagicMock()

        resp = self.test_app.get("/server/command/delete_remote/test1", expect_errors=True)
        self.assertEqual(504, resp.status_int)
        self.controller.queue_command.assert_called_once()
        command = self.controller.queue_command.call_args[0][0]
        self.assertEqual(Controller.Command.Action.DELETE_REMOTE, command.action)

    @timeout_decorator.timeout(5)
    @patch("web.handler.controller._ACTION_TIMEOUT_IN_SECS", 0.05)
    def test_success_unaffected_by_timeout_bound(self):
        # When the controller responds in time, the 200 path is unchanged
        def side_effect(cmd: Controller.Command):
            cmd.callbacks[0].on_success()

        self.controller.queue_command = MagicMock()
        self.controller.queue_command.side_effect = side_effect

        resp = self.test_app.get("/server/command/queue/test1")
        self.assertEqual(200, resp.status_int)

    @timeout_decorator.timeout(5)
    @patch("web.handler.controller._ACTION_TIMEOUT_IN_SECS", 0.05)
    def test_failure_unaffected_by_timeout_bound(self):
        # When the controller signals failure in time, the 400 path is unchanged
        def side_effect(cmd: Controller.Command):
            cmd.callbacks[0].on_failure("boom")

        self.controller.queue_command = MagicMock()
        self.controller.queue_command.side_effect = side_effect

        resp = self.test_app.get("/server/command/queue/test1", expect_errors=True)
        self.assertEqual(400, resp.status_int)
        self.assertIn("boom", resp.text)
