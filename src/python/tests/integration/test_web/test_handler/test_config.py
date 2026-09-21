# Copyright 2017, Inderpreet Singh, All rights reserved.

import json
from unittest.mock import patch
from urllib.parse import quote

from common import Config
from ssh import SshcpError
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

    def test_set_percent_value_persists_and_reloads(self):
        """A config value containing '%' must set, persist, and reload cleanly.

        Regression guard for #507: the persist path (to_file -> Config.to_str)
        used configparser's default BasicInterpolation, which raised on '%'.
        """
        value = "100%secret"
        uri = quote(quote(value, safe=""), safe="")
        resp = self.test_app.get("/server/config/set/lftp/remote_password/" + uri)
        self.assertEqual(200, resp.status_int)
        self.assertEqual(value, self.context.config.lftp.remote_password)
        # Reload from the persisted settings file to confirm the on-disk round trip.
        with open(self.context.config_path) as f:
            reloaded = Config.from_str(f.read())
        self.assertEqual(value, reloaded.lftp.remote_password)

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

    def test_set_persistence_failure_rolls_back_on_non_oserror(self):
        """A non-OSError persist failure must also revert in-memory state.

        Regression guard for #507 Part 2: serialization can raise non-OSError
        exceptions (e.g. configparser.Error). Those must still trigger the
        rollback rather than escaping and leaving the new value live but never
        persisted.
        """
        self.context.config.general.log_level = "INFO"
        with patch.object(Config, "to_file", side_effect=RuntimeError("serialize boom")):
            resp = self.test_app.get("/server/config/set/general/log_level/DEBUG", expect_errors=True)
        self.assertEqual(500, resp.status_int)
        self.assertIn("Failed to persist config general.log_level", str(resp.html))
        self.assertEqual("INFO", self.context.config.general.log_level)
        self.controller.request_lftp_reconfigure.assert_not_called()

    def test_set_persistence_failure_rolls_back_lftp_tuning_key(self):
        """A failed write on a hot-reload key must not fire the LFTP callback."""
        self.context.config.lftp.num_max_parallel_downloads = 3
        with patch.object(Config, "to_file", side_effect=OSError("disk full")):
            resp = self.test_app.get("/server/config/set/lftp/num_max_parallel_downloads/7", expect_errors=True)
        self.assertEqual(500, resp.status_int)
        self.assertEqual(3, self.context.config.lftp.num_max_parallel_downloads)
        self.controller.request_lftp_reconfigure.assert_not_called()

    def test_set_persistence_success_fires_lftp_callback(self):
        """Baseline: a successful write on a hot-reload key still fires the callback."""
        resp = self.test_app.get("/server/config/set/lftp/num_max_parallel_downloads/7")
        self.assertEqual(200, resp.status_int)
        self.assertEqual(7, self.context.config.lftp.num_max_parallel_downloads)
        self.controller.request_lftp_reconfigure.assert_called_once()

    def test_set_protocol_ftps_persists_without_lftp_callback(self):
        """protocol is a connection-level key: it persists but does NOT fire the
        LFTP hot-reload callback (it is not in _LFTP_TUNING_KEYS).
        """
        self.assertEqual("sftp", self.context.config.lftp.protocol)
        resp = self.test_app.get("/server/config/set/lftp/protocol/ftps")
        self.assertEqual(200, resp.status_int)
        self.assertEqual("ftps", self.context.config.lftp.protocol)
        # Connection-level change requires a restart, so the hot-reload callback
        # must not fire.
        self.controller.request_lftp_reconfigure.assert_not_called()
        # Confirm the on-disk round trip.
        with open(self.context.config_path) as f:
            reloaded = Config.from_str(f.read())
        self.assertEqual("ftps", reloaded.lftp.protocol)

    def test_set_remote_ftp_port_persists_without_lftp_callback(self):
        """remote_ftp_port is connection-level: persists but does NOT fire the
        LFTP hot-reload callback.
        """
        self.assertEqual(21, self.context.config.lftp.remote_ftp_port)
        resp = self.test_app.get("/server/config/set/lftp/remote_ftp_port/21")
        self.assertEqual(200, resp.status_int)
        self.assertEqual(21, self.context.config.lftp.remote_ftp_port)
        self.controller.request_lftp_reconfigure.assert_not_called()
        with open(self.context.config_path) as f:
            reloaded = Config.from_str(f.read())
        self.assertEqual(21, reloaded.lftp.remote_ftp_port)

    def test_set_connection_key_no_callback_contrast_with_tuning_key(self):
        """Contrast: a connection-level key does NOT fire the callback, while a
        known tuning key (same handler, same request shape) DOES.
        """
        # Connection-level key: no callback.
        resp = self.test_app.get("/server/config/set/lftp/protocol/ftps")
        self.assertEqual(200, resp.status_int)
        self.controller.request_lftp_reconfigure.assert_not_called()

        # Known tuning key: callback fires.
        resp = self.test_app.get("/server/config/set/lftp/num_max_parallel_downloads/7")
        self.assertEqual(200, resp.status_int)
        self.controller.request_lftp_reconfigure.assert_called_once()

    def test_set_protocol_invalid_value_rejected(self):
        """An invalid protocol (e.g. scp) is rejected with a 400 and the
        'must be one of' message; the value is left unchanged.
        """
        self.assertEqual("sftp", self.context.config.lftp.protocol)
        resp = self.test_app.get("/server/config/set/lftp/protocol/scp", expect_errors=True)
        self.assertEqual(400, resp.status_int)
        self.assertIn("Bad config: Lftp.protocol (scp) must be one of:", str(resp.html))
        self.assertEqual("sftp", self.context.config.lftp.protocol)
        self.controller.request_lftp_reconfigure.assert_not_called()

    def test_get_surfaces_ftps_fields_unredacted(self):
        """/server/config/get surfaces protocol/remote_ftp_port/
        ftp_ssl_verify_certificate; none are sensitive, so none are redacted.
        """
        self.context.config.lftp.protocol = "ftps"
        self.context.config.lftp.remote_ftp_port = 990
        self.context.config.lftp.ftp_ssl_verify_certificate = True
        resp = self.test_app.get("/server/config/get")
        self.assertEqual(200, resp.status_int)
        json_dict = json.loads(str(resp.html))
        self.assertEqual("ftps", json_dict["lftp"]["protocol"])
        self.assertEqual(990, json_dict["lftp"]["remote_ftp_port"])
        self.assertEqual(True, json_dict["lftp"]["ftp_ssl_verify_certificate"])
        # None of the new fields are sensitive, so none are redacted.
        self.assertNotEqual(Config.REDACTED_SENTINEL, json_dict["lftp"]["protocol"])
        self.assertNotEqual(Config.REDACTED_SENTINEL, json_dict["lftp"]["remote_ftp_port"])
        self.assertNotEqual(Config.REDACTED_SENTINEL, json_dict["lftp"]["ftp_ssl_verify_certificate"])

    def test_set_serializes_concurrent_writers(self):
        """The handler's __write_lock must serialize concurrent set_config calls.

        Without the lock, two threads can interleave the mutate → persist →
        rollback sequence and the second thread's value can be captured into
        to_file mid-way through the first thread's rollback. With the lock,
        every full mutate→persist→rollback runs atomically.
        """
        import threading

        # Block to_file just long enough that thread B's request would
        # interleave with thread A's failed write if the lock were missing.
        enter_to_file = threading.Event()
        release_to_file = threading.Event()

        def slow_failing_write(*_args, **_kw):
            enter_to_file.set()
            release_to_file.wait(timeout=5)
            raise OSError("disk full")

        results: dict[str, int] = {}

        def writer_a():
            with patch.object(Config, "to_file", side_effect=slow_failing_write):
                resp = self.test_app.get("/server/config/set/general/log_level/DEBUG", expect_errors=True)
                results["a"] = resp.status_int

        def writer_b():
            enter_to_file.wait(timeout=5)
            resp = self.test_app.get("/server/config/set/general/log_level/WARNING", expect_errors=True)
            results["b"] = resp.status_int

        t_a = threading.Thread(target=writer_a)
        t_b = threading.Thread(target=writer_b)
        t_a.start()
        t_b.start()
        # Give B a moment to block on the lock, then release A.
        enter_to_file.wait(timeout=5)
        release_to_file.set()
        t_a.join(timeout=10)
        t_b.join(timeout=10)

        # A failed (500), B saw a fully-rolled-back state, then succeeded (200).
        self.assertEqual(500, results["a"])
        self.assertEqual(200, results["b"])
        # B's value wins because it ran after A's rollback completed.
        self.assertEqual("WARNING", self.context.config.general.log_level)

    def _post_test_connection(self, expect_errors=False):
        # CSRF protection exempts localhost; the default TestApp REMOTE_ADDR
        # is not localhost, so it must be set explicitly for POST requests.
        return self.test_app.post(
            "/server/config/test-connection",
            extra_environ={"REMOTE_ADDR": "127.0.0.1"},
            expect_errors=expect_errors,
        )

    def test_test_connection_missing_required_settings(self):
        resp = self._post_test_connection(expect_errors=True)
        self.assertEqual(400, resp.status_int)
        json_dict = json.loads(resp.text)
        self.assertIn("remote_address", json_dict["error"])
        self.assertIn("remote_username", json_dict["error"])
        self.assertIn("remote_port", json_dict["error"])

    def test_test_connection_missing_password_reports_missing_setting_not_credential_error(self):
        # Password auth (use_ssh_key False, the default) with no password set
        # must surface as a config problem, not attempt an empty-password
        # login and report a misleading credential failure.
        self.context.config.lftp.remote_address = "example.com"
        self.context.config.lftp.remote_username = "user"
        self.context.config.lftp.remote_port = 22
        with patch("web.lftp_ssh.Sshcp") as mock_sshcp:
            resp = self._post_test_connection(expect_errors=True)
        self.assertEqual(400, resp.status_int)
        json_dict = json.loads(resp.text)
        self.assertIn("remote_password", json_dict["error"])
        self.assertNotIn("credential_error", json_dict)
        mock_sshcp.assert_not_called()

    def test_test_connection_success(self):
        self.context.config.lftp.remote_address = "example.com"
        self.context.config.lftp.remote_username = "user"
        self.context.config.lftp.remote_password = "pass"
        self.context.config.lftp.remote_port = 22
        with patch("web.lftp_ssh.Sshcp.detect_shell", return_value="/bin/bash"):
            resp = self._post_test_connection()
        self.assertEqual(200, resp.status_int)
        json_dict = json.loads(resp.text)
        self.assertTrue(json_dict["success"])

    def test_test_connection_failure_surfaces_error(self):
        self.context.config.lftp.remote_address = "example.com"
        self.context.config.lftp.remote_username = "user"
        self.context.config.lftp.remote_password = "wrong-pass"
        self.context.config.lftp.remote_port = 22
        with patch("web.lftp_ssh.Sshcp.detect_shell", side_effect=SshcpError("Incorrect password")):
            resp = self._post_test_connection(expect_errors=True)
        self.assertEqual(502, resp.status_int)
        json_dict = json.loads(resp.text)
        self.assertEqual("Incorrect password", json_dict["error"])

    def test_test_connection_incorrect_password_flags_credential_error(self):
        self.context.config.lftp.remote_address = "example.com"
        self.context.config.lftp.remote_username = "user"
        self.context.config.lftp.remote_password = "wrong-pass"
        self.context.config.lftp.remote_port = 22
        with patch("web.lftp_ssh.Sshcp.detect_shell", side_effect=SshcpError("Incorrect password")):
            resp = self._post_test_connection(expect_errors=True)
        json_dict = json.loads(resp.text)
        self.assertTrue(json_dict["credential_error"])

    def test_test_connection_permission_denied_flags_credential_error(self):
        self.context.config.lftp.remote_address = "example.com"
        self.context.config.lftp.remote_username = "user"
        self.context.config.lftp.remote_port = 22
        self.context.config.lftp.use_ssh_key = True
        with patch(
            "web.lftp_ssh.Sshcp.detect_shell",
            side_effect=SshcpError("user@example.com: Permission denied (publickey)."),
        ):
            resp = self._post_test_connection(expect_errors=True)
        json_dict = json.loads(resp.text)
        self.assertTrue(json_dict["credential_error"])

    def test_test_connection_non_credential_failure_omits_credential_error(self):
        self.context.config.lftp.remote_address = "example.com"
        self.context.config.lftp.remote_username = "user"
        self.context.config.lftp.remote_password = "pass"
        self.context.config.lftp.remote_port = 22
        with patch("web.lftp_ssh.Sshcp.detect_shell", side_effect=SshcpError("Connection refused by server")):
            resp = self._post_test_connection(expect_errors=True)
        json_dict = json.loads(resp.text)
        self.assertNotIn("credential_error", json_dict)

    def test_test_connection_uses_ssh_key_omits_password(self):
        self.context.config.lftp.remote_address = "example.com"
        self.context.config.lftp.remote_username = "user"
        self.context.config.lftp.remote_password = "should-be-ignored"
        self.context.config.lftp.remote_port = 22
        self.context.config.lftp.use_ssh_key = True
        with patch("web.lftp_ssh.Sshcp") as mock_sshcp:
            mock_sshcp.return_value.detect_shell.return_value = "/bin/bash"
            resp = self._post_test_connection()
        self.assertEqual(200, resp.status_int)
        mock_sshcp.assert_called_once_with(host="example.com", port=22, user="user", password=None)
