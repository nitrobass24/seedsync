# Copyright 2017, Inderpreet Singh, All rights reserved.

from datetime import datetime
from typing import Any


class SystemFile:
    """
    Represents a system file or directory
    """

    def __init__(
        self,
        name: str,
        size: int,
        is_dir: bool = False,
        time_created: datetime | None = None,
        time_modified: datetime | None = None,
    ):
        if size < 0:
            raise ValueError("File size must be non-negative")
        self.__name = name
        self.__size = size  # in bytes
        self.__is_dir = is_dir
        self.__timestamp_created = time_created
        self.__timestamp_modified = time_modified
        self.__children = []

    def __eq__(self, other):
        return self.__dict__ == other.__dict__

    def __repr__(self):
        return str(self.__dict__)

    @property
    def name(self) -> str:
        return self.__name

    @property
    def size(self) -> int:
        return self.__size

    @property
    def is_dir(self) -> bool:
        return self.__is_dir

    @property
    def timestamp_created(self) -> datetime | None:
        return self.__timestamp_created

    @property
    def timestamp_modified(self) -> datetime | None:
        return self.__timestamp_modified

    @property
    def children(self) -> list["SystemFile"]:
        return self.__children

    def add_child(self, file: "SystemFile"):
        if not self.__is_dir:
            raise TypeError("Cannot add children to a file")
        self.__children.append(file)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.__name,
            "size": self.__size,
            "is_dir": self.__is_dir,
            "time_created": self.__timestamp_created.isoformat() if self.__timestamp_created else None,
            "time_modified": self.__timestamp_modified.isoformat() if self.__timestamp_modified else None,
            "children": [child.to_dict() for child in self.__children],
        }

    @staticmethod
    def from_dict(d: dict) -> "SystemFile":
        tc = datetime.fromisoformat(d["time_created"]) if d.get("time_created") else None
        tm = datetime.fromisoformat(d["time_modified"]) if d.get("time_modified") else None
        sf = SystemFile(
            name=d["name"], size=d["size"], is_dir=d.get("is_dir", False), time_created=tc, time_modified=tm
        )
        for child_dict in d.get("children", []):
            sf.add_child(SystemFile.from_dict(child_dict))
        return sf
