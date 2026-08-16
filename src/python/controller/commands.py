# Copyright 2017, Inderpreet Singh, All rights reserved.

"""Command types shared between Controller and CommandPipeline.

Extracted from controller.py to break the bidirectional Controller <->
CommandPipeline coupling. Both modules import these symbols directly from
here; Controller additionally re-exports them as class attributes so that
existing `Controller.Command`, `Controller.CommandProcessWrapper`, and
`Controller.MAX_CONCURRENT_COMMAND_PROCESSES` references keep resolving to
the same objects (identity preserved).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from enum import Enum

from common import AppOneShotProcess


class Command:
    """
    Class by which clients of Controller can request Actions to be executed
    Supports callbacks by which clients can be notified of action success/failure
    Note: callbacks will be executed in Controller thread, so any heavy computation
          should be moved out of the callback
    """

    class Action(Enum):
        QUEUE = 0
        STOP = 1
        EXTRACT = 2
        DELETE_LOCAL = 3
        DELETE_REMOTE = 4
        VALIDATE = 5
        CLEANUP_LOCAL = 6

    class ICallback(ABC):
        """Command callback interface"""

        @abstractmethod
        def on_success(self):
            """Called on successful completion of action"""
            pass

        @abstractmethod
        def on_failure(self, error: str):
            """Called on action failure"""
            pass

    def __init__(self, action: Action, filename: str, pair_id: str | None = None):
        self.action = action
        self.filename = filename
        self.pair_id = pair_id
        self.callbacks: list[Command.ICallback] = []

    def add_callback(self, callback: ICallback):
        self.callbacks.append(callback)


class CommandProcessWrapper:
    """
    Wraps any one-shot command processes launched by the controller
    """

    def __init__(self, process: AppOneShotProcess, post_callback: Callable[[], None]):
        self.process = process
        self.post_callback = post_callback


MAX_CONCURRENT_COMMAND_PROCESSES = 8
