# Copyright 2017, Inderpreet Singh, All rights reserved.

import copy
import os
from collections.abc import Iterator
from dataclasses import dataclass, field, fields
from datetime import datetime
from enum import Enum
from typing import Any, Optional

# Fields that hold byte/second counts and must never go negative.
_NON_NEGATIVE_FIELDS = frozenset({"remote_size", "local_size", "transferred_size", "downloading_speed", "eta"})

# Excluded from __eq__ (in addition to _children/_parent, which are not
# dataclass fields): we don't care about the update timestamp in comparisons.
_EQ_EXCLUDED_FIELDS = frozenset({"update_timestamp"})


@dataclass(eq=False, repr=False)
class ModelFile:
    """
    Represents a file or directory
    The information in this object may be inconsistent. E.g. the size of a directory
    may not match the sum of its children. This is allowed as a source may have
    updated only certain levels in the hierarchy. Specifically for this example,
    an Lftp status provides local sizes for a downloading directory but not its
    children.
    """

    class State(Enum):
        DEFAULT = 0
        DOWNLOADING = 1
        QUEUED = 2
        DOWNLOADED = 3
        DELETED = 4
        EXTRACTING = 5
        EXTRACTED = 6
        EXTRACT_FAILED = 7
        VALIDATING = 8
        VALIDATED = 9
        CORRUPT = 10
        MOVE_FAILED = 11

    name: str  # file or folder name
    is_dir: bool  # True if this is a dir, False if file
    pair_id: str | None = None  # which path pair this file belongs to
    state: State = State.DEFAULT  # status
    remote_size: int | None = None  # remote size in bytes, None if file does not exist
    local_size: int | None = None  # local size in bytes, None if file does not exist
    transferred_size: int | None = None  # transferred size in bytes, None if file does not exist
    downloading_speed: int | None = None  # in bytes / sec, None if not downloading
    eta: int | None = None  # est. time remaining in seconds, None if not available
    is_extractable: bool = False  # whether file is an archive or dir contains archives
    local_created_timestamp: datetime | None = None
    local_modified_timestamp: datetime | None = None
    remote_created_timestamp: datetime | None = None
    remote_modified_timestamp: datetime | None = None
    # timestamp of the latest update; not part of the equality operator
    update_timestamp: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        self._children: list[ModelFile] = []  # children files
        self._parent: ModelFile | None = None  # direct predecessor

    def __setattr__(self, key: str, value: Any):
        if key in _NON_NEGATIVE_FIELDS and value is not None and value < 0:
            raise ValueError(f"{key} must be non-negative")
        super().__setattr__(key, value)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ModelFile):
            return NotImplemented
        # disregard in comparisons:
        #   update_timestamp: we don't care about it
        #   parent: semantics are to check self and children only
        #   children: check these manually for easier debugging
        for f in fields(self):
            if f.name in _EQ_EXCLUDED_FIELDS:
                continue
            if getattr(self, f.name) != getattr(other, f.name):
                return False

        # Check children's properties
        if len(self._children) != len(other._children):
            return False
        my_children_dict = {f.name: f for f in self._children}
        other_children_dict = {f.name: f for f in other._children}
        if my_children_dict.keys() != other_children_dict.keys():
            return False
        return all(my_children_dict[name] == other_children_dict[name] for name in my_children_dict)

    def __repr__(self) -> str:
        return str(self.__dict__)

    @property
    def full_path(self) -> str:
        """Full path including all predecessors"""
        if self._parent:
            return os.path.join(self._parent.full_path, self.name)
        return self.name

    def add_child(self, child_file: "ModelFile"):
        if not self.is_dir:
            raise TypeError("Cannot add child to a non-directory")
        if child_file is self:
            raise ValueError("Cannot add parent as a child")
        if child_file.name in (f.name for f in self._children):
            raise ValueError("Cannot add child more than once")
        self._children.append(child_file)
        child_file._parent = self

    def get_children(self) -> list["ModelFile"]:
        return copy.copy(self._children)

    def iter_children(self) -> Iterator["ModelFile"]:
        # Read-only iterator over the live child list, avoiding the defensive
        # copy that get_children() makes. Callers MUST NOT mutate the child
        # list while iterating. Use get_children() if a snapshot is needed.
        return iter(self._children)

    @property
    def parent(self) -> Optional["ModelFile"]:
        return self._parent
