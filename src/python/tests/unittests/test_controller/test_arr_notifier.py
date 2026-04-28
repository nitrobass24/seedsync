import logging
import threading
import unittest
from unittest.mock import patch

from common import ArrInstance, IntegrationsConfig, PathPair, PathPairsConfig
from controller.arr_notifier import ArrNotifier
from model.file import ModelFile


class TestArrNotifier(unittest.TestCase):
    """Tests for ArrNotifier multi-instance, per-pair routing."""

    def _make_pair(
        self,
        name="TV",
        local_path="/media/tv",
        arr_target_ids: list[str] | None = None,
    ) -> PathPair:
        return PathPair(
            name=name,
            remote_path=f"/remote/{name}",
            local_path=local_path,
            enabled=True,
            auto_queue=True,
            arr_target_ids=list(arr_target_ids) if arr_target_ids else [],
        )

    def _build_notifier(
        self,
        instances: list[ArrInstance] | None = None,
        pairs: list[PathPair] | None = None,
    ) -> tuple[ArrNotifier, IntegrationsConfig, PathPairsConfig]:
        ic = IntegrationsConfig()
        for inst in instances or []:
            ic.add_instance(inst)
        pp = PathPairsConfig()
        for pair in pairs or []:
            pp.add_pair(pair)
        logger = logging.getLogger("test_arr_notifier")
        return ArrNotifier(ic, pp, logger), ic, pp

    def _make_file(
        self,
        name="Show.S01E01.mkv",
        state=ModelFile.State.DEFAULT,
        pair_id: str | None = None,
    ) -> ModelFile:
        f = ModelFile(name, False)
        f.state = state
        if pair_id is not None:
            f.pair_id = pair_id
        return f

    def _trigger(self, notifier: ArrNotifier, pair_id: str | None) -> None:
        old = self._make_file(state=ModelFile.State.DOWNLOADING, pair_id=pair_id)
        new = self._make_file(state=ModelFile.State.DOWNLOADED, pair_id=pair_id)
        notifier.file_updated(old, new)

    # ------------------------------------------------------------------
    # No-op cases
    # ------------------------------------------------------------------
    def test_no_action_when_state_unchanged(self):
        inst = ArrInstance(name="Sonarr", kind="sonarr", url="http://s", api_key="k")
        pair = self._make_pair(arr_target_ids=[inst.id])
        notifier, _, _ = self._build_notifier(instances=[inst], pairs=[pair])

        with patch.object(notifier, "_send_post") as mock_send:
            old = self._make_file(state=ModelFile.State.DOWNLOADED, pair_id=pair.id)
            new = self._make_file(state=ModelFile.State.DOWNLOADED, pair_id=pair.id)
            notifier.file_updated(old, new)
            notifier.shutdown(timeout=2)
            mock_send.assert_not_called()

    def test_no_action_when_state_not_downloaded(self):
        inst = ArrInstance(name="Sonarr", kind="sonarr", url="http://s", api_key="k")
        pair = self._make_pair(arr_target_ids=[inst.id])
        notifier, _, _ = self._build_notifier(instances=[inst], pairs=[pair])

        with patch.object(notifier, "_send_post") as mock_send:
            old = self._make_file(state=ModelFile.State.DOWNLOADED, pair_id=pair.id)
            new = self._make_file(state=ModelFile.State.EXTRACTED, pair_id=pair.id)
            notifier.file_updated(old, new)
            notifier.shutdown(timeout=2)
            mock_send.assert_not_called()

    def test_skips_orphan_file_without_pair(self):
        inst = ArrInstance(name="Sonarr", kind="sonarr", url="http://s", api_key="k")
        notifier, _, _ = self._build_notifier(instances=[inst], pairs=[])

        with patch.object(notifier, "_send_post") as mock_send:
            self._trigger(notifier, pair_id=None)
            notifier.shutdown(timeout=2)
            mock_send.assert_not_called()

    def test_skips_pair_with_empty_target_list(self):
        inst = ArrInstance(name="Sonarr", kind="sonarr", url="http://s", api_key="k")
        pair = self._make_pair(arr_target_ids=[])  # explicit no-op
        notifier, _, _ = self._build_notifier(instances=[inst], pairs=[pair])

        with patch.object(notifier, "_send_post") as mock_send:
            self._trigger(notifier, pair_id=pair.id)
            notifier.shutdown(timeout=2)
            mock_send.assert_not_called()

    def test_unknown_pair_id_is_skipped(self):
        inst = ArrInstance(name="Sonarr", kind="sonarr", url="http://s", api_key="k")
        notifier, _, _ = self._build_notifier(instances=[inst], pairs=[])

        with patch.object(notifier, "_send_post") as mock_send:
            self._trigger(notifier, pair_id="ghost-id")
            notifier.shutdown(timeout=2)
            mock_send.assert_not_called()

    def test_dangling_target_id_is_skipped(self):
        pair = self._make_pair(arr_target_ids=["does-not-exist"])
        notifier, _, _ = self._build_notifier(instances=[], pairs=[pair])

        with patch.object(notifier, "_send_post") as mock_send:
            self._trigger(notifier, pair_id=pair.id)
            notifier.shutdown(timeout=2)
            mock_send.assert_not_called()

    def test_disabled_instance_is_skipped(self):
        inst = ArrInstance(name="Sonarr", kind="sonarr", url="http://s", api_key="k", enabled=False)
        pair = self._make_pair(arr_target_ids=[inst.id])
        notifier, _, _ = self._build_notifier(instances=[inst], pairs=[pair])

        with patch.object(notifier, "_send_post") as mock_send:
            self._trigger(notifier, pair_id=pair.id)
            notifier.shutdown(timeout=2)
            mock_send.assert_not_called()

    def test_instance_missing_url_or_api_key_is_skipped(self):
        no_url = ArrInstance(name="A", kind="sonarr", url="", api_key="k")
        no_key = ArrInstance(name="B", kind="radarr", url="http://r", api_key="")
        pair = self._make_pair(arr_target_ids=[no_url.id, no_key.id])
        notifier, _, _ = self._build_notifier(instances=[no_url, no_key], pairs=[pair])

        with patch.object(notifier, "_send_post") as mock_send:
            self._trigger(notifier, pair_id=pair.id)
            notifier.shutdown(timeout=2)
            mock_send.assert_not_called()

    # ------------------------------------------------------------------
    # Routing cases
    # ------------------------------------------------------------------
    def test_sonarr_fires_with_correct_command(self):
        sonarr = ArrInstance(name="Sonarr — TV", kind="sonarr", url="http://s", api_key="key1")
        pair = self._make_pair(name="TV", local_path="/media/tv", arr_target_ids=[sonarr.id])
        notifier, _, _ = self._build_notifier(instances=[sonarr], pairs=[pair])

        with patch.object(notifier, "_send_post") as mock_send:
            self._trigger(notifier, pair_id=pair.id)
            notifier.shutdown(timeout=2)

            mock_send.assert_called_once()
            args = mock_send.call_args[0]
            service_label, url, api_key, payload = args
            self.assertIn("Sonarr", service_label)
            self.assertEqual(url, "http://s/api/v3/command")
            self.assertEqual(api_key, "key1")
            self.assertEqual(payload["name"], "DownloadedEpisodesScan")
            self.assertEqual(payload["path"], "/media/tv/Show.S01E01.mkv")

    def test_radarr_fires_with_correct_command(self):
        radarr = ArrInstance(name="Radarr — Anime", kind="radarr", url="http://r", api_key="key2")
        pair = self._make_pair(name="Anime", local_path="/media/anime", arr_target_ids=[radarr.id])
        notifier, _, _ = self._build_notifier(instances=[radarr], pairs=[pair])

        with patch.object(notifier, "_send_post") as mock_send:
            self._trigger(notifier, pair_id=pair.id)
            notifier.shutdown(timeout=2)

            args = mock_send.call_args[0]
            self.assertIn("Radarr", args[0])
            self.assertEqual(args[3]["name"], "DownloadedMoviesScan")
            self.assertEqual(args[3]["path"], "/media/anime/Show.S01E01.mkv")

    def test_multiple_targets_attached_to_one_pair(self):
        sonarr = ArrInstance(name="Sonarr — TV", kind="sonarr", url="http://s", api_key="k1")
        radarr = ArrInstance(name="Radarr — Movies", kind="radarr", url="http://r", api_key="k2")
        pair = self._make_pair(arr_target_ids=[sonarr.id, radarr.id])
        notifier, _, _ = self._build_notifier(instances=[sonarr, radarr], pairs=[pair])

        with patch.object(notifier, "_send_post") as mock_send:
            self._trigger(notifier, pair_id=pair.id)
            notifier.shutdown(timeout=2)
            self.assertEqual(mock_send.call_count, 2)
            kinds = {call[0][3]["name"] for call in mock_send.call_args_list}
            self.assertEqual(kinds, {"DownloadedEpisodesScan", "DownloadedMoviesScan"})

    def test_two_pairs_with_distinct_targets(self):
        s_anime = ArrInstance(name="Sonarr — Anime", kind="sonarr", url="http://sa", api_key="k1")
        s_tv = ArrInstance(name="Sonarr — TV", kind="sonarr", url="http://stv", api_key="k2")
        anime_pair = self._make_pair(name="Anime", local_path="/media/anime", arr_target_ids=[s_anime.id])
        tv_pair = self._make_pair(name="TV", local_path="/media/tv", arr_target_ids=[s_tv.id])
        notifier, _, _ = self._build_notifier(instances=[s_anime, s_tv], pairs=[anime_pair, tv_pair])

        with patch.object(notifier, "_send_post") as mock_send:
            self._trigger(notifier, pair_id=anime_pair.id)
            notifier.shutdown(timeout=2)

            mock_send.assert_called_once()
            api_key = mock_send.call_args[0][2]
            path = mock_send.call_args[0][3]["path"]
            self.assertEqual(api_key, "k1")
            self.assertTrue(path.startswith("/media/anime/"))

    def test_url_trailing_slash_is_stripped(self):
        inst = ArrInstance(name="Sonarr", kind="sonarr", url="http://s/", api_key="k")
        pair = self._make_pair(arr_target_ids=[inst.id])
        notifier, _, _ = self._build_notifier(instances=[inst], pairs=[pair])

        with patch.object(notifier, "_send_post") as mock_send:
            self._trigger(notifier, pair_id=pair.id)
            notifier.shutdown(timeout=2)
            self.assertEqual(mock_send.call_args[0][1], "http://s/api/v3/command")

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def test_shutdown_prevents_new_scans(self):
        inst = ArrInstance(name="Sonarr", kind="sonarr", url="http://s", api_key="k")
        pair = self._make_pair(arr_target_ids=[inst.id])
        notifier, _, _ = self._build_notifier(instances=[inst], pairs=[pair])
        notifier.shutdown(timeout=1)

        with patch.object(notifier, "_send_post") as mock_send:
            self._trigger(notifier, pair_id=pair.id)
            mock_send.assert_not_called()

    def test_shutdown_waits_for_inflight(self):
        inst = ArrInstance(name="Sonarr", kind="sonarr", url="http://s", api_key="k")
        pair = self._make_pair(arr_target_ids=[inst.id])
        notifier, _, _ = self._build_notifier(instances=[inst], pairs=[pair])
        barrier = threading.Event()
        started = threading.Event()

        def slow_send(*_args, **_kwargs):
            started.set()
            barrier.wait(timeout=5)

        with patch.object(notifier, "_send_post", side_effect=slow_send):
            self._trigger(notifier, pair_id=pair.id)
            self.assertTrue(started.wait(timeout=5))

            with notifier._lock:
                self.assertEqual(len(notifier._active_threads), 1)

            barrier.set()
            notifier.shutdown(timeout=2)

            with notifier._lock:
                self.assertEqual(len(notifier._active_threads), 0)

    def test_thread_cleaned_up_on_exception(self):
        inst = ArrInstance(name="Sonarr", kind="sonarr", url="http://s", api_key="k")
        pair = self._make_pair(arr_target_ids=[inst.id])
        notifier, _, _ = self._build_notifier(instances=[inst], pairs=[pair])
        started = threading.Event()

        def failing_send(*_args, **_kwargs):
            started.set()
            raise RuntimeError("connection refused")

        with patch.object(notifier, "_send_post", side_effect=failing_send):
            self._trigger(notifier, pair_id=pair.id)
            self.assertTrue(started.wait(timeout=5))
            notifier.shutdown(timeout=2)

            with notifier._lock:
                self.assertEqual(len(notifier._active_threads), 0)


if __name__ == "__main__":
    unittest.main()
