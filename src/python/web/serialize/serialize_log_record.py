# Copyright 2017, Inderpreet Singh, All rights reserved.

import json
import logging

from .serialize import Serialize


class SerializeLogRecord(Serialize):
    """
    This class defines the serialization interface between python backend
    and the EventSource client frontend for the log stream.
    """

    def __init__(self):
        super().__init__()
        # logging formatter to generate exception traceback
        self.__log_formatter = logging.Formatter()

    def record(self, record: logging.LogRecord) -> str:
        exc_text = None
        if record.exc_text:
            exc_text = record.exc_text
        elif record.exc_info:
            exc_text = self.__log_formatter.formatException(record.exc_info)

        json_dict = {
            "time": str(record.created),
            "level_name": record.levelname,
            "logger_name": record.name,
            "message": record.getMessage(),
            "exc_tb": exc_text,
        }
        return self._sse_pack(event="log-record", data=json.dumps(json_dict))
