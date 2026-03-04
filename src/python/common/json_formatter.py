import json
import logging
import traceback


class JsonFormatter(logging.Formatter):
    """Structured JSON log formatter."""

    def format(self, record: logging.LogRecord) -> str:
        tb = None
        if record.exc_info and record.exc_info[2]:
            tb = "".join(traceback.format_exception(*record.exc_info))

        log_entry = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "process": record.processName,
            "thread": record.threadName,
        }
        if tb:
            log_entry["traceback"] = tb

        return json.dumps(log_entry)
