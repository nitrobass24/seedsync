# Copyright 2017, Inderpreet Singh, All rights reserved.

from tests.integration.test_web.test_web_app import BaseTestWebApp


class TestServerHandler(BaseTestWebApp):
    def test_restart(self):
        self.assertFalse(self.web_app_builder.server_handler.is_restart_requested())
        print(self.test_app.get("/server/command/restart"))
        self.assertTrue(self.web_app_builder.server_handler.is_restart_requested())
        print(self.test_app.get("/server/command/restart"))
        self.assertTrue(self.web_app_builder.server_handler.is_restart_requested())

    def test_restart_response_body(self):
        """Response body is 'Requested restart'."""
        resp = self.test_app.get("/server/command/restart")
        self.assertIn("Requested restart", resp.text)

    def test_restart_response_is_200(self):
        """Restart endpoint returns 200."""
        resp = self.test_app.get("/server/command/restart")
        self.assertEqual(200, resp.status_int)

    def test_state_transition_false_to_true(self):
        """is_restart_requested() transitions from False to True after restart call."""
        handler = self.web_app_builder.server_handler
        self.assertFalse(handler.is_restart_requested())
        self.test_app.get("/server/command/restart")
        self.assertTrue(handler.is_restart_requested())

    def test_restart_idempotent(self):
        """Calling restart twice still returns 200 (idempotent)."""
        resp1 = self.test_app.get("/server/command/restart")
        resp2 = self.test_app.get("/server/command/restart")
        self.assertEqual(200, resp1.status_int)
        self.assertEqual(200, resp2.status_int)

    def test_restart_state_stays_true(self):
        """Once restart is requested, state remains True."""
        handler = self.web_app_builder.server_handler
        self.test_app.get("/server/command/restart")
        self.assertTrue(handler.is_restart_requested())
        self.test_app.get("/server/command/restart")
        self.assertTrue(handler.is_restart_requested())
