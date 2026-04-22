import json
import os
import re
from collections import deque

from bottle import HTTPResponse, request

from common import Constants, overrides

from ..web_app import IHandler, WebApp

# Pattern matching the standard log format:
# "2024-01-15 10:30:45,123 - INFO - seedsync (MainProcess/MainThread) - message"
_LOG_PATTERN = re.compile(
    r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3})"  # timestamp
    r" - (\w+)"  # level
    r" - ([\w.]+)"  # logger
    r" \(([^/]+)/([^)]+)\)"  # process/thread
    r" - (.*)$"  # message
)

_VALID_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
_LEVEL_ORDER = {"DEBUG": 0, "INFO": 1, "WARNING": 2, "ERROR": 3, "CRITICAL": 4}


class LogsHandler(IHandler):
    def __init__(self, logdir: str | None, service_name: str):
        self._logdir = logdir
        self._service_name = service_name

    @overrides(IHandler)
    def add_routes(self, web_app: WebApp):
        web_app.add_handler("/server/logs", self._handle_get_logs)

    def _handle_get_logs(self):
        if not self._logdir:
            return HTTPResponse(
                body=json.dumps({"error": "Logging to file is not configured"}),
                status=400,
                content_type="application/json",
            )

        # Parse query params
        search = request.query.get("search", "").strip()  # type: ignore[attr-defined]
        level = request.query.get("level", "").strip().upper()  # type: ignore[attr-defined]
        try:
            limit = int(request.query.get("limit", "500"))  # type: ignore[attr-defined]
        except ValueError:
            limit = 500
        limit = max(1, min(limit, 2000))

        try:
            before = int(request.query.get("before", "0"))  # type: ignore[attr-defined]
        except ValueError:
            before = 0

        min_level = _LEVEL_ORDER.get(level, 0) if level in _VALID_LEVELS else 0

        # Collect log entries from rotated files
        entries = self._read_logs(search, min_level, limit, before)

        return HTTPResponse(body=json.dumps(entries), content_type="application/json")

    def _read_logs(self, search: str, min_level: int, limit: int, before: int) -> list[dict[str, str]]:
        """
        Read log entries from rotated log files without loading any file fully into memory.

        Files are iterated line-by-line (constant memory per file). Only the trailing
        ``limit`` matching entries are retained via a ``deque(maxlen=limit)``. The
        current (in-progress) entry is held outside the deque so that continuation
        lines (tracebacks, multi-line messages) can still be appended to its
        ``message`` field until the next header line flushes it.

        Peak memory is therefore O(limit x avg entry size) rather than
        O(sum of all log file bytes).
        """
        assert self._logdir is not None
        base_path = os.path.join(self._logdir, "{}.log".format(self._service_name))

        # Gather log file paths in oldest -> newest order.
        # RotatingFileHandler convention: on rotation, the current .log is
        # renamed to .log.1, previous .log.1 becomes .log.2, etc. So .log.N is
        # the oldest surviving backup and .log is the currently-active file.
        # Iterate rotated indices in reverse (N .. 1) then append .log last so
        # the deque below naturally retains the *newest* `limit` entries.
        log_files: list[str] = []
        for i in range(Constants.LOG_BACKUP_COUNT, 0, -1):
            rotated = "{}.{}".format(base_path, i)
            if os.path.isfile(rotated):
                log_files.append(rotated)
        if os.path.isfile(base_path):
            log_files.append(base_path)

        # Bounded buffer of the most recent `limit` matching entries. Ordering is
        # preserved (oldest first) across rotated files because log_files is
        # ordered oldest -> newest and files are streamed in order.
        matched: deque[dict[str, str]] = deque(maxlen=limit)
        # `global_entry_idx` counts EVERY completed entry seen (pre-filter). This
        # matches the old implementation's `before` semantics (global index over
        # running entries list, regardless of search/min_level filtering).
        global_entry_idx = 0

        def flush(entry: dict[str, str]) -> None:
            nonlocal global_entry_idx
            global_entry_idx += 1
            if before != 0 and global_entry_idx > before:
                return
            if self._entry_matches(entry, search, min_level):
                matched.append(entry)

        for log_file in log_files:
            try:
                f = open(log_file, encoding="utf-8", errors="replace")
            except OSError:
                continue
            current_entry: dict[str, str] | None = None
            with f:
                for line in f:
                    match = _LOG_PATTERN.match(line)
                    if match:
                        # Header line: flush any previous entry, then start a new one.
                        if current_entry is not None:
                            flush(current_entry)
                            if before != 0 and global_entry_idx >= before:
                                current_entry = None
                                break
                        current_entry = {
                            "timestamp": match.group(1),
                            "level": match.group(2),
                            "logger": match.group(3),
                            "process": match.group(4),
                            "thread": match.group(5),
                            "message": match.group(6),
                        }
                    elif current_entry is not None:
                        # Continuation line (traceback, etc.) — append to current entry.
                        current_entry["message"] += "\n" + line.rstrip()

            # End-of-file flush: preserves old behaviour of flushing each file's
            # final entry before moving on to the next rotated file.
            if current_entry is not None:
                flush(current_entry)

            # Once the pagination cursor is exhausted, no further entry can
            # contribute to the result — stop opening additional rotated files.
            if before != 0 and global_entry_idx >= before:
                break

        return list(matched)

    @staticmethod
    def _entry_matches(entry: dict[str, str], search: str, min_level: int) -> bool:
        if min_level > 0:
            entry_level = _LEVEL_ORDER.get(entry["level"], 0)
            if entry_level < min_level:
                return False
        if search and search.lower() not in entry["message"].lower():
            return False
        return True
