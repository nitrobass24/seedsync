import collections
import logging
import sqlite3
import threading
import time
from datetime import datetime
from typing import Any

from model import IModelListener, ModelFile


class StatsRecorder(IModelListener):
    """Records completed transfer statistics to SQLite and provides query methods."""

    _SCHEMA = """
        CREATE TABLE IF NOT EXISTS transfers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            pair_id TEXT,
            size_bytes INTEGER,
            duration_seconds REAL,
            completed_at REAL NOT NULL,
            status TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_transfers_completed_at ON transfers(completed_at);

        CREATE TABLE IF NOT EXISTS speed_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bucket_epoch INTEGER NOT NULL,
            bytes_per_sec INTEGER NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_speed_history_bucket ON speed_history(bucket_epoch);
    """

    _FLUSH_INTERVAL_SECS = 60

    def __init__(self, db_path: str, logger: logging.Logger):
        self._logger = logger.getChild("StatsRecorder")
        self._lock = threading.Lock()
        self._available = True
        self._start_times: dict[str, datetime] = {}
        self._speed_buffer: collections.deque[tuple[float, int]] = collections.deque()
        self._stop_event = threading.Event()
        self._conn: sqlite3.Connection | None = None

        try:
            self._conn = sqlite3.connect(db_path, check_same_thread=False)
            self._conn.executescript(self._SCHEMA)
            self._conn.commit()
        except Exception:
            self._logger.exception("Failed to initialize stats database")
            self._available = False
            self._conn = None

        if self._available:
            self._flush_thread = threading.Thread(target=self._flush_loop, daemon=True)
            self._flush_thread.start()
        else:
            self._flush_thread = None

    @staticmethod
    def _file_key(file: ModelFile) -> str:
        if file.pair_id:
            return f"{file.pair_id}:{file.name}"
        return file.name

    def file_added(self, file: ModelFile):
        pass

    def file_removed(self, file: ModelFile):
        with self._lock:
            self._start_times.pop(self._file_key(file), None)

    def file_updated(self, old_file: ModelFile, new_file: ModelFile):
        if not self._available:
            return

        key = self._file_key(new_file)
        old_state = old_file.state
        new_state = new_file.state

        # Entering DOWNLOADING — record start time and speed sample
        if new_state == ModelFile.State.DOWNLOADING:
            with self._lock:
                if old_state != ModelFile.State.DOWNLOADING:
                    self._start_times[key] = datetime.now()
                if new_file.downloading_speed is not None:
                    self._speed_buffer.append((time.time(), new_file.downloading_speed))
            return

        # Terminal state: DOWNLOADED = success
        if new_state == ModelFile.State.DOWNLOADED and old_state != ModelFile.State.DOWNLOADED:
            self._record_transfer(key, new_file, "success")
            return

        # Failed: was DOWNLOADING but went back to DEFAULT
        if old_state == ModelFile.State.DOWNLOADING and new_state == ModelFile.State.DEFAULT:
            self._record_transfer(key, new_file, "failed")
            return

    def _record_transfer(self, key: str, file: ModelFile, status: str) -> None:
        assert self._conn is not None
        now = datetime.now()
        with self._lock:
            start = self._start_times.get(key)
        duration = (now - start).total_seconds() if start else None
        size_bytes = file.remote_size

        with self._lock:
            try:
                self._conn.execute(
                    "INSERT INTO transfers (filename, pair_id, size_bytes, duration_seconds, completed_at, status) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (file.name, file.pair_id, size_bytes, duration, time.time(), status),
                )
                self._conn.commit()
                self._start_times.pop(key, None)
            except Exception:
                self._logger.exception("Failed to record transfer for %s", file.name)

    def _flush_loop(self) -> None:
        while not self._stop_event.wait(self._FLUSH_INTERVAL_SECS):
            self._flush_speed_buffer()

    def _flush_speed_buffer(self) -> None:
        if self._conn is None:
            return
        with self._lock:
            if not self._speed_buffer:
                return
            samples = list(self._speed_buffer)

        # Aggregate into per-minute buckets (max speed per bucket)
        buckets: dict[int, int] = {}
        for epoch, speed in samples:
            bucket = int(epoch) // 60 * 60
            if bucket not in buckets or speed > buckets[bucket]:
                buckets[bucket] = speed

        with self._lock:
            try:
                self._conn.executemany(
                    "INSERT INTO speed_history (bucket_epoch, bytes_per_sec) VALUES (?, ?)",
                    list(buckets.items()),
                )
                self._conn.commit()
                self._speed_buffer.clear()
            except Exception:
                self._logger.exception("Failed to flush speed buffer")

    # --- Query methods (called from HTTP handler threads) ---

    def get_summary(self, days: int = 7) -> dict[str, int]:
        if not self._available or self._conn is None:
            return {"total_count": 0, "success_count": 0, "failed_count": 0, "total_bytes": 0, "avg_speed_bps": 0}

        cutoff = time.time() - days * 86400
        with self._lock:
            row = self._conn.execute(
                """
                SELECT
                    COUNT(*) AS total_count,
                    COALESCE(SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END), 0) AS success_count,
                    COALESCE(SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END), 0) AS failed_count,
                    COALESCE(SUM(CASE WHEN status = 'success' THEN size_bytes ELSE 0 END), 0) AS total_bytes,
                    COALESCE(AVG(CASE WHEN status = 'success' AND duration_seconds > 0
                        THEN size_bytes / duration_seconds END), 0) AS avg_speed_bps
                FROM transfers
                WHERE completed_at > ?
                """,
                (cutoff,),
            ).fetchone()

        return {
            "total_count": row[0],
            "success_count": row[1],
            "failed_count": row[2],
            "total_bytes": row[3],
            "avg_speed_bps": round(row[4]),
        }

    def get_transfers(self, limit: int = 50) -> list[dict[str, Any]]:
        if not self._available or self._conn is None:
            return []

        with self._lock:
            rows = self._conn.execute(
                """
                SELECT id, filename, pair_id, size_bytes, duration_seconds, completed_at, status
                FROM transfers
                ORDER BY completed_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

        return [
            {
                "id": r[0],
                "filename": r[1],
                "pair_id": r[2],
                "size_bytes": r[3],
                "duration_seconds": r[4],
                "completed_at": r[5],
                "status": r[6],
            }
            for r in rows
        ]

    def get_speed_history(self, hours: int = 24) -> list[dict[str, int]]:
        if not self._available or self._conn is None:
            return []

        cutoff = time.time() - hours * 3600
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT bucket_epoch, bytes_per_sec
                FROM speed_history
                WHERE bucket_epoch > ?
                ORDER BY bucket_epoch ASC
                """,
                (cutoff,),
            ).fetchall()

        return [{"bucket_epoch": r[0], "bytes_per_sec": r[1]} for r in rows]

    def shutdown(self, timeout: float = 5) -> None:
        if self._flush_thread is not None:
            self._stop_event.set()
            self._flush_thread.join(timeout=timeout)
            self._flush_speed_buffer()
        if self._conn is not None:
            self._conn.close()
