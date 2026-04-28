import json
import logging
import urllib.request
from datetime import UTC, datetime

from bottle import HTTPResponse

from common import Config
from common.types import overrides
from controller.notification_formatters import format_discord, format_telegram

from ..web_app import IHandler, WebApp


class NotificationsHandler(IHandler):
    """REST endpoints for testing Discord and Telegram notifications."""

    def __init__(self, config: Config):
        self.__config = config
        self._logger = logging.getLogger(self.__class__.__name__)

    @overrides(IHandler)
    def add_routes(self, web_app: WebApp):
        web_app.add_post_handler("/server/notifications/test/discord", self.__handle_test_discord)
        web_app.add_post_handler("/server/notifications/test/telegram", self.__handle_test_telegram)

    def __handle_test_discord(self):
        url = self.__config.notifications.discord_webhook_url
        if not url:
            return HTTPResponse(
                body=json.dumps({"error": "Discord webhook URL is not configured"}),
                status=400,
                headers={"Content-Type": "application/json"},
            )
        headers, body = format_discord("test", "seedsync-test", timestamp=datetime.now(UTC).isoformat())
        return self.__send_test(url, headers, body, "Discord")

    def __handle_test_telegram(self):
        token = self.__config.notifications.telegram_bot_token
        chat_id = self.__config.notifications.telegram_chat_id
        if not token:
            return HTTPResponse(
                body=json.dumps({"error": "Telegram bot token is not configured"}),
                status=400,
                headers={"Content-Type": "application/json"},
            )
        if not chat_id:
            return HTTPResponse(
                body=json.dumps({"error": "Telegram chat ID is not configured"}),
                status=400,
                headers={"Content-Type": "application/json"},
            )
        url, headers, body = format_telegram(token, chat_id, "test", "seedsync-test")
        return self.__send_test(url, headers, body, "Telegram")

    def __send_test(self, url: str, headers: dict[str, str], body: bytes, service: str) -> HTTPResponse:
        try:
            req = urllib.request.Request(url, data=body, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=10):
                pass
            return HTTPResponse(
                body=json.dumps({"success": True}),
                status=200,
                headers={"Content-Type": "application/json"},
            )
        except Exception:
            self._logger.exception("%s test notification failed", service)
            return HTTPResponse(
                body=json.dumps({"error": f"{service} notification failed. Check server logs for details."}),
                status=502,
                headers={"Content-Type": "application/json"},
            )
