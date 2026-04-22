# Copyright 2017, Inderpreet Singh, All rights reserved.

from enum import Enum
from typing import NamedTuple


class LftpJobStatus:
    """
    Represents the status of a single Lftp jobs
    """

    class Type(Enum):
        MIRROR = "mirror"
        PGET = "pget"

    class State(Enum):
        QUEUED = 0
        RUNNING = 1

    class TransferState(NamedTuple):
        """
        State of transfer for a file or entire download
          size_local: size in bytes that have been downloaded
          size_remote: size in bytes on the remote server (may not be available)
          percent_local: percent of bytes that have been downloaded (0-100)
          speed: transfer speed in bytes per second
          eta: est. remaining transfer time in seconds
        """

        size_local: int | None
        size_remote: int | None
        percent_local: float | None
        speed: int | None
        eta: int | None

    def __init__(self, job_id: int, job_type: Type, state: State, name: str, flags: str):
        self.__id = job_id
        self.__type = job_type
        self.__state = state
        self.__name = name
        self.__flags = flags
        self.__total_transfer_state = LftpJobStatus.TransferState(None, None, None, None, None)
        # dict of active file transfer states, maps filename to their transfer state
        # there's no hierarchical info for now
        self.__active_files_state: dict[str, LftpJobStatus.TransferState] = {}

    @property
    def id(self) -> int:
        return self.__id

    @property
    def type(self) -> Type:
        return self.__type

    @property
    def state(self) -> "LftpJobStatus.State":
        return self.__state

    @property
    def name(self) -> str:
        return self.__name

    @property
    def total_transfer_state(self) -> TransferState:
        return self.__total_transfer_state

    @total_transfer_state.setter
    def total_transfer_state(self, total_transfer_state: TransferState):
        if self.__state == LftpJobStatus.State.QUEUED:
            raise TypeError("Cannot set transfer state on job of type queue")
        self.__total_transfer_state = total_transfer_state

    def add_active_file_transfer_state(self, filename: str, transfer_state: TransferState):
        if self.__state == LftpJobStatus.State.QUEUED:
            raise TypeError("Cannot set transfer state on job of type queue")
        self.__active_files_state[filename] = transfer_state

    def get_active_file_transfer_states(self) -> list[tuple[str, TransferState]]:
        """
        Returns list of pairs (filename, transfer state)
        :return:
        """
        return list(self.__active_files_state.items())

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, LftpJobStatus):
            return NotImplemented
        return self.__dict__ == other.__dict__

    def __str__(self) -> str:
        return str(self.__dict__)

    def __repr__(self) -> str:
        return str(self.__dict__)
