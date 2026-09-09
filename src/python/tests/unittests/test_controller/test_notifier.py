import logging
import threading
import time
import unittest
from unittest.mock import MagicMock, patch

from controller.notifier import WebhookNotifier
from model.file import ModelFile


class TestWebhookNotifierShutdown(unittest.TestCase):
    """Tests for WebhookNotifier shutdown drain behavior."""

    def _make_config(
        self,
        webhook_url="http://example.com/hook",
        discord_webhook_url="",
        telegram_bot_token="",
        telegram_chat_id="",
    ):
        config = MagicMock()
        config.notifications.webhook_url = webhook_url
        config.notifications.notify_on_download_start = False
        config.notifications.notify_on_download_complete = True
        config.notifications.notify_on_extraction_complete = True
        config.notifications.notify_on_extraction_failed = True
        config.notifications.notify_on_delete_complete = True
        config.notifications.discord_webhook_url = discord_webhook_url
        config.notifications.telegram_bot_token = telegram_bot_token
        config.notifications.telegram_chat_id = telegram_chat_id
        return config

    def _make_notifier(self, **kwargs):
        config = self._make_config(**kwargs)
        logger = logging.getLogger("test_notifier")
        return WebhookNotifier(config, logger)

    def _make_file(self, name="test.txt", state=ModelFile.State.DEFAULT):
        f = ModelFile(name, False)
        f.state = state
        return f

    def test_shutdown_no_threads(self):
        notifier = self._make_notifier()
        notifier.shutdown(timeout=1)

    def test_shutdown_prevents_new_webhooks(self):
        notifier = self._make_notifier()
        notifier.shutdown(timeout=1)

        with patch.object(notifier, "_send_post") as mock_send:
            notifier._fire_webhook("download_complete", "test.txt", "2026-01-01T00:00:00+00:00")
            mock_send.assert_not_called()

    def test_shutdown_waits_for_inflight_sends(self):
        notifier = self._make_notifier()
        barrier = threading.Event()
        started = threading.Event()
        finished = threading.Event()

        def slow_send(*_args):
            started.set()
            barrier.wait(timeout=5)
            finished.set()

        with patch.object(notifier, "_send_post", side_effect=slow_send):
            notifier._fire_webhook("download_complete", "test.txt", "2026-01-01T00:00:00+00:00")
            self.assertTrue(started.wait(timeout=5))

            barrier.set()
            notifier.shutdown(timeout=2)

            self.assertTrue(finished.is_set())

    def test_shutdown_timeout_respected(self):
        notifier = self._make_notifier()
        barrier = threading.Event()
        started = threading.Event()

        def stuck_send(*_args):
            started.set()
            barrier.wait(timeout=10)

        with patch.object(notifier, "_send_post", side_effect=stuck_send):
            notifier._fire_webhook("download_complete", "test.txt", "2026-01-01T00:00:00+00:00")
            self.assertTrue(started.wait(timeout=5))

            start = time.monotonic()
            notifier.shutdown(timeout=0.2)
            elapsed = time.monotonic() - start

            self.assertLess(elapsed, 1.0)

        barrier.set()

    def test_shutdown_completes_after_send_exception(self):
        notifier = self._make_notifier()
        started = threading.Event()

        def failing_send(*_args):
            started.set()
            raise RuntimeError("webhook failed")

        with patch.object(notifier, "_send_post", side_effect=failing_send):
            notifier._fire_webhook("download_complete", "test.txt", "2026-01-01T00:00:00+00:00")
            self.assertTrue(started.wait(timeout=5))

            start = time.monotonic()
            notifier.shutdown(timeout=2)
            elapsed = time.monotonic() - start

            self.assertLess(elapsed, 1.0)

    def test_shutdown_suppresses_all_subsequent_fires(self):
        notifier = self._make_notifier()
        notifier.shutdown(timeout=0)

        with patch.object(notifier, "_send_post") as mock_send:
            for i in range(10):
                notifier._fire_webhook("download_complete", f"file{i}.txt", "2026-01-01T00:00:00+00:00")

            mock_send.assert_not_called()

    def test_total_timeout_not_per_send(self):
        # 4 concurrent hung sends fill the executor; shutdown's deadline must
        # apply to the batch, not per send.
        notifier = self._make_notifier()
        barriers: list[threading.Event] = []
        all_started = threading.Event()
        started_count = 0
        started_lock = threading.Lock()

        def slow_send(*_args):
            nonlocal started_count
            b = threading.Event()
            barriers.append(b)
            with started_lock:
                started_count += 1
                if started_count >= 4:
                    all_started.set()
            b.wait(timeout=10)

        with patch.object(notifier, "_send_post", side_effect=slow_send):
            for i in range(4):
                notifier._fire_webhook("download_complete", f"file{i}.txt", "2026-01-01T00:00:00+00:00")
            self.assertTrue(all_started.wait(timeout=5))

            start = time.monotonic()
            notifier.shutdown(timeout=0.3)
            elapsed = time.monotonic() - start

            self.assertLess(elapsed, 1.0)

        for b in barriers:
            b.set()


class TestWebhookNotifierDispatch(unittest.TestCase):
    """Tests for event dispatch to webhook, Discord, and Telegram."""

    def _make_config(
        self,
        webhook_url="",
        discord_webhook_url="",
        telegram_bot_token="",
        telegram_chat_id="",
    ):
        config = MagicMock()
        config.notifications.webhook_url = webhook_url
        config.notifications.notify_on_download_start = False
        config.notifications.notify_on_download_complete = True
        config.notifications.notify_on_extraction_complete = True
        config.notifications.notify_on_extraction_failed = True
        config.notifications.notify_on_delete_complete = True
        config.notifications.discord_webhook_url = discord_webhook_url
        config.notifications.telegram_bot_token = telegram_bot_token
        config.notifications.telegram_chat_id = telegram_chat_id
        return config

    def _make_notifier(self, **kwargs):
        config = self._make_config(**kwargs)
        logger = logging.getLogger("test_notifier_dispatch")
        return WebhookNotifier(config, logger)

    def _trigger(self, notifier):
        old = ModelFile("test.mkv", False)
        old.state = ModelFile.State.DOWNLOADING
        new = ModelFile("test.mkv", False)
        new.state = ModelFile.State.DOWNLOADED
        notifier.file_updated(old, new)

    def test_webhook_fires_when_configured(self):
        notifier = self._make_notifier(webhook_url="http://hook.test")
        with patch.object(notifier, "_fire_raw") as mock:
            self._trigger(notifier)
            notifier.shutdown(timeout=1)
            mock.assert_called_once()
            self.assertEqual("webhook", mock.call_args[0][0])

    def test_discord_fires_when_configured(self):
        notifier = self._make_notifier(discord_webhook_url="https://discord.com/api/webhooks/123/TOKEN")
        with patch.object(notifier, "_fire_raw") as mock:
            self._trigger(notifier)
            notifier.shutdown(timeout=1)
            mock.assert_called_once()
            self.assertEqual("Discord", mock.call_args[0][0])

    def test_telegram_fires_when_both_token_and_chat_id_set(self):
        notifier = self._make_notifier(telegram_bot_token="tok", telegram_chat_id="123")
        with patch.object(notifier, "_fire_raw") as mock:
            self._trigger(notifier)
            notifier.shutdown(timeout=1)
            mock.assert_called_once()
            self.assertEqual("Telegram", mock.call_args[0][0])

    def test_telegram_skipped_when_token_missing(self):
        notifier = self._make_notifier(telegram_bot_token="", telegram_chat_id="123")
        with patch.object(notifier, "_fire_raw") as mock:
            self._trigger(notifier)
            notifier.shutdown(timeout=1)
            mock.assert_not_called()

    def test_telegram_skipped_when_chat_id_missing(self):
        notifier = self._make_notifier(telegram_bot_token="tok", telegram_chat_id="")
        with patch.object(notifier, "_fire_raw") as mock:
            self._trigger(notifier)
            notifier.shutdown(timeout=1)
            mock.assert_not_called()

    def test_all_three_fire_simultaneously(self):
        notifier = self._make_notifier(
            webhook_url="http://hook.test",
            discord_webhook_url="https://discord.com/api/webhooks/123/TOKEN",
            telegram_bot_token="tok",
            telegram_chat_id="123",
        )
        with patch.object(notifier, "_fire_raw") as mock:
            self._trigger(notifier)
            notifier.shutdown(timeout=1)
            self.assertEqual(3, mock.call_count)
            labels = {call[0][0] for call in mock.call_args_list}
            self.assertEqual({"webhook", "Discord", "Telegram"}, labels)

    def test_nothing_fires_when_event_disabled(self):
        notifier = self._make_notifier(
            webhook_url="http://hook.test",
            discord_webhook_url="https://discord.com/hook",
        )
        notifier._config.notifications.notify_on_download_complete = False
        with patch.object(notifier, "_fire_raw") as mock:
            self._trigger(notifier)
            notifier.shutdown(timeout=1)
            mock.assert_not_called()

    def test_nothing_fires_when_no_channels_configured(self):
        notifier = self._make_notifier()
        with patch.object(notifier, "_fire_raw") as mock:
            self._trigger(notifier)
            notifier.shutdown(timeout=1)
            mock.assert_not_called()


class TestWebhookNotifierDownloadStart(unittest.TestCase):
    """Tests for the download_start event (state → DOWNLOADING)."""

    def _make_config(self, **flags):
        config = MagicMock()
        config.notifications.webhook_url = "http://hook.test"
        config.notifications.notify_on_download_start = flags.get("notify_on_download_start", True)
        config.notifications.notify_on_download_complete = True
        config.notifications.notify_on_extraction_complete = True
        config.notifications.notify_on_extraction_failed = True
        config.notifications.notify_on_delete_complete = True
        config.notifications.discord_webhook_url = ""
        config.notifications.telegram_bot_token = ""
        config.notifications.telegram_chat_id = ""
        return config

    def _make_notifier(self, **flags):
        return WebhookNotifier(self._make_config(**flags), logging.getLogger("test_download_start"))

    def _transition(self, from_state, to_state):
        old = ModelFile("test.mkv", False)
        old.state = from_state
        new = ModelFile("test.mkv", False)
        new.state = to_state
        return old, new

    def test_default_to_downloading_fires_when_enabled(self):
        notifier = self._make_notifier(notify_on_download_start=True)
        old, new = self._transition(ModelFile.State.DEFAULT, ModelFile.State.DOWNLOADING)
        with patch.object(notifier, "_fire_raw") as mock:
            notifier.file_updated(old, new)
            notifier.shutdown(timeout=1)
            mock.assert_called_once()
            # Payload body carries event_type
            body = mock.call_args[0][3]
            self.assertIn(b'"event_type": "download_start"', body)

    def test_queued_to_downloading_fires_when_enabled(self):
        notifier = self._make_notifier(notify_on_download_start=True)
        old, new = self._transition(ModelFile.State.QUEUED, ModelFile.State.DOWNLOADING)
        with patch.object(notifier, "_fire_raw") as mock:
            notifier.file_updated(old, new)
            notifier.shutdown(timeout=1)
            mock.assert_called_once()

    def test_does_not_fire_when_disabled(self):
        notifier = self._make_notifier(notify_on_download_start=False)
        old, new = self._transition(ModelFile.State.DEFAULT, ModelFile.State.DOWNLOADING)
        with patch.object(notifier, "_fire_raw") as mock:
            notifier.file_updated(old, new)
            notifier.shutdown(timeout=1)
            mock.assert_not_called()


class TestWebhookNotifierSchemeGuard(unittest.TestCase):
    """_send_post's http/https allowlist is the SSRF/scheme guard for the
    generic webhook and Discord/Telegram egress. Other tests patch _send_post
    (or _fire_raw) itself, so the rejection branch and the urlopen call are
    otherwise never executed."""

    _LOGGER_NAME = "test_notifier_scheme"

    def _make_notifier(self) -> WebhookNotifier:
        return WebhookNotifier(MagicMock(), logging.getLogger(self._LOGGER_NAME))

    def test_send_post_rejects_non_http_schemes(self):
        for url in ("file:///etc/passwd", "ftp://example.com/payload", "gopher://example.com"):
            with self.subTest(url=url):
                notifier = self._make_notifier()
                with (
                    patch("urllib.request.urlopen") as mock_urlopen,
                    self.assertLogs(self._LOGGER_NAME, level="WARNING") as logs,
                ):
                    notifier._send_post("Webhook", url, {}, b"payload")
                mock_urlopen.assert_not_called()
                self.assertTrue(any("rejected" in line for line in logs.output))

    def test_send_post_allows_http_scheme(self):
        """Sanity check that the guard isn't rejecting everything: a valid
        http:// URL does reach urlopen."""
        notifier = self._make_notifier()
        with patch("urllib.request.urlopen") as mock_urlopen:
            notifier._send_post("Webhook", "http://example.com/hook", {}, b"payload")
        mock_urlopen.assert_called_once()


if __name__ == "__main__":
    unittest.main()
