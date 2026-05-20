# Copyright 2017, Inderpreet Singh, All rights reserved.

import json
from unittest.mock import patch
from urllib.parse import quote

from common import Config
from tests.integration.test_web.test_web_app import BaseTestWebApp


class TestConfigHandler(BaseTestWebApp):
    def test_get(self):
        self.context.config.general.log_level = "DEBUG"
        self.context.config.lftp.remote_path = "/remote/server/path"
        self.context.config.controller.interval_ms_local_scan = 5678
        self.context.config.web.port = 8080
        resp = self.test_app.get("/server/config/get")
        self.assertEqual(200, resp.status_int)
        json_dict = json.loads(str(resp.html))
        self.assertEqual("DEBUG", json_dict["general"]["log_level"])
        self.assertEqual("/remote/server/path", json_dict["lftp"]["remote_path"])
        self.assertEqual(5678, json_dict["controller"]["interval_ms_local_scan"])
        self.assertEqual(8080, json_dict["web"]["port"])

    def test_set_good(self):
        self.assertEqual("INFO", self.context.config.general.log_level)
        resp = self.test_app.get("/server/config/set/general/log_level/DEBUG")
        self.assertEqual(200, resp.status_int)
        self.assertEqual("DEBUG", self.context.config.general.log_level)

        self.assertEqual(None, self.context.config.lftp.remote_path)
        uri = quote(quote("/path/to/somewhere", safe=""), safe="")
        resp = self.test_app.get("/server/config/set/lftp/remote_path/" + uri)
        self.assertEqual(200, resp.status_int)
        self.assertEqual("/path/to/somewhere", self.context.config.lftp.remote_path)

        self.assertEqual(None, self.context.config.controller.interval_ms_local_scan)
        resp = self.test_app.get("/server/config/set/controller/interval_ms_local_scan/5678")
        self.assertEqual(200, resp.status_int)
        self.assertEqual(5678, self.context.config.controller.interval_ms_local_scan)

        self.assertEqual(None, self.context.config.web.port)
        resp = self.test_app.get("/server/config/set/web/port/8080")
        self.assertEqual(200, resp.status_int)
        self.assertEqual(8080, self.context.config.web.port)

    def test_set_missing_section(self):
        self.assertFalse(self.context.config.has_section("bad_section"))
        resp = self.test_app.get("/server/config/set/bad_section/option/value", expect_errors=True)
        self.assertEqual(400, resp.status_int)
        self.assertEqual("There is no section 'bad_section' in config", str(resp.html))
        self.assertFalse(self.context.config.has_section("bad_section"))

    def test_set_missing_option(self):
        self.assertFalse(self.context.config.general.has_property("bad_option"))
        resp = self.test_app.get("/server/config/set/general/bad_option/value", expect_errors=True)
        self.assertEqual(400, resp.status_int)
        self.assertEqual("Section 'general' in config has no option 'bad_option'", str(resp.html))
        self.assertFalse(self.context.config.general.has_property("bad_option"))

    def test_set_bad_value(self):
        # log_level
        self.assertEqual("INFO", self.context.config.general.log_level)
        resp = self.test_app.get("/server/config/set/general/log_level/cat", expect_errors=True)
        self.assertEqual(400, resp.status_int)
        self.assertIn("Bad config: General.log_level (cat) must be one of:", str(resp.html))
        self.assertEqual("INFO", self.context.config.general.log_level)

        # positive int
        self.assertEqual(None, self.context.config.controller.interval_ms_local_scan)
        resp = self.test_app.get("/server/config/set/controller/interval_ms_local_scan/-1", expect_errors=True)
        self.assertEqual(400, resp.status_int)
        self.assertEqual("Bad config: Controller.interval_ms_local_scan (-1) must be greater than 0", str(resp.html))
        self.assertEqual(None, self.context.config.controller.interval_ms_local_scan)

    def test_set_empty_value(self):
        self.assertEqual(None, self.context.config.lftp.remote_path)
        resp = self.test_app.get("/server/config/set/lftp/remote_path/", expect_errors=True)
        self.assertEqual(404, resp.status_int)
        self.assertEqual(None, self.context.config.lftp.remote_path)

        self.assertEqual(None, self.context.config.lftp.remote_path)
        resp = self.test_app.get("/server/config/set/lftp/remote_path/%20%20", expect_errors=True)
        self.assertEqual(400, resp.status_int)
        self.assertEqual("Bad config: Lftp.remote_path is empty", str(resp.html))
        self.assertEqual(None, self.context.config.lftp.remote_path)

    def test_get_redacts_sensitive_fields(self):
        self.context.config.lftp.remote_password = "super-secret"
        self.context.config.web.api_key = "my-api-key"
        resp = self.test_app.get("/server/config/get")
        self.assertEqual(200, resp.status_int)
        json_dict = json.loads(str(resp.html))
        self.assertEqual(Config.REDACTED_SENTINEL, json_dict["lftp"]["remote_password"])
        self.assertEqual(Config.REDACTED_SENTINEL, json_dict["web"]["api_key"])

    def test_set_sensitive_field_does_not_echo_value(self):
        resp = self.test_app.get("/server/config/set/lftp/remote_password/my-secret")
        self.assertEqual(200, resp.status_int)
        self.assertNotIn("my-secret", str(resp.html))
        self.assertIn("lftp.remote_password updated", str(resp.html))
        self.assertEqual("my-secret", self.context.config.lftp.remote_password)

    def test_set_sensitive_field_rejects_redacted_sentinel(self):
        self.context.config.lftp.remote_password = "real-password"
        sentinel = quote(quote(Config.REDACTED_SENTINEL, safe=""), safe="")
        resp = self.test_app.get("/server/config/set/lftp/remote_password/" + sentinel, expect_errors=True)
        self.assertEqual(400, resp.status_int)
        self.assertIn("Cannot set sensitive field to redacted value", str(resp.html))
        self.assertEqual("real-password", self.context.config.lftp.remote_password)

    def test_set_persistence_failure_rolls_back(self):
        """If to_file raises, in-memory state must revert and no LFTP callback fires."""
        self.context.config.general.log_level = "INFO"
        with patch.object(Config, "to_file", side_effect=OSError("disk full")):
            resp = self.test_app.get("/server/config/set/general/log_level/DEBUG", expect_errors=True)
        self.assertEqual(500, resp.status_int)
        self.assertIn("Failed to persist config general.log_level", str(resp.html))
        self.assertEqual("INFO", self.context.config.general.log_level)
        self.controller.request_lftp_reconfigure.assert_not_called()

    def test_set_persistence_failure_rolls_back_lftp_tuning_key(self):
        """A failed write on a hot-reload key must not fire the LFTP callback."""
        self.context.config.lftp.num_max_parallel_downloads = 3
        with patch.object(Config, "to_file", side_effect=OSError("disk full")):
            resp = self.test_app.get(
                "/server/config/set/lftp/num_max_parallel_downloads/7", expect_errors=True
            )
        self.assertEqual(500, resp.status_int)
        self.assertEqual(3, self.context.config.lftp.num_max_parallel_downloads)
        self.controller.request_lftp_reconfigure.assert_not_called()

    def test_set_persistence_success_fires_lftp_callback(self):
        """Baseline: a successful write on a hot-reload key still fires the callback."""
        resp = self.test_app.get("/server/config/set/lftp/num_max_parallel_downloads/7")
        self.assertEqual(200, resp.status_int)
        self.assertEqual(7, self.context.config.lftp.num_max_parallel_downloads)
        self.controller.request_lftp_reconfigure.assert_called_once()

    def test_set_persistence_failure_skips_rollback_when_concurrent_update(self):
        """If another request overwrote the value before our rollback fires,
        we must not clobber the newer value with our stale old_value."""
        self.context.config.general.log_level = "INFO"

        # Simulate a concurrent write landing between set_property and rollback:
        # to_file raises, but before the except handler runs, another mutation
        # has already changed the in-memory value to "WARNING".
        def fail_then_simulate_concurrent_write(*_args, **_kw):
            self.context.config.general.log_level = "WARNING"
            raise OSError("disk full")

        with patch.object(Config, "to_file", side_effect=fail_then_simulate_concurrent_write):
            resp = self.test_app.get("/server/config/set/general/log_level/DEBUG", expect_errors=True)
        self.assertEqual(500, resp.status_int)
        # Rollback must be skipped — the newer "WARNING" survives, not "INFO".
        self.assertEqual("WARNING", self.context.config.general.log_level)
