import logging
import time
import threading
import unittest

from controller.stats_recorder import StatsRecorder
from model.file import ModelFile


class TestStatsRecorder(unittest.TestCase):
    """Tests for StatsRecorder transfer statistics recording."""

    def _make_recorder(self):
        logger = logging.getLogger("test_stats_recorder")
        return StatsRecorder(db_path=":memory:", logger=logger)

    def _make_model_file(self, name="test.mkv", state=ModelFile.State.DEFAULT, remote_size=None, pair_id=None):
        f = ModelFile(name, False, pair_id=pair_id)
        f.state = state
        if remote_size is not None:
            f.remote_size = remote_size
        return f

    def test_success_records_row(self):
        """A DOWNLOADING -> DOWNLOADED transition records a success row."""
        recorder = self._make_recorder()
        old = self._make_model_file(state=ModelFile.State.DOWNLOADING)
        new = self._make_model_file(state=ModelFile.State.DOWNLOADED, remote_size=1024)

        # First trigger DOWNLOADING entry so start time is recorded
        pre = self._make_model_file(state=ModelFile.State.DEFAULT)
        recorder.file_updated(pre, old)

        recorder.file_updated(old, new)

        transfers = recorder.get_transfers(limit=10)
        self.assertEqual(len(transfers), 1)
        self.assertEqual(transfers[0]["filename"], "test.mkv")
        self.assertEqual(transfers[0]["status"], "success")
        self.assertEqual(transfers[0]["size_bytes"], 1024)
        self.assertIsNotNone(transfers[0]["duration_seconds"])
        recorder.shutdown(timeout=1)

    def test_failure_records_row(self):
        """A DOWNLOADING -> DEFAULT transition records a failed row."""
        recorder = self._make_recorder()
        pre = self._make_model_file(state=ModelFile.State.DEFAULT)
        downloading = self._make_model_file(state=ModelFile.State.DOWNLOADING)
        failed = self._make_model_file(state=ModelFile.State.DEFAULT)

        recorder.file_updated(pre, downloading)
        recorder.file_updated(downloading, failed)

        transfers = recorder.get_transfers(limit=10)
        self.assertEqual(len(transfers), 1)
        self.assertEqual(transfers[0]["status"], "failed")
        recorder.shutdown(timeout=1)

    def test_no_record_on_same_state(self):
        """No row is recorded when old and new state are the same."""
        recorder = self._make_recorder()
        old = self._make_model_file(state=ModelFile.State.DOWNLOADED)
        new = self._make_model_file(state=ModelFile.State.DOWNLOADED)

        recorder.file_updated(old, new)

        transfers = recorder.get_transfers(limit=10)
        self.assertEqual(len(transfers), 0)
        recorder.shutdown(timeout=1)

    def test_no_record_on_non_terminal_transition(self):
        """No row is recorded for DOWNLOADED -> EXTRACTED."""
        recorder = self._make_recorder()
        old = self._make_model_file(state=ModelFile.State.DOWNLOADED)
        new = self._make_model_file(state=ModelFile.State.EXTRACTED)

        recorder.file_updated(old, new)

        transfers = recorder.get_transfers(limit=10)
        self.assertEqual(len(transfers), 0)
        recorder.shutdown(timeout=1)

    def test_get_summary_respects_days_window(self):
        """get_summary only counts transfers within the day range."""
        recorder = self._make_recorder()
        # Insert a row directly with a timestamp in the past (8 days ago)
        past_time = time.time() - 8 * 86400
        with recorder._lock:
            recorder._conn.execute(
                "INSERT INTO transfers (filename, pair_id, size_bytes, duration_seconds, completed_at, status) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                ("old.mkv", None, 500, 10.0, past_time, "success"),
            )
            recorder._conn.commit()

        # Insert a recent row via the normal path
        pre = self._make_model_file(name="new.mkv", state=ModelFile.State.DEFAULT, remote_size=2048)
        downloading = self._make_model_file(name="new.mkv", state=ModelFile.State.DOWNLOADING, remote_size=2048)
        done = self._make_model_file(name="new.mkv", state=ModelFile.State.DOWNLOADED, remote_size=2048)
        recorder.file_updated(pre, downloading)
        recorder.file_updated(downloading, done)

        summary = recorder.get_summary(days=7)
        self.assertEqual(summary["total_count"], 1)
        self.assertEqual(summary["success_count"], 1)
        self.assertEqual(summary["total_bytes"], 2048)

        # days=30 should include the old one too
        summary_30 = recorder.get_summary(days=30)
        self.assertEqual(summary_30["total_count"], 2)
        recorder.shutdown(timeout=1)

    def test_get_transfers_respects_limit(self):
        """get_transfers returns at most 'limit' rows."""
        recorder = self._make_recorder()
        for i in range(5):
            pre = self._make_model_file(name=f"file{i}.mkv", state=ModelFile.State.DEFAULT)
            dl = self._make_model_file(name=f"file{i}.mkv", state=ModelFile.State.DOWNLOADING)
            done = self._make_model_file(name=f"file{i}.mkv", state=ModelFile.State.DOWNLOADED, remote_size=100)
            recorder.file_updated(pre, dl)
            recorder.file_updated(dl, done)

        transfers = recorder.get_transfers(limit=3)
        self.assertEqual(len(transfers), 3)
        recorder.shutdown(timeout=1)

    def test_speed_sample_recorded_during_downloading(self):
        """Speed samples are buffered when file is in DOWNLOADING state."""
        recorder = self._make_recorder()
        old = self._make_model_file(state=ModelFile.State.DEFAULT)
        new = self._make_model_file(state=ModelFile.State.DOWNLOADING)
        new.downloading_speed = 5000

        recorder.file_updated(old, new)

        self.assertEqual(len(recorder._speed_buffer), 1)
        self.assertEqual(recorder._speed_buffer[0][1], 5000)
        recorder.shutdown(timeout=1)

    def test_speed_buffer_flushes_to_db(self):
        """Flushing the speed buffer writes buckets to speed_history."""
        recorder = self._make_recorder()
        now = time.time()
        with recorder._lock:
            recorder._speed_buffer.append((now, 1000))
            recorder._speed_buffer.append((now + 1, 2000))
            recorder._speed_buffer.append((now + 61, 3000))  # different minute bucket

        recorder._flush_speed_buffer()

        history = recorder.get_speed_history(hours=1)
        self.assertEqual(len(history), 2)
        # Max of first bucket should be 2000
        speeds = {h["bytes_per_sec"] for h in history}
        self.assertIn(2000, speeds)
        self.assertIn(3000, speeds)
        recorder.shutdown(timeout=1)

    def test_get_speed_history_respects_hours_window(self):
        """get_speed_history only returns samples within the hour range."""
        recorder = self._make_recorder()
        now = time.time()
        old_epoch = int(now - 25 * 3600) // 60 * 60
        recent_epoch = int(now) // 60 * 60

        with recorder._lock:
            recorder._conn.execute(
                "INSERT INTO speed_history (bucket_epoch, bytes_per_sec) VALUES (?, ?)",
                (old_epoch, 1000),
            )
            recorder._conn.execute(
                "INSERT INTO speed_history (bucket_epoch, bytes_per_sec) VALUES (?, ?)",
                (recent_epoch, 2000),
            )
            recorder._conn.commit()

        history = recorder.get_speed_history(hours=24)
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["bytes_per_sec"], 2000)
        recorder.shutdown(timeout=1)

    def test_pair_id_stored(self):
        """pair_id is recorded in the transfer row."""
        recorder = self._make_recorder()
        pre = self._make_model_file(state=ModelFile.State.DEFAULT, pair_id="pair-abc")
        dl = self._make_model_file(state=ModelFile.State.DOWNLOADING, pair_id="pair-abc")
        done = self._make_model_file(state=ModelFile.State.DOWNLOADED, remote_size=512, pair_id="pair-abc")

        recorder.file_updated(pre, dl)
        recorder.file_updated(dl, done)

        transfers = recorder.get_transfers(limit=10)
        self.assertEqual(transfers[0]["pair_id"], "pair-abc")
        recorder.shutdown(timeout=1)

    def test_file_removed_cleans_start_time(self):
        """Removing a file cleans up its start time entry."""
        recorder = self._make_recorder()
        pre = self._make_model_file(state=ModelFile.State.DEFAULT)
        dl = self._make_model_file(state=ModelFile.State.DOWNLOADING)
        recorder.file_updated(pre, dl)

        self.assertIn("test.mkv", recorder._start_times)
        recorder.file_removed(dl)
        self.assertNotIn("test.mkv", recorder._start_times)
        recorder.shutdown(timeout=1)

    def test_concurrent_file_updates(self):
        """Concurrent file_updated calls don't corrupt the database."""
        recorder = self._make_recorder()
        errors = []

        def worker(index):
            try:
                name = f"file{index}.mkv"
                pre = self._make_model_file(name=name, state=ModelFile.State.DEFAULT, remote_size=100)
                dl = self._make_model_file(name=name, state=ModelFile.State.DOWNLOADING, remote_size=100)
                done = self._make_model_file(name=name, state=ModelFile.State.DOWNLOADED, remote_size=100)
                recorder.file_updated(pre, dl)
                recorder.file_updated(dl, done)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        self.assertEqual(len(errors), 0)
        transfers = recorder.get_transfers(limit=100)
        self.assertEqual(len(transfers), 10)
        recorder.shutdown(timeout=1)

    def test_unavailable_recorder_returns_defaults(self):
        """When DB init fails, query methods return empty/zero defaults."""
        logger = logging.getLogger("test_stats_recorder")
        recorder = StatsRecorder(db_path="/nonexistent/path/stats.db", logger=logger)

        self.assertFalse(recorder._available)
        summary = recorder.get_summary()
        self.assertEqual(summary["total_count"], 0)
        self.assertEqual(recorder.get_transfers(), [])
        self.assertEqual(recorder.get_speed_history(), [])
        recorder.shutdown(timeout=1)


if __name__ == "__main__":
    unittest.main()
