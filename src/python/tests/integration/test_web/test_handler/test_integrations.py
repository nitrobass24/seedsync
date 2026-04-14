import json
import unittest
from unittest.mock import MagicMock, patch

from tests.integration.test_web.test_web_app import BaseTestWebApp


class TestIntegrationsHandler(BaseTestWebApp):
    def test_test_sonarr_missing_url(self):
        self.context.config.integrations.sonarr_url = ""
        self.context.config.integrations.sonarr_api_key = "some-key"
        resp = self.test_app.get("/server/integrations/test/sonarr", expect_errors=True)
        self.assertEqual(400, resp.status_int)
        body = json.loads(str(resp.html))
        self.assertIn("URL is not configured", body["error"])

    def test_test_sonarr_missing_api_key(self):
        self.context.config.integrations.sonarr_url = "http://localhost:8989"
        self.context.config.integrations.sonarr_api_key = ""
        resp = self.test_app.get("/server/integrations/test/sonarr", expect_errors=True)
        self.assertEqual(400, resp.status_int)
        body = json.loads(str(resp.html))
        self.assertIn("API key is not configured", body["error"])

    def test_test_sonarr_bad_scheme(self):
        self.context.config.integrations.sonarr_url = "ftp://localhost:8989"
        self.context.config.integrations.sonarr_api_key = "some-key"
        resp = self.test_app.get("/server/integrations/test/sonarr", expect_errors=True)
        self.assertEqual(400, resp.status_int)
        body = json.loads(str(resp.html))
        self.assertIn("http://", body["error"])

    @patch("web.handler.integrations.urllib.request.urlopen")
    def test_test_sonarr_success(self, mock_urlopen):
        self.context.config.integrations.sonarr_url = "http://localhost:8989"
        self.context.config.integrations.sonarr_api_key = "test-key"
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"version": "4.0.0.1"}).encode("utf-8")
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp
        resp = self.test_app.get("/server/integrations/test/sonarr")
        self.assertEqual(200, resp.status_int)
        body = json.loads(str(resp.html))
        self.assertTrue(body["success"])
        self.assertEqual("4.0.0.1", body["version"])

    @patch("web.handler.integrations.urllib.request.urlopen")
    def test_test_sonarr_connection_failure(self, mock_urlopen):
        self.context.config.integrations.sonarr_url = "http://localhost:8989"
        self.context.config.integrations.sonarr_api_key = "test-key"
        mock_urlopen.side_effect = ConnectionRefusedError("Connection refused")
        resp = self.test_app.get("/server/integrations/test/sonarr", expect_errors=True)
        self.assertEqual(502, resp.status_int)
        body = json.loads(str(resp.html))
        self.assertIn("Connection failed", body["error"])

    @patch("web.handler.integrations.urllib.request.urlopen")
    def test_test_radarr_success(self, mock_urlopen):
        self.context.config.integrations.radarr_url = "http://localhost:7878"
        self.context.config.integrations.radarr_api_key = "test-key"
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"version": "5.2.0.1"}).encode("utf-8")
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp
        resp = self.test_app.get("/server/integrations/test/radarr")
        self.assertEqual(200, resp.status_int)
        body = json.loads(str(resp.html))
        self.assertTrue(body["success"])
        self.assertEqual("5.2.0.1", body["version"])

    def test_test_radarr_missing_url(self):
        self.context.config.integrations.radarr_url = ""
        self.context.config.integrations.radarr_api_key = "some-key"
        resp = self.test_app.get("/server/integrations/test/radarr", expect_errors=True)
        self.assertEqual(400, resp.status_int)
        body = json.loads(str(resp.html))
        self.assertIn("URL is not configured", body["error"])


if __name__ == "__main__":
    unittest.main()
