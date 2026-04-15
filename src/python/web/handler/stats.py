import json

from bottle import HTTPResponse, request

from common.types import overrides
from controller.stats_recorder import StatsRecorder

from ..web_app import IHandler, WebApp

_JSON = "application/json"


class StatsHandler(IHandler):
    """Endpoints for transfer statistics."""

    def __init__(self, stats_recorder: StatsRecorder):
        self._stats_recorder = stats_recorder

    @overrides(IHandler)
    def add_routes(self, web_app: WebApp):
        web_app.add_handler("/server/stats/summary", self._handle_summary)
        web_app.add_handler("/server/stats/transfers", self._handle_transfers)
        web_app.add_handler("/server/stats/speed-history", self._handle_speed_history)

    _ALLOWED_DAYS = {7, 30, 90}

    def _handle_summary(self) -> HTTPResponse:
        days = self._parse_int_param("days", default=7, min_val=1, max_val=90)
        if isinstance(days, HTTPResponse):
            return days
        if days not in self._ALLOWED_DAYS:
            return HTTPResponse(
                body=json.dumps({"error": "'days' must be one of 7, 30, or 90"}),
                status=400,
                content_type=_JSON,
            )
        result = self._stats_recorder.get_summary(days=days)
        return HTTPResponse(body=json.dumps(result), content_type=_JSON)

    def _handle_transfers(self) -> HTTPResponse:
        limit = self._parse_int_param("limit", default=50, min_val=1, max_val=200)
        if isinstance(limit, HTTPResponse):
            return limit
        result = self._stats_recorder.get_transfers(limit=limit)
        return HTTPResponse(body=json.dumps(result), content_type=_JSON)

    def _handle_speed_history(self) -> HTTPResponse:
        hours = self._parse_int_param("hours", default=24, min_val=1, max_val=168)
        if isinstance(hours, HTTPResponse):
            return hours
        result = self._stats_recorder.get_speed_history(hours=hours)
        return HTTPResponse(body=json.dumps(result), content_type=_JSON)

    @staticmethod
    def _parse_int_param(name: str, default: int, min_val: int, max_val: int) -> int | HTTPResponse:
        raw = request.query.get(name)  # type: ignore[union-attr]
        if raw is None or raw == "":
            return default
        try:
            value = int(raw)
        except ValueError:
            return HTTPResponse(
                body=json.dumps({"error": f"Invalid value for '{name}': must be an integer"}),
                status=400,
                content_type=_JSON,
            )
        if value < min_val or value > max_val:
            return HTTPResponse(
                body=json.dumps({"error": f"'{name}' must be between {min_val} and {max_val}"}),
                status=400,
                content_type=_JSON,
            )
        return value
