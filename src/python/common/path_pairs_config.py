# Copyright 2017, Inderpreet Singh, All rights reserved.

import json
import logging
import os
import uuid
from typing import List, Optional

from .persist import Persist, PersistError

_logger = logging.getLogger(__name__)


class PathPair:
    """Represents a single remote-to-local directory mapping."""

    def __init__(self,
                 pair_id: Optional[str] = None,
                 name: str = "",
                 remote_path: str = "",
                 local_path: str = "",
                 enabled: bool = True,
                 auto_queue: bool = True):
        self.id = pair_id or str(uuid.uuid4())
        self.name = name
        self.remote_path = remote_path
        self.local_path = local_path
        self.enabled = enabled
        self.auto_queue = auto_queue

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "remote_path": self.remote_path,
            "local_path": self.local_path,
            "enabled": self.enabled,
            "auto_queue": self.auto_queue,
        }

    @staticmethod
    def from_dict(d: dict) -> "PathPair":
        return PathPair(
            pair_id=d["id"],
            name=d.get("name", ""),
            remote_path=d["remote_path"],
            local_path=d["local_path"],
            enabled=d.get("enabled", True),
            auto_queue=d.get("auto_queue", True),
        )

    def __eq__(self, other):
        if not isinstance(other, PathPair):
            return False
        return self.to_dict() == other.to_dict()

    def __repr__(self):
        return "PathPair({})".format(self.to_dict())


_CURRENT_VERSION = 1


class PathPairsConfig(Persist):
    """
    Manages path_pairs.json configuration file.
    Stores a list of PathPair objects with load/save/migration support.
    """

    def __init__(self):
        self._pairs: List[PathPair] = []

    @property
    def pairs(self) -> List[PathPair]:
        return list(self._pairs)

    @pairs.setter
    def pairs(self, value: List[PathPair]):
        self._pairs = list(value)

    def get_pair(self, pair_id: str) -> Optional[PathPair]:
        for p in self._pairs:
            if p.id == pair_id:
                return p
        return None

    def add_pair(self, pair: PathPair):
        if self.get_pair(pair.id) is not None:
            raise ValueError("PathPair with id '{}' already exists".format(pair.id))
        self._pairs.append(pair)

    def update_pair(self, pair: PathPair):
        for i, p in enumerate(self._pairs):
            if p.id == pair.id:
                self._pairs[i] = pair
                return
        raise ValueError("PathPair with id '{}' not found".format(pair.id))

    def remove_pair(self, pair_id: str):
        self._pairs = [p for p in self._pairs if p.id != pair_id]

    @classmethod
    def from_str(cls, content: str) -> "PathPairsConfig":
        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            raise PersistError("Error parsing PathPairsConfig: {}".format(str(e)))

        config = PathPairsConfig()
        pairs_list = data.get("path_pairs", [])
        for pair_dict in pairs_list:
            config._pairs.append(PathPair.from_dict(pair_dict))
        return config

    def to_str(self) -> str:
        data = {
            "version": _CURRENT_VERSION,
            "path_pairs": [p.to_dict() for p in self._pairs],
        }
        return json.dumps(data, indent=2)

    @staticmethod
    def migrate_from_legacy(remote_path: str, local_path: str) -> "PathPairsConfig":
        """
        Create a PathPairsConfig from legacy single remote_path/local_path
        values in settings.cfg.
        """
        config = PathPairsConfig()
        pair = PathPair(
            name="Default",
            remote_path=remote_path,
            local_path=local_path,
            enabled=True,
            auto_queue=True,
        )
        config._pairs.append(pair)
        return config
