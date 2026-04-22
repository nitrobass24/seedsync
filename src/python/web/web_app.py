# Copyright 2017, Inderpreet Singh, All rights reserved.

import threading
import time
from abc import ABC, abstractmethod
from collections.abc import Callable, Iterator
from typing import Any

import bottle
from bottle import static_file

from common import Context
from controller import Controller


class IHandler(ABC):
    """
    Abstract class that defines a web handler
    """

    @abstractmethod
    def add_routes(self, web_app: "WebApp"):
        """
        Add all the handled routes to the given web app
        :param web_app:
        :return:
        """
        pass


class IStreamHandler(ABC):
    """
    Abstract class that defines a streaming data provider
    """

    @abstractmethod
    def setup(self):
        pass

    @abstractmethod
    def get_value(self) -> str | None:
        pass

    @abstractmethod
    def cleanup(self):
        pass

    @classmethod
    def register(cls, web_app: "WebApp", **kwargs: Any) -> None:
        """
        Register this streaming handler with the web app
        :param web_app: web_app instance
        :param kwargs: args for stream handler ctor
        :return:
        """
        web_app.add_streaming_handler(cls, **kwargs)


class WebApp(bottle.Bottle):
    """
    Web app implementation
    """

    _STREAM_POLL_INTERVAL_IN_MS = 250
    _HEARTBEAT_INTERVAL_IN_SECS = 15

    def __init__(self, context: Context, controller: Controller):
        super().__init__()
        self.logger = context.logger.getChild("WebApp")
        self.__controller = controller
        self.__html_path = context.args.html_path
        self.__status = context.status
        self.logger.info(f"Html path set to: {self.__html_path}")
        self._stop_event = threading.Event()
        self._streaming_handlers: list[tuple[type[IStreamHandler], dict[str, Any]]] = []

    def add_default_routes(self):
        """
        Add the default routes. This must be called after all the handlers have
        been added.
        :return:
        """
        # Streaming route
        self.get("/server/stream")(self.__web_stream)  # type: ignore[operator]

        # Front-end routes
        self.route("/")(self.__index)  # type: ignore[operator]
        self.route("/dashboard")(self.__index)  # type: ignore[operator]
        self.route("/settings")(self.__index)  # type: ignore[operator]
        self.route("/autoqueue")(self.__index)  # type: ignore[operator]
        self.route("/logs")(self.__index)  # type: ignore[operator]
        self.route("/about")(self.__index)  # type: ignore[operator]
        # For static files
        self.route("/<file_path:path>")(self.__static)  # type: ignore[operator]

    def add_handler(self, path: str, handler: Callable[..., Any]) -> None:
        self.get(path)(handler)  # type: ignore[operator]

    def add_post_handler(self, path: str, handler: Callable[..., Any]) -> None:
        self.post(path)(handler)  # type: ignore[operator]

    def add_put_handler(self, path: str, handler: Callable[..., Any]) -> None:
        self.put(path)(handler)  # type: ignore[operator]

    def add_delete_handler(self, path: str, handler: Callable[..., Any]) -> None:
        self.delete(path)(handler)  # type: ignore[operator]

    def add_streaming_handler(self, handler: type[IStreamHandler], **kwargs: Any) -> None:
        self._streaming_handlers.append((handler, kwargs))

    def process(self):
        """
        Advance the web app state
        :return:
        """
        pass

    def stop(self):
        """
        Exit gracefully, kill any connections and clean up any state
        :return:
        """
        self._stop_event.set()

    def __index(self):
        """
        Serves the index.html static file
        :return:
        """
        return self.__static("index.html")

    # noinspection PyMethodMayBeStatic
    def __static(self, file_path: str):
        """
        Serves all the static files
        :param file_path:
        :return:
        """
        assert self.__html_path is not None
        return static_file(file_path, root=self.__html_path)

    def __web_stream(self) -> Iterator[str]:
        # Initialize all the handlers
        handlers: list[IStreamHandler] = [cls(**kwargs) for (cls, kwargs) in self._streaming_handlers]

        try:
            # Setup the response header
            bottle.response.content_type = "text/event-stream"
            bottle.response.cache_control = "no-cache"  # type: ignore[assignment]
            bottle.response.set_header("X-Accel-Buffering", "no")

            # Call setup on all handlers
            for handler in handlers:
                handler.setup()

            # Get streaming values until the connection closes
            last_data_time = time.monotonic()
            while not self._stop_event.is_set():
                had_data = False
                for handler in handlers:
                    # Process all values from this handler
                    while True:
                        value = handler.get_value()
                        if value:
                            yield value
                            had_data = True
                        else:
                            break

                if had_data:
                    last_data_time = time.monotonic()
                elif (time.monotonic() - last_data_time) >= WebApp._HEARTBEAT_INTERVAL_IN_SECS:
                    yield ": heartbeat\n\n"
                    last_data_time = time.monotonic()

                time.sleep(WebApp._STREAM_POLL_INTERVAL_IN_MS / 1000)

        finally:
            self.logger.debug(
                "Stream connection stopped by {}".format("server" if self._stop_event.is_set() else "client")
            )

            # Cleanup all handlers
            for handler in handlers:
                handler.cleanup()
