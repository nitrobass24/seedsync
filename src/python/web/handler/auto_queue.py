# Copyright 2017, Inderpreet Singh, All rights reserved.

import logging
import threading
from urllib.parse import unquote

from bottle import HTTPResponse

from common import overrides
from controller import AutoQueuePattern, AutoQueuePersist

from ..serialize import SerializeAutoQueue
from ..web_app import IHandler, WebApp


class AutoQueueHandler(IHandler):
    _NOSNIFF_HEADERS = {"X-Content-Type-Options": "nosniff"}

    def __init__(self, auto_queue_persist: AutoQueuePersist, persist_path: str):
        self.__auto_queue_persist = auto_queue_persist
        self.__persist_path = persist_path
        self.__logger = logging.getLogger(self.__class__.__name__)
        # Serializes the mutate → persist → rollback sequence in the add/remove
        # handlers (mirrors ConfigHandler). add_pattern/remove_pattern fire
        # listener side effects (AutoQueuePersistListener.new_patterns drives a
        # queue replay on the next controller cycle), so a persist failure must
        # roll back both __patterns and the listener state atomically. Without
        # the lock, two concurrent writers could interleave mutate/persist/
        # rollback and leave on-disk and in-memory state diverged.
        self.__write_lock = threading.Lock()

    @overrides(IHandler)
    def add_routes(self, web_app: WebApp):
        web_app.add_handler("/server/autoqueue/get", self.__handle_get_autoqueue)
        web_app.add_handler("/server/autoqueue/add/<pattern>", self.__handle_add_autoqueue)
        web_app.add_handler("/server/autoqueue/remove/<pattern>", self.__handle_remove_autoqueue)

    def __handle_get_autoqueue(self):
        patterns = list(self.__auto_queue_persist.patterns)
        patterns.sort(key=lambda p: p.pattern)
        out_json = SerializeAutoQueue.patterns(patterns)
        return HTTPResponse(body=out_json, content_type="application/json", headers=self._NOSNIFF_HEADERS)

    def __handle_add_autoqueue(self, pattern: str):
        # value is double encoded
        pattern = unquote(pattern)

        aqp = AutoQueuePattern(pattern=pattern)

        # Hold __write_lock across the existence check AND the mutate → persist →
        # rollback sequence so the test-and-set is atomic: two concurrent adds of
        # the same pattern can't both pass the "already exists" check. add_pattern
        # fires pattern_added, which the AutoQueuePersistListener records in
        # new_patterns and the controller replays against all model files on the
        # next cycle (auto-queueing matching files). If persisting fails we MUST
        # undo that side effect, otherwise the pattern would auto-queue files this
        # session yet be gone on restart — "phantom" queueing that contradicts the
        # 500 (see #518).
        with self.__write_lock:
            if aqp in self.__auto_queue_persist.patterns:
                return HTTPResponse(
                    body=f"Auto-queue pattern '{pattern}' already exists.",
                    status=400,
                    content_type="text/plain",
                    headers=self._NOSNIFF_HEADERS,
                )
            try:
                self.__auto_queue_persist.add_pattern(aqp)
            except ValueError as e:
                return HTTPResponse(
                    body=str(e),
                    status=400,
                    content_type="text/plain",
                    headers=self._NOSNIFF_HEADERS,
                )
            try:
                self.__auto_queue_persist.to_file(self.__persist_path)
            except Exception:
                # Roll back on ANY persist failure (not just OSError — e.g. a
                # to_str()/serialization error). remove_pattern fires
                # pattern_removed, which discards the pattern from the listener's
                # new_patterns, undoing the side effect above so disk and memory
                # stay consistent.
                self.__auto_queue_persist.remove_pattern(aqp)
                self.__logger.exception("Failed to persist auto-queue after adding pattern %r", pattern)
                return HTTPResponse(
                    body="Failed to persist auto-queue",
                    status=500,
                    content_type="text/plain",
                    headers=self._NOSNIFF_HEADERS,
                )
        return HTTPResponse(
            body=f"Added auto-queue pattern '{pattern}'.",
            content_type="text/plain",
            headers=self._NOSNIFF_HEADERS,
        )

    def __handle_remove_autoqueue(self, pattern: str):
        # value is double encoded
        pattern = unquote(pattern)

        aqp = AutoQueuePattern(pattern=pattern)

        # Hold __write_lock across the existence check AND the mutate → persist →
        # rollback sequence so the test-and-set is atomic (see __handle_add_autoqueue).
        with self.__write_lock:
            if aqp not in self.__auto_queue_persist.patterns:
                return HTTPResponse(
                    body=f"Auto-queue pattern '{pattern}' doesn't exist.",
                    status=400,
                    content_type="text/plain",
                    headers=self._NOSNIFF_HEADERS,
                )
            self.__auto_queue_persist.remove_pattern(aqp)
            try:
                self.__auto_queue_persist.to_file(self.__persist_path)
            except Exception:
                # Roll back on ANY persist failure: re-add the pattern so
                # in-memory state matches the on-disk file (the pattern was
                # persisted before this removal).
                self.__auto_queue_persist.add_pattern(aqp)
                self.__logger.exception("Failed to persist auto-queue after removing pattern %r", pattern)
                return HTTPResponse(
                    body="Failed to persist auto-queue",
                    status=500,
                    content_type="text/plain",
                    headers=self._NOSNIFF_HEADERS,
                )
        return HTTPResponse(
            body=f"Removed auto-queue pattern '{pattern}'.",
            content_type="text/plain",
            headers=self._NOSNIFF_HEADERS,
        )
