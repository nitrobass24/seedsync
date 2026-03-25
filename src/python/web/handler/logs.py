import json
import os
import re

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
        entries = []
        assert self._logdir is not None
        base_path = os.path.join(self._logdir, "{}.log".format(self._service_name))

        # Gather log file paths: .log, .log.1, .log.2, ... up to backup count
        log_files = []
        if os.path.isfile(base_path):
            log_files.append(base_path)
        for i in range(1, Constants.LOG_BACKUP_COUNT + 1):
            rotated = "{}.{}".format(base_path, i)
            if os.path.isfile(rotated):
                log_files.append(rotated)

        global_line_idx = 0
        for log_file in log_files:
            try:
                with open(log_file, encoding="utf-8", errors="replace") as f:
                    lines = f.readlines()
            except OSError:
                continue

            current_entry = None
            for line in lines:
                match = _LOG_PATTERN.match(line)
                if match:
                    # Flush previous entry
                    if current_entry is not None:
                        global_line_idx += 1
                        if before == 0 or global_line_idx <= before:
                            if self._entry_matches(current_entry, search, min_level):
                                entries.append(current_entry)
                    current_entry = {
                        "timestamp": match.group(1),
                        "level": match.group(2),
                        "logger": match.group(3),
                        "process": match.group(4),
                        "thread": match.group(5),
                        "message": match.group(6),
                    }
                elif current_entry is not None:
                    # Continuation line (traceback, etc.)
                    current_entry["message"] += "\n" + line.rstrip()

            # Flush last entry
            if current_entry is not None:
                global_line_idx += 1
                if before == 0 or global_line_idx <= before:
                    if self._entry_matches(current_entry, search, min_level):
                        entries.append(current_entry)

        # Return the most recent entries (last N)
        if len(entries) > limit:
            entries = entries[-limit:]

        return entries

    @staticmethod
    def _entry_matches(entry: dict[str, str], search: str, min_level: int) -> bool:
        if min_level > 0:
            entry_level = _LEVEL_ORDER.get(entry["level"], 0)
            if entry_level < min_level:
                return False
        if search and search.lower() not in entry["message"].lower():
            return False
        return True
