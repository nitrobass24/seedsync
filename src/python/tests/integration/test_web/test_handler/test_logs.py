# Copyright 2017, Inderpreet Singh, All rights reserved.

import json
import os
import tempfile
import tracemalloc

from common import Constants
from tests.integration.test_web.test_web_app import BaseTestWebApp


def _header(ts_seconds: int, level: str, msg: str) -> str:
    """Build a log line matching `_LOG_PATTERN` in logs.py."""
    # Timestamp format: "YYYY-MM-DD HH:MM:SS,mmm"
    # We just vary the seconds/millis to make each entry unique.
    ss = ts_seconds % 60
    mm = (ts_seconds // 60) % 60
    hh = (ts_seconds // 3600) % 24
    return f"2024-01-15 {hh:02d}:{mm:02d}:{ss:02d},000 - {level} - seedsync (MainProcess/MainThread) - {msg}\n"


class TestLogsHandler(BaseTestWebApp):
    def setUp(self):
        super().setUp()
        # The LogsHandler was built in BaseTestWebApp.setUp() using a MagicMock
        # for context.args.logdir. Override with a real temp dir so we can
        # drive the handler with synthetic log files.
        self._tmp_dir_obj = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp_dir_obj.cleanup)
        self.tmp_dir = self._tmp_dir_obj.name
        self.web_app_builder.logs_handler._logdir = self.tmp_dir

    def _log_path(self, suffix: str = "") -> str:
        name = "{}.log".format(Constants.SERVICE_NAME)
        if suffix:
            name = "{}.{}".format(name, suffix)
        return os.path.join(self.tmp_dir, name)

    # ---- correctness tests -------------------------------------------------

    def test_default_returns_last_limit_entries_in_order(self):
        """With no filters, the endpoint returns the last `limit` entries,
        ordered oldest -> newest."""
        total = 1200
        limit = 500
        with open(self._log_path(), "w", encoding="utf-8") as f:
            for i in range(total):
                f.write(_header(i, "INFO", f"msg {i}"))

        resp = self.test_app.get("/server/logs?limit={}".format(limit))
        self.assertEqual(200, resp.status_int)
        entries = json.loads(resp.text)
        self.assertEqual(limit, len(entries))
        # The last `limit` entries, in oldest-first order, are msgs [total-limit .. total-1]
        self.assertEqual("msg {}".format(total - limit), entries[0]["message"])
        self.assertEqual("msg {}".format(total - 1), entries[-1]["message"])

    def test_continuation_lines_attached_to_entry(self):
        """Lines that don't match the header pattern are appended to the
        previous entry's message field (traceback behaviour)."""
        with open(self._log_path(), "w", encoding="utf-8") as f:
            f.write(_header(0, "INFO", "before"))
            f.write(_header(1, "ERROR", "boom"))
            f.write("Traceback (most recent call last):\n")
            f.write('  File "foo.py", line 1, in <module>\n')
            f.write("    raise RuntimeError('x')\n")
            f.write("RuntimeError: x\n")
            f.write(_header(2, "INFO", "after"))

        resp = self.test_app.get("/server/logs?limit=500")
        entries = json.loads(resp.text)
        self.assertEqual(3, len(entries))
        self.assertEqual("before", entries[0]["message"])
        self.assertIn("Traceback", entries[1]["message"])
        self.assertIn("RuntimeError: x", entries[1]["message"])
        self.assertEqual("after", entries[2]["message"])

    def test_rotated_file_ordering_oldest_first(self):
        """.log.N files are older than .log; the response should be ordered
        oldest -> newest across rotated files."""
        with open(self._log_path("2"), "w", encoding="utf-8") as f:
            f.write(_header(0, "INFO", "oldest"))
        with open(self._log_path("1"), "w", encoding="utf-8") as f:
            f.write(_header(1, "INFO", "middle"))
        with open(self._log_path(), "w", encoding="utf-8") as f:
            f.write(_header(2, "INFO", "newest"))

        resp = self.test_app.get("/server/logs?limit=500")
        entries = json.loads(resp.text)
        self.assertEqual(3, len(entries))
        self.assertEqual(
            ["newest", "middle", "oldest"],
            [e["message"] for e in entries],
        )

    def test_min_level_filter(self):
        with open(self._log_path(), "w", encoding="utf-8") as f:
            f.write(_header(0, "DEBUG", "d"))
            f.write(_header(1, "INFO", "i"))
            f.write(_header(2, "WARNING", "w"))
            f.write(_header(3, "ERROR", "e"))

        resp = self.test_app.get("/server/logs?level=WARNING&limit=500")
        entries = json.loads(resp.text)
        self.assertEqual(["w", "e"], [x["message"] for x in entries])

    def test_search_filter(self):
        with open(self._log_path(), "w", encoding="utf-8") as f:
            f.write(_header(0, "INFO", "alpha cat"))
            f.write(_header(1, "INFO", "beta dog"))
            f.write(_header(2, "INFO", "gamma cat"))

        resp = self.test_app.get("/server/logs?search=cat&limit=500")
        entries = json.loads(resp.text)
        self.assertEqual(["alpha cat", "gamma cat"], [x["message"] for x in entries])

    def test_before_cursor_is_global_entry_index(self):
        """`before` is a 1-based cutoff on global entry index (pre-filter).
        Returns entries whose global index <= before."""
        with open(self._log_path(), "w", encoding="utf-8") as f:
            for i in range(10):
                f.write(_header(i, "INFO", f"msg {i}"))

        resp = self.test_app.get("/server/logs?limit=500&before=5")
        entries = json.loads(resp.text)
        # First 5 entries kept: msg 0..msg 4
        self.assertEqual(
            [f"msg {i}" for i in range(5)],
            [x["message"] for x in entries],
        )

    # ---- bounded-memory test ----------------------------------------------

    def test_memory_stays_bounded_for_large_log_file(self):
        """Write a ~20 MB synthetic log file and confirm that servicing one
        request does NOT allocate anywhere close to the file size — which
        would FAIL on the old readlines() implementation.
        """
        path = self._log_path()
        target_bytes = 20 * 1024 * 1024  # 20 MB
        written = 0
        i = 0
        # A typical entry is ~100 bytes. 20 MB ≈ 200k entries.
        with open(path, "w", encoding="utf-8") as f:
            while written < target_bytes:
                line = _header(i, "INFO", f"msg {i:08d}")
                f.write(line)
                written += len(line)
                i += 1
        total_entries = i
        self.assertGreater(total_entries, 150_000)

        # Warm up import / lazy-init overhead so it's not counted.
        self.test_app.get("/server/logs?limit=1")

        # Measure peak traced memory during the request. Using
        # get_traced_memory() (not snapshot diffs) so we catch transient
        # allocations like readlines()' line list that are freed before a
        # post-call snapshot would see them.
        tracemalloc.start()
        try:
            tracemalloc.reset_peak()
            resp = self.test_app.get("/server/logs?limit=500")
            _current, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()

        self.assertEqual(200, resp.status_int)
        entries = json.loads(resp.text)
        self.assertEqual(500, len(entries))
        # Ordering: last 500 of the `total_entries` written, oldest-first.
        self.assertEqual(
            "msg {:08d}".format(total_entries - 500),
            entries[0]["message"],
        )
        self.assertEqual(
            "msg {:08d}".format(total_entries - 1),
            entries[-1]["message"],
        )

        # 10 MB is generous. On the old readlines() implementation this
        # allocates >100 MB for a 20 MB file (all line strings held at once).
        self.assertLess(
            peak,
            10 * 1024 * 1024,
            "peak traced allocation was {} bytes (>= 10 MB); streaming is broken".format(peak),
        )
