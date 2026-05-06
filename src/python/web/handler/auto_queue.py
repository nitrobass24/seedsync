# Copyright 2017, Inderpreet Singh, All rights reserved.

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

        if aqp in self.__auto_queue_persist.patterns:
            return HTTPResponse(
                body=f"Auto-queue pattern '{pattern}' already exists.",
                status=400,
                content_type="text/plain",
                headers=self._NOSNIFF_HEADERS,
            )
        try:
            self.__auto_queue_persist.add_pattern(aqp)
            self.__auto_queue_persist.to_file(self.__persist_path)
            return HTTPResponse(
                body=f"Added auto-queue pattern '{pattern}'.",
                content_type="text/plain",
                headers=self._NOSNIFF_HEADERS,
            )
        except ValueError as e:
            return HTTPResponse(
                body=str(e),
                status=400,
                content_type="text/plain",
                headers=self._NOSNIFF_HEADERS,
            )

    def __handle_remove_autoqueue(self, pattern: str):
        # value is double encoded
        pattern = unquote(pattern)

        aqp = AutoQueuePattern(pattern=pattern)

        if aqp not in self.__auto_queue_persist.patterns:
            return HTTPResponse(
                body=f"Auto-queue pattern '{pattern}' doesn't exist.",
                status=400,
                content_type="text/plain",
                headers=self._NOSNIFF_HEADERS,
            )
        self.__auto_queue_persist.remove_pattern(aqp)
        self.__auto_queue_persist.to_file(self.__persist_path)
        return HTTPResponse(
            body=f"Removed auto-queue pattern '{pattern}'.",
            content_type="text/plain",
            headers=self._NOSNIFF_HEADERS,
        )
