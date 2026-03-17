# Copyright 2017, Inderpreet Singh, All rights reserved.

import logging
import time
from socketserver import ThreadingMixIn
from threading import Thread
from wsgiref.simple_server import WSGIRequestHandler, WSGIServer, make_server

import bottle

from common import Context, Job, overrides

from .web_app import WebApp


class WebAppJob(Job):
    """
    Web interface service
    :return:
    """

    def __init__(self, context: Context, web_app: WebApp):
        super().__init__(name=self.__class__.__name__, context=context)
        self.web_access_logger = context.web_access_logger
        self.__context = context
        self.__app = web_app
        self.__server = None
        self.__server_thread = None

    @overrides(Job)
    def setup(self):
        # Note: do not use requestlogger.WSGILogger as it breaks SSE
        self.__server = MyWSGIRefServer(self.web_access_logger, host="0.0.0.0", port=self.__context.config.web.port)
        self.__server_thread = Thread(
            target=bottle.run, kwargs={"app": self.__app, "server": self.__server, "debug": self.__context.args.debug}
        )
        self.__server_thread.start()

    @overrides(Job)
    def execute(self):
        self.__app.process()

    @overrides(Job)
    def cleanup(self):
        self.__app.stop()
        self.__server.stop()
        self.__server_thread.join()


class _ThreadingWSGIServer(ThreadingMixIn, WSGIServer):
    """Multi-threaded WSGI server so SSE connections don't block other requests."""

    daemon_threads = True


class _QuietHandler(WSGIRequestHandler):
    """Suppress default stderr request logging."""

    def log_request(self, *args, **kwargs):
        pass


class _RequestLoggingMiddleware:
    """WSGI middleware that logs request method, path, status, and duration."""

    def __init__(self, app, logger, level=logging.DEBUG):
        self.app = app
        self.logger = logger
        self.level = level

    def __call__(self, environ, start_response):
        method = environ.get("REQUEST_METHOD", "")
        path = environ.get("PATH_INFO", "")
        start = time.monotonic()
        status_code = None

        def _start_response(status, headers, *args):
            nonlocal status_code
            status_code = status.split(" ", 1)[0]
            return start_response(status, headers, *args)

        try:
            return self.app(environ, _start_response)
        finally:
            duration_ms = (time.monotonic() - start) * 1000
            self.logger.log(self.level, "%s %s %s %.1fms", method, path, status_code or "-", duration_ms)


class MyWSGIRefServer(bottle.ServerAdapter):
    """
    Extend bottle's default server to support programatic stopping of server
    Copied from: https://stackoverflow.com/a/16056443
    """

    quiet = True  # disable logging to stdout

    def __init__(self, logger: logging.Logger, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logger = logger
        self.server = None

    @overrides(bottle.ServerAdapter)
    def run(self, handler):
        self.logger.debug("Starting web server")
        handler = _RequestLoggingMiddleware(handler, logger=self.logger, level=logging.DEBUG)
        self.server = make_server(
            self.host, self.port, handler, server_class=_ThreadingWSGIServer, handler_class=_QuietHandler
        )
        self.server.serve_forever()

    def stop(self):
        if self.server is None:
            self.logger.warning("Web server was never initialized; skipping shutdown")
            return
        self.logger.debug("Stopping web server")
        self.server.shutdown()
        self.server.server_close()
