# Copyright 2017, Inderpreet Singh, All rights reserved.

from __future__ import annotations

import copy
import logging
import time
from threading import Lock
from typing import TYPE_CHECKING, Any, override

from ..serialize import SerializeLogRecord
from ..utils import StreamQueue
from ..web_app import IStreamHandler

if TYPE_CHECKING:
    from ..web_app import WebApp


class CachedQueueLogHandler(logging.Handler):
    """
    A logging.Handler that caches the past X seconds of
    logs
    """

    def __init__(self, history_size_in_ms: int):
        """
        Constructs a CachedQueueLogHandler
        :param history_size_in_ms: history size, set to 0 to disable caching
        """
        super().__init__()
        self.__history_size_in_ms = history_size_in_ms
        self.__cached_records: list[logging.LogRecord] = []
        self.__cache_lock = Lock()

    def get_cached_records(self) -> list[logging.LogRecord]:
        self.__cache_lock.acquire()
        self.__prune_history()
        cache = copy.copy(self.__cached_records)
        self.__cache_lock.release()
        return cache

    @override
    def emit(self, record: logging.LogRecord):
        if self.__history_size_in_ms > 0:
            self.__cache_lock.acquire()
            self.__cached_records.append(record)
            self.__prune_history()
            self.__cache_lock.release()

    def __prune_history(self):
        current_time_in_ms = int(time.time() * 1000)
        history_start_time_in_ms = current_time_in_ms - self.__history_size_in_ms
        self.__cached_records = [r for r in self.__cached_records if 1000.0 * r.created >= history_start_time_in_ms]


class QueueLogHandler(logging.Handler, StreamQueue[logging.LogRecord]):
    """
    A log handler that stored records in a thread-safe queue
    """

    def __init__(self):
        logging.Handler.__init__(self)
        StreamQueue.__init__(self)  # type: ignore[reportUnknownMemberType]

    @override
    def emit(self, record: logging.LogRecord) -> None:
        self.put(record)


class LogStreamHandler(IStreamHandler):
    """
    Streams logs captured after the stream starts.
    Also cache a small history of logs and sends them when the stream
    starts.
    """

    _CACHE_HISTORY_SIZE_IN_MS = 3000

    def __init__(self, logger: logging.Logger, cache: CachedQueueLogHandler):
        self.logger = logger
        self.cache = cache
        self.handler = QueueLogHandler()
        self.serialize = SerializeLogRecord()

    @classmethod
    @override
    def register(cls, web_app: WebApp, **kwargs: Any) -> None:
        # One shared cache, attached to the logger at registration time and
        # handed to every stream instance the web app constructs.
        cache = CachedQueueLogHandler(history_size_in_ms=cls._CACHE_HISTORY_SIZE_IN_MS)
        kwargs["logger"].addHandler(cache)
        super().register(web_app=web_app, cache=cache, **kwargs)

    @override
    def setup(self):
        # Send out all the cached records first
        for record in self.cache.get_cached_records():
            self.handler.emit(record)
        # Then subscribe the live stream
        self.logger.addHandler(self.handler)

    @override
    def get_value(self) -> str | None:
        record = self.handler.get_next_event()
        if record is not None:
            return self.serialize.record(record)
        return None

    @override
    def cleanup(self):
        self.logger.removeHandler(self.handler)
