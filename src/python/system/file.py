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
        self.name = name
        self.size = size  # in bytes
        self.is_dir = is_dir
        self.timestamp_created = time_created
        self.timestamp_modified = time_modified
        self.children: list[SystemFile] = []

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, SystemFile):
            return NotImplemented
        return self.__dict__ == other.__dict__

    def __repr__(self) -> str:
        return str(self.__dict__)

    def add_child(self, file: "SystemFile"):
        if not self.is_dir:
            raise TypeError("Cannot add children to a file")
        self.children.append(file)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "size": self.size,
            "is_dir": self.is_dir,
            "time_created": self.timestamp_created.isoformat() if self.timestamp_created else None,
            "time_modified": self.timestamp_modified.isoformat() if self.timestamp_modified else None,
            "children": [child.to_dict() for child in self.children],
        }

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "SystemFile":
        tc = datetime.fromisoformat(d["time_created"]) if d.get("time_created") else None
        tm = datetime.fromisoformat(d["time_modified"]) if d.get("time_modified") else None
        sf = SystemFile(
            name=d["name"], size=d["size"], is_dir=d.get("is_dir", False), time_created=tc, time_modified=tm
        )
        for child_dict in d.get("children", []):
            sf.add_child(SystemFile.from_dict(child_dict))
        return sf
