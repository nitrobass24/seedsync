import logging
import threading
import time
import unittest
from unittest.mock import MagicMock, patch

from controller.arr_notifier import ArrNotifier
from model.file import ModelFile


class TestArrNotifier(unittest.TestCase):
    """Tests for ArrNotifier Sonarr/Radarr integration."""

    def _make_config(
        self,
        sonarr_enabled=False,
        sonarr_url="http://localhost:8989",
        sonarr_api_key="test-sonarr-key",
        radarr_enabled=False,
        radarr_url="http://localhost:7878",
        radarr_api_key="test-radarr-key",
    ):
        config = MagicMock()
        config.integrations.sonarr_enabled = sonarr_enabled
        config.integrations.sonarr_url = sonarr_url
        config.integrations.sonarr_api_key = sonarr_api_key
        config.integrations.radarr_enabled = radarr_enabled
        config.integrations.radarr_url = radarr_url
        config.integrations.radarr_api_key = radarr_api_key
        return config

    def _make_notifier(self, **kwargs):
        config = self._make_config(**kwargs)
        logger = logging.getLogger("test_arr_notifier")
        return ArrNotifier(config, logger)

    def _make_model_file(self, name="test.mkv", state=ModelFile.State.DEFAULT):
        f = ModelFile(name, False)
        f.state = state
        return f

    def test_no_action_when_disabled(self):
        """No scan fires when both Sonarr and Radarr are disabled."""
        notifier = self._make_notifier(sonarr_enabled=False, radarr_enabled=False)
        old_file = self._make_model_file(state=ModelFile.State.DOWNLOADING)
        new_file = self._make_model_file(state=ModelFile.State.DOWNLOADED)

        with patch.object(notifier, "_send_post") as mock_send:
            notifier.file_updated(old_file, new_file)
            # Give threads a moment (there shouldn't be any)
            time.sleep(0.1)
            mock_send.assert_not_called()

    def test_sonarr_fires_on_download_complete(self):
        """Sonarr scan fires when enabled and file transitions to DOWNLOADED."""
        notifier = self._make_notifier(sonarr_enabled=True)
        old_file = self._make_model_file(state=ModelFile.State.DOWNLOADING)
        new_file = self._make_model_file(state=ModelFile.State.DOWNLOADED)

        with patch.object(notifier, "_send_post") as mock_send:
            notifier.file_updated(old_file, new_file)
            notifier.shutdown(timeout=2)
            mock_send.assert_called_once()
            args = mock_send.call_args
            self.assertEqual(args[0][0], "Sonarr")
            self.assertIn("/api/v3/command", args[0][1])
            self.assertEqual(args[0][2], "test-sonarr-key")
            self.assertEqual(args[0][3]["name"], "DownloadedEpisodesScan")

    def test_radarr_fires_on_download_complete(self):
        """Radarr scan fires when enabled and file transitions to DOWNLOADED."""
        notifier = self._make_notifier(radarr_enabled=True)
        old_file = self._make_model_file(state=ModelFile.State.DOWNLOADING)
        new_file = self._make_model_file(state=ModelFile.State.DOWNLOADED)

        with patch.object(notifier, "_send_post") as mock_send:
            notifier.file_updated(old_file, new_file)
            notifier.shutdown(timeout=2)
            mock_send.assert_called_once()
            args = mock_send.call_args
            self.assertEqual(args[0][0], "Radarr")
            self.assertEqual(args[0][3]["name"], "DownloadedMoviesScan")

    def test_both_fire_when_both_enabled(self):
        """Both Sonarr and Radarr fire when both are enabled."""
        notifier = self._make_notifier(sonarr_enabled=True, radarr_enabled=True)
        old_file = self._make_model_file(state=ModelFile.State.DOWNLOADING)
        new_file = self._make_model_file(state=ModelFile.State.DOWNLOADED)

        with patch.object(notifier, "_send_post") as mock_send:
            notifier.file_updated(old_file, new_file)
            notifier.shutdown(timeout=2)
            self.assertEqual(mock_send.call_count, 2)
            service_names = {call[0][0] for call in mock_send.call_args_list}
            self.assertEqual(service_names, {"Sonarr", "Radarr"})

    def test_no_fire_on_non_downloaded_state(self):
        """No scan fires for state transitions other than DOWNLOADED."""
        notifier = self._make_notifier(sonarr_enabled=True, radarr_enabled=True)
        old_file = self._make_model_file(state=ModelFile.State.DOWNLOADED)
        new_file = self._make_model_file(state=ModelFile.State.EXTRACTED)

        with patch.object(notifier, "_send_post") as mock_send:
            notifier.file_updated(old_file, new_file)
            time.sleep(0.1)
            mock_send.assert_not_called()

    def test_no_fire_when_state_unchanged(self):
        """No scan fires when old and new state are the same."""
        notifier = self._make_notifier(sonarr_enabled=True)
        old_file = self._make_model_file(state=ModelFile.State.DOWNLOADED)
        new_file = self._make_model_file(state=ModelFile.State.DOWNLOADED)

        with patch.object(notifier, "_send_post") as mock_send:
            notifier.file_updated(old_file, new_file)
            time.sleep(0.1)
            mock_send.assert_not_called()

    def test_no_fire_when_url_empty(self):
        """No scan fires when URL is empty even if enabled."""
        notifier = self._make_notifier(sonarr_enabled=True, sonarr_url="")
        old_file = self._make_model_file(state=ModelFile.State.DOWNLOADING)
        new_file = self._make_model_file(state=ModelFile.State.DOWNLOADED)

        with patch.object(notifier, "_send_post") as mock_send:
            notifier.file_updated(old_file, new_file)
            time.sleep(0.1)
            mock_send.assert_not_called()

    def test_no_fire_when_api_key_empty(self):
        """No scan fires when API key is empty even if enabled."""
        notifier = self._make_notifier(sonarr_enabled=True, sonarr_api_key="")
        old_file = self._make_model_file(state=ModelFile.State.DOWNLOADING)
        new_file = self._make_model_file(state=ModelFile.State.DOWNLOADED)

        with patch.object(notifier, "_send_post") as mock_send:
            notifier.file_updated(old_file, new_file)
            time.sleep(0.1)
            mock_send.assert_not_called()

    def test_shutdown_prevents_new_scans(self):
        """After shutdown, no new threads are started."""
        notifier = self._make_notifier(sonarr_enabled=True)
        notifier.shutdown(timeout=1)

        with patch.object(notifier, "_send_post") as mock_send:
            old_file = self._make_model_file(state=ModelFile.State.DOWNLOADING)
            new_file = self._make_model_file(state=ModelFile.State.DOWNLOADED)
            notifier.file_updated(old_file, new_file)
            mock_send.assert_not_called()

    def test_shutdown_waits_for_inflight(self):
        """Shutdown joins in-flight threads."""
        notifier = self._make_notifier(sonarr_enabled=True)
        barrier = threading.Event()
        started = threading.Event()

        def slow_send(service, url, api_key, payload):
            started.set()
            barrier.wait(timeout=5)

        with patch.object(notifier, "_send_post", side_effect=slow_send):
            old_file = self._make_model_file(state=ModelFile.State.DOWNLOADING)
            new_file = self._make_model_file(state=ModelFile.State.DOWNLOADED)
            notifier.file_updated(old_file, new_file)
            started.wait(timeout=5)

            with notifier._lock:
                self.assertEqual(len(notifier._active_threads), 1)

            barrier.set()
            notifier.shutdown(timeout=2)

            with notifier._lock:
                self.assertEqual(len(notifier._active_threads), 0)

    def test_thread_removed_on_exception(self):
        """Thread is cleaned up even if _send_post raises."""
        notifier = self._make_notifier(sonarr_enabled=True)
        started = threading.Event()

        def failing_send(service, url, api_key, payload):
            started.set()
            raise RuntimeError("connection refused")

        with patch.object(notifier, "_send_post", side_effect=failing_send):
            old_file = self._make_model_file(state=ModelFile.State.DOWNLOADING)
            new_file = self._make_model_file(state=ModelFile.State.DOWNLOADED)
            notifier.file_updated(old_file, new_file)
            started.wait(timeout=5)
            notifier.shutdown(timeout=2)

            with notifier._lock:
                self.assertEqual(len(notifier._active_threads), 0)

    def test_url_trailing_slash_stripped(self):
        """Trailing slash on URL is handled correctly."""
        notifier = self._make_notifier(sonarr_enabled=True, sonarr_url="http://localhost:8989/")
        old_file = self._make_model_file(state=ModelFile.State.DOWNLOADING)
        new_file = self._make_model_file(state=ModelFile.State.DOWNLOADED)

        with patch.object(notifier, "_send_post") as mock_send:
            notifier.file_updated(old_file, new_file)
            notifier.shutdown(timeout=2)
            url_arg = mock_send.call_args[0][1]
            self.assertEqual(url_arg, "http://localhost:8989/api/v3/command")


if __name__ == "__main__":
    unittest.main()
