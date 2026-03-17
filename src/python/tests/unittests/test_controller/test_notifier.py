import logging
import threading
import time
import unittest
from unittest.mock import MagicMock, patch

from controller.notifier import WebhookNotifier


class TestWebhookNotifierShutdown(unittest.TestCase):
    """Tests for WebhookNotifier shutdown drain behavior."""

    def _make_config(self, webhook_url="http://example.com/hook"):
        config = MagicMock()
        config.notifications.webhook_url = webhook_url
        config.notifications.notify_on_download_complete = True
        config.notifications.notify_on_extraction_complete = True
        config.notifications.notify_on_extraction_failed = True
        config.notifications.notify_on_delete_complete = True
        return config

    def _make_notifier(self, **kwargs):
        config = self._make_config(**kwargs)
        logger = logging.getLogger("test_notifier")
        return WebhookNotifier(config, logger)

    def test_shutdown_no_threads(self):
        """Shutdown with no in-flight threads completes immediately."""
        notifier = self._make_notifier()
        notifier.shutdown(timeout=1)
        # Should not raise

    def test_shutdown_prevents_new_webhooks(self):
        """After shutdown, _fire_webhook should not start new threads."""
        notifier = self._make_notifier()
        notifier.shutdown(timeout=1)

        with patch.object(notifier, "_send_post") as mock_send:
            notifier._fire_webhook("download_complete", "test.txt")
            mock_send.assert_not_called()

    def test_shutdown_waits_for_inflight_threads(self):
        """Shutdown joins in-flight threads."""
        notifier = self._make_notifier()
        barrier = threading.Event()
        started = threading.Event()

        def slow_send(url, payload):
            started.set()
            barrier.wait(timeout=5)

        with patch.object(notifier, "_send_post", side_effect=slow_send):
            notifier._fire_webhook("download_complete", "test.txt")
            started.wait(timeout=5)

            with notifier._lock:
                self.assertEqual(len(notifier._active_threads), 1)

            # Release the barrier so shutdown can complete
            barrier.set()
            notifier.shutdown(timeout=2)

            with notifier._lock:
                self.assertEqual(len(notifier._active_threads), 0)

    def test_shutdown_timeout_respected(self):
        """Shutdown returns after timeout even if threads are stuck."""
        notifier = self._make_notifier()
        barrier = threading.Event()
        started = threading.Event()

        def stuck_send(url, payload):
            started.set()
            barrier.wait(timeout=10)

        with patch.object(notifier, "_send_post", side_effect=stuck_send):
            notifier._fire_webhook("download_complete", "test.txt")
            started.wait(timeout=5)

            start = time.monotonic()
            notifier.shutdown(timeout=0.2)
            elapsed = time.monotonic() - start

            # Should return in roughly the timeout period, not 10s
            self.assertLess(elapsed, 1.0)

        # Clean up: release stuck thread
        barrier.set()

    def test_thread_removed_on_exception(self):
        """Thread is removed from _active_threads even if _send_post raises."""
        notifier = self._make_notifier()
        started = threading.Event()

        def failing_send(url, payload):
            started.set()
            raise RuntimeError("webhook failed")

        with patch.object(notifier, "_send_post", side_effect=failing_send):
            notifier._fire_webhook("download_complete", "test.txt")
            started.wait(timeout=5)
            # Give the thread a moment to complete the exception handling
            notifier.shutdown(timeout=2)

            with notifier._lock:
                self.assertEqual(len(notifier._active_threads), 0)

    def test_shutdown_flag_and_registration_atomic(self):
        """No race between shutdown flag check and thread registration.

        After shutdown sets the flag, no new threads should appear in
        _active_threads.
        """
        notifier = self._make_notifier()
        notifier.shutdown(timeout=0)

        with patch.object(notifier, "_send_post") as mock_send:
            # Try to fire multiple webhooks after shutdown
            for i in range(10):
                notifier._fire_webhook("download_complete", f"file{i}.txt")

            mock_send.assert_not_called()
            with notifier._lock:
                self.assertEqual(len(notifier._active_threads), 0)

    def test_total_timeout_not_per_thread(self):
        """Total shutdown time should be bounded by timeout, not timeout * N."""
        notifier = self._make_notifier()
        barriers = []
        all_started = threading.Event()
        started_count = 0
        started_lock = threading.Lock()

        def slow_send(url, payload):
            nonlocal started_count
            b = threading.Event()
            barriers.append(b)
            with started_lock:
                started_count += 1
                if started_count >= 5:
                    all_started.set()
            b.wait(timeout=10)

        with patch.object(notifier, "_send_post", side_effect=slow_send):
            # Fire 5 webhooks
            for i in range(5):
                notifier._fire_webhook("download_complete", f"file{i}.txt")
            all_started.wait(timeout=5)

            start = time.monotonic()
            notifier.shutdown(timeout=0.3)
            elapsed = time.monotonic() - start

            # With 5 threads and 0.3s total timeout, should finish well under 1.5s
            # (would be 1.5s if timeout was per-thread)
            self.assertLess(elapsed, 1.0)

        # Clean up
        for b in barriers:
            b.set()


if __name__ == "__main__":
    unittest.main()
