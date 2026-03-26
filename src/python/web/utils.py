# Copyright 2017, Inderpreet Singh, All rights reserved.

from __future__ import annotations

from queue import Empty, Queue
from typing import Generic, TypeVar

T = TypeVar("T")


class StreamQueue(Generic[T]):
    """
    A queue that transfers events from one thread to another.
    Useful for web streams that wait for listener events from other threads.
    The producer thread calls put() to insert events. The consumer stream
    calls get_next_event() to receive event in its own thread.
    """

    def __init__(self):
        self.__queue: Queue[T] = Queue()

    def put(self, event: T):
        self.__queue.put(event)

    def get_next_event(self) -> T | None:
        """
        Returns the next event if there is one, otherwise returns None
        :return:
        """
        try:
            return self.__queue.get(block=False)
        except Empty:
            return None
