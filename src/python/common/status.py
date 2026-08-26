# Copyright 2017, Inderpreet Singh, All rights reserved.

from collections.abc import Callable
from dataclasses import dataclass, field, fields
from datetime import datetime
from threading import Lock
from typing import TypeVar

T = TypeVar("T", bound="StatusComponent")

type ComponentListener = Callable[[str], None]


@dataclass(eq=False)
class StatusComponent:
    """
    Base class for status of a single component.
    Assigning any public field notifies listeners with the field name.
    """

    _listeners: list[ComponentListener] = field(default_factory=list[ComponentListener], init=False, repr=False)

    def add_listener(self, listener: ComponentListener):
        if listener not in self._listeners:
            self._listeners.append(listener)

    def remove_listener(self, listener: ComponentListener):
        if listener in self._listeners:
            self._listeners.remove(listener)

    @classmethod
    def copy(cls: type[T], src: T, dst: T) -> None:
        """Copy field values (but not listeners) from src to dst."""
        for f in fields(src):
            if not f.name.startswith("_"):
                setattr(dst, f.name, getattr(src, f.name))

    def __setattr__(self, name: str, value: object):
        object.__setattr__(self, name, value)
        if not name.startswith("_"):
            for listener in self._listeners:
                listener(name)


class Status:
    """
    This class tracks the status of all components across the server
    This is meant to be one-way communication - i.e. only one component
    should set the status

    Clients can use listeners to be notified when values are updated.
    Listeners can be added to the overall status for notification on
    any change, or to each component for component-specific changes.
    """

    # ----- Start of component definition -----
    @dataclass(eq=False)
    class ServerStatus(StatusComponent):
        up: bool = True
        error_msg: str | None = None

    @dataclass(eq=False)
    class ControllerStatus(StatusComponent):
        latest_local_scan_time: datetime | None = None
        latest_remote_scan_time: datetime | None = None
        latest_remote_scan_failed: bool | None = None
        latest_remote_scan_error: str | None = None
        no_enabled_pairs: bool = False

    # ----- End of component definition -----

    def __init__(self):
        self._listeners: list[Callable[[], None]] = []
        self._listeners_lock = Lock()

        # Component initialization
        self.server = Status.ServerStatus()
        self.controller = Status.ControllerStatus()
        self.server.add_listener(self._on_component_changed)
        self.controller.add_listener(self._on_component_changed)

    def __setattr__(self, name: str, value: object):
        """Components can only be set once"""
        if isinstance(getattr(self, name, None), StatusComponent):
            raise ValueError("Cannot reassign component")
        object.__setattr__(self, name, value)

    def _on_component_changed(self, _name: str) -> None:
        """Propagates notifications from component to status listeners"""
        with self._listeners_lock:
            for listener in self._listeners:
                listener()

    def copy(self) -> "Status":
        copy = Status()
        StatusComponent.copy(self.server, copy.server)
        StatusComponent.copy(self.controller, copy.controller)
        return copy

    def add_listener(self, listener: Callable[[], None]):
        with self._listeners_lock:
            if listener not in self._listeners:
                self._listeners.append(listener)

    def remove_listener(self, listener: Callable[[], None]):
        with self._listeners_lock:
            if listener in self._listeners:
                self._listeners.remove(listener)
