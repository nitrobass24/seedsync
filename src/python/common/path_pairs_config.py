# Copyright 2017, Inderpreet Singh, All rights reserved.

import copy
import json
import logging
import threading
import uuid

from .persist import Persist, PersistError

_logger = logging.getLogger(__name__)


class PathPair:
    """Represents a single remote-to-local directory mapping."""

    def __init__(
        self,
        pair_id: str | None = None,
        name: str = "",
        remote_path: str = "",
        local_path: str = "",
        enabled: bool = True,
        auto_queue: bool = True,
    ):
        self.id = pair_id or str(uuid.uuid4())
        self.name = name
        self.remote_path = remote_path
        self.local_path = local_path
        self.enabled = enabled
        self.auto_queue = auto_queue

    def to_dict(self) -> dict[str, str | bool]:
        return {
            "id": self.id,
            "name": self.name,
            "remote_path": self.remote_path,
            "local_path": self.local_path,
            "enabled": self.enabled,
            "auto_queue": self.auto_queue,
        }

    @staticmethod
    def from_dict(d: dict[str, str | bool]) -> "PathPair":
        pair_id = d["id"]
        name = d.get("name", "")
        remote_path = d["remote_path"]
        local_path = d["local_path"]
        enabled = d.get("enabled", True)
        auto_queue = d.get("auto_queue", True)
        if not isinstance(pair_id, str):
            raise TypeError("id must be a string, got {}".format(type(pair_id).__name__))
        if not isinstance(name, str):
            raise TypeError("name must be a string, got {}".format(type(name).__name__))
        if not isinstance(remote_path, str):
            raise TypeError("remote_path must be a string, got {}".format(type(remote_path).__name__))
        if not isinstance(local_path, str):
            raise TypeError("local_path must be a string, got {}".format(type(local_path).__name__))
        if not isinstance(enabled, bool):
            raise TypeError("enabled must be a boolean, got {}".format(type(enabled).__name__))
        if not isinstance(auto_queue, bool):
            raise TypeError("auto_queue must be a boolean, got {}".format(type(auto_queue).__name__))
        return PathPair(
            pair_id=pair_id,
            name=name,
            remote_path=remote_path,
            local_path=local_path,
            enabled=enabled,
            auto_queue=auto_queue,
        )

    def __eq__(self, other: object) -> bool:
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
        self._lock = threading.RLock()
        self._pairs: list[PathPair] = []

    @property
    def pairs(self) -> list[PathPair]:
        with self._lock:
            return [copy.deepcopy(p) for p in self._pairs]

    @pairs.setter
    def pairs(self, value: list[PathPair]):
        with self._lock:
            self._pairs = list(value)

    def get_pair(self, pair_id: str) -> PathPair | None:
        with self._lock:
            for p in self._pairs:
                if p.id == pair_id:
                    return copy.deepcopy(p)
            return None

    def add_pair(self, pair: PathPair):
        with self._lock:
            if any(p.id == pair.id for p in self._pairs):
                raise ValueError("PathPair with id '{}' already exists".format(pair.id))
            if any(p.name == pair.name for p in self._pairs):
                raise ValueError("PathPair with name '{}' already exists".format(pair.name))
            self._pairs.append(pair)

    def update_pair(self, pair: PathPair):
        with self._lock:
            for i, p in enumerate(self._pairs):
                if p.id == pair.id:
                    if any(other.name == pair.name and other.id != pair.id for other in self._pairs):
                        raise ValueError("PathPair with name '{}' already exists".format(pair.name))
                    self._pairs[i] = pair
                    return
            raise ValueError("PathPair with id '{}' not found".format(pair.id))

    def remove_pair(self, pair_id: str):
        with self._lock:
            new_pairs = [p for p in self._pairs if p.id != pair_id]
            if len(new_pairs) == len(self._pairs):
                raise ValueError("PathPair with id '{}' not found".format(pair_id))
            self._pairs = new_pairs

    @classmethod
    def from_str(cls, content: str) -> "PathPairsConfig":
        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            raise PersistError("Error parsing PathPairsConfig: {}".format(str(e))) from e

        if not isinstance(data, dict):
            raise PersistError("Expected JSON object in PathPairsConfig")
        config = PathPairsConfig()
        pairs_list = data.get("path_pairs", [])
        if not isinstance(pairs_list, list):
            raise PersistError("Expected 'path_pairs' to be a list")
        for pair_dict in pairs_list:
            try:
                config.add_pair(PathPair.from_dict(pair_dict))
            except (KeyError, TypeError, ValueError) as e:
                raise PersistError("Malformed path pair entry: {}".format(e)) from e
        return config

    def to_str(self) -> str:
        with self._lock:
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
