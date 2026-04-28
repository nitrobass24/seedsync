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
            notifier._fire_webhook("download_complete", "test.txt")
            mock_send.assert_not_called()

    def test_shutdown_waits_for_inflight_threads(self):
        notifier = self._make_notifier()
        barrier = threading.Event()
        started = threading.Event()

        def slow_send(*_args):
            started.set()
            barrier.wait(timeout=5)

        with patch.object(notifier, "_send_post", side_effect=slow_send):
            notifier._fire_webhook("download_complete", "test.txt")
            started.wait(timeout=5)

            with notifier._lock:
                self.assertEqual(len(notifier._active_threads), 1)

            barrier.set()
            notifier.shutdown(timeout=2)

            with notifier._lock:
                self.assertEqual(len(notifier._active_threads), 0)

    def test_shutdown_timeout_respected(self):
        notifier = self._make_notifier()
        barrier = threading.Event()
        started = threading.Event()

        def stuck_send(*_args):
            started.set()
            barrier.wait(timeout=10)

        with patch.object(notifier, "_send_post", side_effect=stuck_send):
            notifier._fire_webhook("download_complete", "test.txt")
            started.wait(timeout=5)

            start = time.monotonic()
            notifier.shutdown(timeout=0.2)
            elapsed = time.monotonic() - start

            self.assertLess(elapsed, 1.0)

        barrier.set()

    def test_thread_removed_on_exception(self):
        notifier = self._make_notifier()
        started = threading.Event()

        def failing_send(*_args):
            started.set()
            raise RuntimeError("webhook failed")

        with patch.object(notifier, "_send_post", side_effect=failing_send):
            notifier._fire_webhook("download_complete", "test.txt")
            started.wait(timeout=5)
            notifier.shutdown(timeout=2)

            with notifier._lock:
                self.assertEqual(len(notifier._active_threads), 0)

    def test_shutdown_flag_and_registration_atomic(self):
        notifier = self._make_notifier()
        notifier.shutdown(timeout=0)

        with patch.object(notifier, "_send_post") as mock_send:
            for i in range(10):
                notifier._fire_webhook("download_complete", f"file{i}.txt")

            mock_send.assert_not_called()
            with notifier._lock:
                self.assertEqual(len(notifier._active_threads), 0)

    def test_total_timeout_not_per_thread(self):
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
                if started_count >= 5:
                    all_started.set()
            b.wait(timeout=10)

        with patch.object(notifier, "_send_post", side_effect=slow_send):
            for i in range(5):
                notifier._fire_webhook("download_complete", f"file{i}.txt")
            all_started.wait(timeout=5)

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


if __name__ == "__main__":
    unittest.main()
