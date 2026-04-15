import json
import logging
import unittest

from webtest import TestApp

from controller.stats_recorder import StatsRecorder
from model.file import ModelFile
from tests.integration.test_web.test_web_app import BaseTestWebApp
from web import WebAppBuilder


class TestStatsHandler(BaseTestWebApp):
    """Integration tests for the stats REST endpoints."""

    def setUp(self):
        self.stats_recorder = StatsRecorder(db_path=":memory:", logger=logging.getLogger("test_stats"))
        super().setUp()
        # Rebuild with stats_recorder injected
        self.web_app_builder = WebAppBuilder(
            self.context, self.controller, self.auto_queue_persist, self.stats_recorder
        )
        self.web_app = self.web_app_builder.build()
        self.test_app = TestApp(self.web_app)

    def tearDown(self):
        self.stats_recorder.shutdown(timeout=1)

    def test_summary_default_params(self):
        resp = self.test_app.get("/server/stats/summary")
        self.assertEqual(200, resp.status_int)
        body = json.loads(resp.text)
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
        body = json.loads(resp.text)
        self.assertIn("error", body)

    def test_summary_days_out_of_range(self):
        resp = self.test_app.get("/server/stats/summary?days=0", expect_errors=True)
        self.assertEqual(400, resp.status_int)

    def test_summary_days_not_allowed(self):
        resp = self.test_app.get("/server/stats/summary?days=15", expect_errors=True)
        self.assertEqual(400, resp.status_int)
        body = json.loads(resp.text)
        self.assertIn("7, 30, or 90", body["error"])

    def test_transfers_default_params(self):
        resp = self.test_app.get("/server/stats/transfers")
        self.assertEqual(200, resp.status_int)
        body = json.loads(resp.text)
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
        body = json.loads(resp.text)
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

    def test_summary_and_transfers_with_seeded_data(self):
        """Seed a transfer via StatsRecorder and verify endpoints return it."""
        old = ModelFile("seeded.mkv", False)
        old.state = ModelFile.State.DEFAULT
        downloading = ModelFile("seeded.mkv", False)
        downloading.state = ModelFile.State.DOWNLOADING
        downloading.remote_size = 2048
        done = ModelFile("seeded.mkv", False)
        done.state = ModelFile.State.DOWNLOADED
        done.remote_size = 2048

        self.stats_recorder.file_updated(old, downloading)
        self.stats_recorder.file_updated(downloading, done)

        resp = self.test_app.get("/server/stats/summary?days=7")
        self.assertEqual(200, resp.status_int)
        body = json.loads(resp.text)
        self.assertGreater(body["total_count"], 0)
        self.assertGreater(body["success_count"], 0)
        self.assertGreater(body["total_bytes"], 0)

        resp = self.test_app.get("/server/stats/transfers")
        self.assertEqual(200, resp.status_int)
        transfers = json.loads(resp.text)
        self.assertGreater(len(transfers), 0)
        filenames = [t["filename"] for t in transfers]
        self.assertIn("seeded.mkv", filenames)


if __name__ == "__main__":
    unittest.main()
