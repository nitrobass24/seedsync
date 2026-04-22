# Copyright 2017, Inderpreet Singh, All rights reserved.


from common import IStatusListener, Status, overrides

from ..serialize import SerializeStatus
from ..utils import StreamQueue
from ..web_app import IStreamHandler


class StatusListener(IStatusListener, StreamQueue[Status]):
    """
    Status listener used by status streams to listen to status updates
    """

    def __init__(self, status: Status):
        super().__init__()
        self.__status = status

    @overrides(IStatusListener)
    def notify(self):
        self.put(self.__status.copy())


class StatusStreamHandler(IStreamHandler):
    def __init__(self, status: Status):
        self.status = status
        self.serialize = SerializeStatus()
        self.status_listener = StatusListener(status)
        self.first_run = True

    @overrides(IStreamHandler)
    def setup(self):
        self.status.add_listener(self.status_listener)

    @overrides(IStreamHandler)
    def get_value(self) -> str | None:
        if self.first_run:
            self.first_run = False
            status = self.status.copy()
            return self.serialize.status(status)
        status = self.status_listener.get_next_event()
        if status is not None:
            return self.serialize.status(status)
        return None

    @overrides(IStreamHandler)
    def cleanup(self):
        if self.status_listener:
            self.status.remove_listener(self.status_listener)
