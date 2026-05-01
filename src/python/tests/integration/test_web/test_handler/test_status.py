# Copyright 2017, Inderpreet Singh, All rights reserved.

import json

from tests.integration.test_web.test_web_app import BaseTestWebApp


class TestStatusHandler(BaseTestWebApp):
    def test_status(self):
        resp = self.test_app.get("/server/status")
        self.assertEqual(200, resp.status_int)
        json_dict = json.loads(str(resp.html))
        self.assertEqual(True, json_dict["server"]["up"])

    def test_full_response_structure(self):
        """Response body contains both 'server' and 'controller' sections."""
        resp = self.test_app.get("/server/status")
        json_dict = json.loads(str(resp.html))
        self.assertIn("server", json_dict)
        self.assertIn("controller", json_dict)
        # Server section
        self.assertIn("up", json_dict["server"])
        self.assertIn("error_msg", json_dict["server"])
        # Controller section
        self.assertIn("latest_local_scan_time", json_dict["controller"])
        self.assertIn("latest_remote_scan_time", json_dict["controller"])
        self.assertIn("no_enabled_pairs", json_dict["controller"])

    def test_remote_scan_time_null_initially(self):
        """controller.latest_remote_scan_time is null initially."""
        resp = self.test_app.get("/server/status")
        json_dict = json.loads(str(resp.html))
        self.assertIsNone(json_dict["controller"]["latest_remote_scan_time"])

    def test_local_scan_time_null_initially(self):
        """controller.latest_local_scan_time is null initially."""
        resp = self.test_app.get("/server/status")
        json_dict = json.loads(str(resp.html))
        self.assertIsNone(json_dict["controller"]["latest_local_scan_time"])

    def test_no_enabled_pairs_reflects_state(self):
        """controller.no_enabled_pairs reflects actual state."""
        resp = self.test_app.get("/server/status")
        json_dict = json.loads(str(resp.html))
        # Default status has no_enabled_pairs = False
        self.assertFalse(json_dict["controller"]["no_enabled_pairs"])

    def test_no_enabled_pairs_true_when_set(self):
        """controller.no_enabled_pairs reflects True when set."""
        self.context.status.controller.no_enabled_pairs = True
        resp = self.test_app.get("/server/status")
        json_dict = json.loads(str(resp.html))
        self.assertTrue(json_dict["controller"]["no_enabled_pairs"])
