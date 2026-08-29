# Copyright 2017, Inderpreet Singh, All rights reserved.


from typing import override

from common import Status

from ..serialize import SerializeStatus
from ..utils import StreamQueue
from ..web_app import IStreamHandler


class StatusListener(StreamQueue[Status]):
    """
    Status listener used by status streams to listen to status updates
    """

    def __init__(self, status: Status):
        super().__init__()
        self.__status = status

    def notify(self):
        self.put(self.__status.copy())


class StatusStreamHandler(IStreamHandler):
    def __init__(self, status: Status):
        self.status = status
        self.serialize = SerializeStatus()
        self.status_listener = StatusListener(status)
        self.first_run = True

    @override
    def setup(self):
        self.status.add_listener(self.status_listener.notify)

    @override
    def get_value(self) -> str | None:
        if self.first_run:
            self.first_run = False
            status = self.status.copy()
            return self.serialize.status(status)
        status = self.status_listener.get_next_event()
        if status is not None:
            return self.serialize.status(status)
        return None

    @override
    def cleanup(self):
        if self.status_listener:
            self.status.remove_listener(self.status_listener.notify)
