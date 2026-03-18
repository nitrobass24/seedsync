# Copyright 2017, Inderpreet Singh, All rights reserved.

import unittest
from unittest.mock import MagicMock, patch

from web.web_app import WebApp


class TestWebStreamHeartbeat(unittest.TestCase):
    """Tests for SSE stream heartbeat behavior."""

    def setUp(self):
        self.context = MagicMock()
        self.context.logger = MagicMock()
        self.context.args.html_path = "/tmp"
        self.controller = MagicMock()
        self.app = WebApp(self.context, self.controller)

    def _make_handler(self, values):
        """Create a mock stream handler that returns values from a list, then None."""
        handler_cls = MagicMock()
        handler_instance = MagicMock()
        handler_instance.get_value.side_effect = list(values) + [None]
        handler_cls.return_value = handler_instance
        return handler_cls, handler_instance

    def test_heartbeat_sent_after_idle_period(self):
        """A heartbeat comment should be emitted after _HEARTBEAT_INTERVAL_IN_SECS of no data."""
        handler_cls, handler_instance = self._make_handler([])
        self.app.add_streaming_handler(handler_cls)

        # Simulate the stream generator with a very short heartbeat interval
        original_interval = WebApp._HEARTBEAT_INTERVAL_IN_SECS
        original_poll = WebApp._STREAM_POLL_INTERVAL_IN_MS
        try:
            WebApp._HEARTBEAT_INTERVAL_IN_SECS = 0  # immediate heartbeat
            WebApp._STREAM_POLL_INTERVAL_IN_MS = 0

            # Call the stream method directly
            # We need to mock bottle.response to avoid errors
            with patch("web.web_app.bottle") as mock_bottle:
                mock_bottle.response = MagicMock()

                # After the first get_value returns None and heartbeat fires,
                # stop the loop
                call_count = [0]
                stop_after = 2  # let it loop twice

                def side_effect_with_stop():
                    call_count[0] += 1
                    if call_count[0] > stop_after:
                        self.app._stop_event.set()
                    return None

                handler_instance.get_value.side_effect = side_effect_with_stop

                gen = self.app._WebApp__web_stream()
                results = list(gen)

            # Should have at least one heartbeat comment
            heartbeats = [r for r in results if r == ": heartbeat\n\n"]
            self.assertGreaterEqual(len(heartbeats), 1)
        finally:
            WebApp._HEARTBEAT_INTERVAL_IN_SECS = original_interval
            WebApp._STREAM_POLL_INTERVAL_IN_MS = original_poll

    def test_no_heartbeat_when_data_flowing(self):
        """No heartbeat should be emitted when data is actively flowing."""
        handler_cls, handler_instance = self._make_handler([])
        self.app.add_streaming_handler(handler_cls)

        original_interval = WebApp._HEARTBEAT_INTERVAL_IN_SECS
        original_poll = WebApp._STREAM_POLL_INTERVAL_IN_MS
        try:
            WebApp._HEARTBEAT_INTERVAL_IN_SECS = 0  # would fire immediately if idle
            WebApp._STREAM_POLL_INTERVAL_IN_MS = 0

            with patch("web.web_app.bottle") as mock_bottle:
                mock_bottle.response = MagicMock()

                # Return data on every call, then stop
                call_count = [0]

                def side_effect_data():
                    call_count[0] += 1
                    if call_count[0] > 3:
                        self.app._stop_event.set()
                        return None
                    return "event: test\ndata: {}\n\n"

                handler_instance.get_value.side_effect = side_effect_data

                gen = self.app._WebApp__web_stream()
                results = list(gen)

            heartbeats = [r for r in results if r == ": heartbeat\n\n"]
            data_events = [r for r in results if r.startswith("event:")]
            self.assertEqual(0, len(heartbeats))
            self.assertGreaterEqual(len(data_events), 1)
        finally:
            WebApp._HEARTBEAT_INTERVAL_IN_SECS = original_interval
            WebApp._STREAM_POLL_INTERVAL_IN_MS = original_poll

    def test_x_accel_buffering_header(self):
        """X-Accel-Buffering header should be set to 'no' to disable proxy buffering."""
        handler_cls, handler_instance = self._make_handler([])
        self.app.add_streaming_handler(handler_cls)

        with patch("web.web_app.bottle") as mock_bottle:
            mock_response = MagicMock()
            mock_bottle.response = mock_response

            # Stop immediately so the while loop never executes
            self.app._stop_event.set()

            gen = self.app._WebApp__web_stream()
            list(gen)

            mock_response.set_header.assert_called_with("X-Accel-Buffering", "no")
