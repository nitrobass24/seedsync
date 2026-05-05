# Copyright 2017, Inderpreet Singh, All rights reserved.

import logging
import unittest
from unittest.mock import MagicMock, patch

from web.web_app_job import MyWSGIRefServer, WebAppJob, _RequestLoggingMiddleware


class TestWebAppJobSetup(unittest.TestCase):
    """Tests for WebAppJob.setup() — server creation and thread start."""

    def _make_context(self):
        context = MagicMock()
        # Don't attach a StreamHandler — assertLogs() in tests installs its
        # own capture handler, and adding one here would leak across tests
        # (loggers are singletons).
        logger = logging.getLogger("test_web_app_job")
        logger.setLevel(logging.DEBUG)
        context.logger = logger
        context.web_access_logger = logger
        context.config.web.port = 8080
        context.args.debug = False
        return context

    @patch("web.web_app_job.Thread")
    @patch("web.web_app_job.MyWSGIRefServer")
    def test_setup_creates_server_and_starts_thread(self, mock_server_cls, mock_thread_cls):
        """setup() creates server on configured port and starts thread."""
        context = self._make_context()
        web_app = MagicMock()

        job = WebAppJob(context, web_app)
        job.setup()

        mock_server_cls.assert_called_once_with(context.web_access_logger, host="0.0.0.0", port=8080)
        mock_thread_cls.assert_called_once()
        mock_thread_cls.return_value.start.assert_called_once()

    def test_execute_calls_process(self):
        """execute() calls web_app.process()."""
        context = self._make_context()
        web_app = MagicMock()

        job = WebAppJob(context, web_app)
        job.execute()

        web_app.process.assert_called_once()

    @patch("web.web_app_job.Thread")
    @patch("web.web_app_job.MyWSGIRefServer")
    def test_cleanup_stops_server_and_joins_thread(self, mock_server_cls, mock_thread_cls):
        """cleanup() stops server and joins thread without hanging."""
        context = self._make_context()
        web_app = MagicMock()
        mock_thread = mock_thread_cls.return_value

        job = WebAppJob(context, web_app)
        job.setup()
        job.cleanup()

        web_app.stop.assert_called_once()
        mock_server_cls.return_value.stop.assert_called_once()
        mock_thread.join.assert_called_once()


class TestMyWSGIRefServer(unittest.TestCase):
    """Tests for MyWSGIRefServer."""

    def test_stop_on_never_initialized_server_logs_warning(self):
        """Stop on never-initialized server logs warning, doesn't crash."""
        logger = logging.getLogger("test_wsgi_server")
        server = MyWSGIRefServer(logger, host="0.0.0.0", port=8080)

        with self.assertLogs("test_wsgi_server", level="WARNING") as log_ctx:
            server.stop()

        self.assertTrue(any("never initialized" in msg for msg in log_ctx.output))

    def test_quiet_flag_is_true(self):
        """Server has quiet=True to suppress stdout logging."""
        logger = logging.getLogger("test_wsgi_server")
        server = MyWSGIRefServer(logger, host="0.0.0.0", port=8080)
        self.assertTrue(server.quiet)


class TestRequestLoggingMiddleware(unittest.TestCase):
    """Tests for _RequestLoggingMiddleware."""

    def test_logs_method_path_status_duration(self):
        """Middleware logs method, path, status, duration."""
        logger = logging.getLogger("test_request_logging")

        def mock_app(environ, start_response):
            start_response("200 OK", [])
            return [b"ok"]

        middleware = _RequestLoggingMiddleware(mock_app, logger)

        environ = {
            "REQUEST_METHOD": "GET",
            "PATH_INFO": "/test/path",
        }

        def start_response(status, headers, *args):
            pass

        with self.assertLogs("test_request_logging", level="DEBUG") as log_ctx:
            result = list(middleware(environ, start_response))

        self.assertEqual(result, [b"ok"])
        # Some log line should contain method, path, and status. Don't index
        # log_ctx.output[0] — other loggers might emit lines first under load.
        self.assertTrue(any("GET" in o and "/test/path" in o and "200" in o for o in log_ctx.output))

    def test_logs_even_on_app_error(self):
        """Duration is logged even when the app raises."""
        logger = logging.getLogger("test_request_logging_error")

        def failing_app(environ, start_response):
            start_response("500 Internal Server Error", [])
            raise RuntimeError("boom")

        middleware = _RequestLoggingMiddleware(failing_app, logger)

        environ = {
            "REQUEST_METHOD": "POST",
            "PATH_INFO": "/fail",
        }

        def start_response(status, headers, *args):
            pass

        with self.assertLogs("test_request_logging_error", level="DEBUG") as log_ctx:
            with self.assertRaises(RuntimeError):
                list(middleware(environ, start_response))

        # Mirror the happy-path assertion: the error branch should still log
        # the method, path, and status that start_response saw before the raise.
        self.assertTrue(any("POST" in o and "/fail" in o and "500" in o for o in log_ctx.output))
