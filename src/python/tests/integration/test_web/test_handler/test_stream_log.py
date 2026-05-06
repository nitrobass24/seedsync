# Copyright 2017, Inderpreet Singh, All rights reserved.

import logging
from threading import Timer
from unittest.mock import patch

from tests.integration.test_web.test_web_app import BaseTestWebApp
from web.handler.stream_log import CachedQueueLogHandler, QueueLogHandler


class TestLogStreamHandler(BaseTestWebApp):
    @patch("web.handler.stream_log.SerializeLogRecord")
    def test_stream_log_serializes_record(self, mock_serialize_log_record_cls):
        # Schedule server stop
        Timer(2.0, self.web_app.stop).start()

        # Schedule status update
        def issue_logs():
            self.context.logger.debug("Debug msg")
            self.context.logger.info("Info msg")
            self.context.logger.warning("Warning msg")
            self.context.logger.error("Error msg")

        Timer(0.3, issue_logs).start()

        # Setup mock serialize instance
        mock_serialize = mock_serialize_log_record_cls.return_value
        mock_serialize.record.return_value = "\n"

        self.test_app.get("/server/stream")
        self.assertEqual(4, len(mock_serialize.record.call_args_list))
        call1, call2, call3, call4 = mock_serialize.record.call_args_list
        record1 = call1[0][0]
        self.assertEqual("Debug msg", record1.msg)
        self.assertEqual(logging.DEBUG, record1.levelno)
        record2 = call2[0][0]
        self.assertEqual("Info msg", record2.msg)
        self.assertEqual(logging.INFO, record2.levelno)
        record3 = call3[0][0]
        self.assertEqual("Warning msg", record3.msg)
        self.assertEqual(logging.WARNING, record3.levelno)
        record4 = call4[0][0]
        self.assertEqual("Error msg", record4.msg)
        self.assertEqual(logging.ERROR, record4.levelno)


class TestLogStreamHandlerCleanup(BaseTestWebApp):
    """Tests for handler attachment and cleanup."""

    def test_queue_handler_attach_remove(self):
        """QueueLogHandler can be attached and removed from logger."""
        logger = self.context.logger
        handler = QueueLogHandler()
        initial_count = len(logger.handlers)

        logger.addHandler(handler)
        self.assertEqual(len(logger.handlers), initial_count + 1)

        logger.removeHandler(handler)
        self.assertEqual(len(logger.handlers), initial_count)

    def test_multiple_handlers_independent(self):
        """Multiple QueueLogHandlers attach/remove independently."""
        logger = self.context.logger
        h1 = QueueLogHandler()
        h2 = QueueLogHandler()

        logger.addHandler(h1)
        logger.addHandler(h2)

        logger.info("test message")

        # Both handlers should have received the message
        r1 = h1.get_next_event()
        r2 = h2.get_next_event()
        self.assertIsNotNone(r1)
        self.assertIsNotNone(r2)
        self.assertEqual(r1.msg, "test message")
        self.assertEqual(r2.msg, "test message")

        # Remove h1, h2 still works
        logger.removeHandler(h1)
        logger.info("second message")

        r1 = h1.get_next_event()
        r2 = h2.get_next_event()
        self.assertIsNone(r1)
        self.assertIsNotNone(r2)
        self.assertEqual(r2.msg, "second message")

        logger.removeHandler(h2)

    def test_cached_handler_delivers_history(self):
        """CachedQueueLogHandler stores records and returns them via get_cached_records()."""
        logger = self.context.logger
        cache = CachedQueueLogHandler(history_size_in_ms=5000)
        logger.addHandler(cache)

        # Log something before the queue handler connects
        logger.info("before connection")

        # Get cached records
        cached = cache.get_cached_records()
        self.assertTrue(any(r.msg == "before connection" for r in cached))

        logger.removeHandler(cache)

    def test_cache_zero_sends_no_history(self):
        """CachedQueueLogHandler with history_size_in_ms=0 sends no historical records."""
        logger = self.context.logger
        cache = CachedQueueLogHandler(history_size_in_ms=0)
        logger.addHandler(cache)

        logger.info("should not be cached")

        cached = cache.get_cached_records()
        self.assertEqual(len(cached), 0)

        logger.removeHandler(cache)
