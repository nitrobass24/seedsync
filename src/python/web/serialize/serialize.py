# Copyright 2017, Inderpreet Singh, All rights reserved.

from abc import ABC


class Serialize(ABC):
    """
    Base class for SSE serialization
    """

    # noinspection PyMethodMayBeStatic
    def _sse_pack(self, event: str, data: str) -> str:
        """Pack data in SSE format"""
        buffer = ""
        buffer += f"event: {event}\n"
        buffer += f"data: {data}\n"
        buffer += "\n"
        return buffer
