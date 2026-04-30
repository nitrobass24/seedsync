import json
import unittest
import urllib.error
from unittest.mock import MagicMock, patch

from common import overrides
from tests.integration.test_web.test_web_app import BaseTestWebApp


class TestNotificationsHandler(BaseTestWebApp):
    """Integration tests for the Discord/Telegram test notification endpoints."""

    @overrides(BaseTestWebApp)
    def setUp(self):
        super().setUp()
        from webtest import TestApp

        from web import WebAppBuilder

        self.web_app_builder = WebAppBuilder(self.context, self.controller, self.auto_queue_persist)
        self.web_app = self.web_app_builder.build()
        self.test_app = TestApp(self.web_app, extra_environ={"REMOTE_ADDR": "127.0.0.1"})

    def _post(self, url, expect_errors=False):
        return self.test_app.post(
            url,
            params=json.dumps({}),
            content_type="application/json",
            expect_errors=expect_errors,
        )

    # ------------------------------------------------------------------
    # Discord
    # ------------------------------------------------------------------
    def test_discord_not_configured(self):
        self.context.config.notifications.discord_webhook_url = ""
        resp = self._post("/server/notifications/test/discord", expect_errors=True)
        self.assertEqual(400, resp.status_int)
        body = json.loads(resp.text)
        self.assertIn("not configured", body["error"].lower())

    @patch("web.handler.notifications.urllib.request.urlopen")
    def test_discord_success(self, mock_urlopen):
        self.context.config.notifications.discord_webhook_url = "https://discord.com/api/webhooks/123/TOKEN"
        mock_resp = MagicMock()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        resp = self._post("/server/notifications/test/discord")
        self.assertEqual(200, resp.status_int)
        body = json.loads(resp.text)
        self.assertTrue(body["success"])

    @patch("web.handler.notifications.urllib.request.urlopen")
    def test_discord_failure_returns_502(self, mock_urlopen):
        self.context.config.notifications.discord_webhook_url = "https://discord.com/api/webhooks/123/TOKEN"
        mock_urlopen.side_effect = urllib.error.URLError("connection refused")
        resp = self._post("/server/notifications/test/discord", expect_errors=True)
        self.assertEqual(502, resp.status_int)
        body = json.loads(resp.text)
        self.assertIn("failed", body["error"].lower())
        self.assertNotIn("URLError", resp.text)

    # ------------------------------------------------------------------
    # Telegram
    # ------------------------------------------------------------------
    def test_telegram_token_not_configured(self):
        self.context.config.notifications.telegram_bot_token = ""
        self.context.config.notifications.telegram_chat_id = "123"
        resp = self._post("/server/notifications/test/telegram", expect_errors=True)
        self.assertEqual(400, resp.status_int)
        body = json.loads(resp.text)
        self.assertIn("bot token", body["error"].lower())

    def test_telegram_chat_id_not_configured(self):
        self.context.config.notifications.telegram_bot_token = "tok"
        self.context.config.notifications.telegram_chat_id = ""
        resp = self._post("/server/notifications/test/telegram", expect_errors=True)
        self.assertEqual(400, resp.status_int)
        body = json.loads(resp.text)
        self.assertIn("chat id", body["error"].lower())

    @patch("web.handler.notifications.urllib.request.urlopen")
    def test_telegram_success(self, mock_urlopen):
        self.context.config.notifications.telegram_bot_token = "tok"
        self.context.config.notifications.telegram_chat_id = "123"
        mock_resp = MagicMock()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        resp = self._post("/server/notifications/test/telegram")
        self.assertEqual(200, resp.status_int)
        body = json.loads(resp.text)
        self.assertTrue(body["success"])

    @patch("web.handler.notifications.urllib.request.urlopen")
    def test_telegram_failure_returns_502(self, mock_urlopen):
        self.context.config.notifications.telegram_bot_token = "tok"
        self.context.config.notifications.telegram_chat_id = "123"
        mock_urlopen.side_effect = urllib.error.URLError("connection refused")
        resp = self._post("/server/notifications/test/telegram", expect_errors=True)
        self.assertEqual(502, resp.status_int)
        body = json.loads(resp.text)
        self.assertIn("failed", body["error"].lower())


if __name__ == "__main__":
    unittest.main()
