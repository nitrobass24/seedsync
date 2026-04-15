import json
import logging
import sys
import unittest
from unittest.mock import MagicMock

from webtest import TestApp

from common import Config, Status, overrides
from controller import AutoQueuePersist
from controller.stats_recorder import StatsRecorder
from web import WebAppBuilder


class TestStatsHandler(unittest.TestCase):
    """Integration tests for the stats REST endpoints."""

    def setUp(self):
        self.context = MagicMock()

        logger = logging.getLogger()
        handler = logging.StreamHandler(sys.stdout)
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
        self.context.logger = logger

        self.model_files = []
        self.context.status = Status()
        self.context.config = Config()

        auto_queue_persist = AutoQueuePersist()

        controller = MagicMock()
        controller.get_model_files_and_add_listener = MagicMock(side_effect=lambda l: self.model_files)
        controller.remove_model_listener = MagicMock()

        self.stats_recorder = StatsRecorder(db_path=":memory:", logger=logger)

        web_app_builder = WebAppBuilder(self.context, controller, auto_queue_persist, self.stats_recorder)
        self.web_app = web_app_builder.build()
        self.test_app = TestApp(self.web_app)

    def tearDown(self):
        self.stats_recorder.shutdown(timeout=1)

    def test_summary_default_params(self):
        resp = self.test_app.get("/server/stats/summary")
        self.assertEqual(200, resp.status_int)
        body = json.loads(str(resp.html))
        self.assertIn("total_count", body)
        self.assertIn("success_count", body)
        self.assertIn("failed_count", body)
        self.assertIn("total_bytes", body)
        self.assertIn("avg_speed_bps", body)
        self.assertEqual(body["total_count"], 0)

    def test_summary_with_days_param(self):
        resp = self.test_app.get("/server/stats/summary?days=30")
        self.assertEqual(200, resp.status_int)

    def test_summary_invalid_days(self):
        resp = self.test_app.get("/server/stats/summary?days=abc", expect_errors=True)
        self.assertEqual(400, resp.status_int)
        body = json.loads(str(resp.html))
        self.assertIn("error", body)

    def test_summary_days_out_of_range(self):
        resp = self.test_app.get("/server/stats/summary?days=0", expect_errors=True)
        self.assertEqual(400, resp.status_int)

    def test_transfers_default_params(self):
        resp = self.test_app.get("/server/stats/transfers")
        self.assertEqual(200, resp.status_int)
        body = json.loads(str(resp.html))
        self.assertIsInstance(body, list)
        self.assertEqual(len(body), 0)

    def test_transfers_with_limit(self):
        resp = self.test_app.get("/server/stats/transfers?limit=10")
        self.assertEqual(200, resp.status_int)

    def test_transfers_invalid_limit(self):
        resp = self.test_app.get("/server/stats/transfers?limit=notanumber", expect_errors=True)
        self.assertEqual(400, resp.status_int)

    def test_transfers_limit_out_of_range(self):
        resp = self.test_app.get("/server/stats/transfers?limit=999", expect_errors=True)
        self.assertEqual(400, resp.status_int)

    def test_speed_history_default_params(self):
        resp = self.test_app.get("/server/stats/speed-history")
        self.assertEqual(200, resp.status_int)
        body = json.loads(str(resp.html))
        self.assertIsInstance(body, list)

    def test_speed_history_with_hours(self):
        resp = self.test_app.get("/server/stats/speed-history?hours=48")
        self.assertEqual(200, resp.status_int)

    def test_speed_history_invalid_hours(self):
        resp = self.test_app.get("/server/stats/speed-history?hours=xyz", expect_errors=True)
        self.assertEqual(400, resp.status_int)

    def test_speed_history_hours_out_of_range(self):
        resp = self.test_app.get("/server/stats/speed-history?hours=200", expect_errors=True)
        self.assertEqual(400, resp.status_int)


if __name__ == "__main__":
    unittest.main()
