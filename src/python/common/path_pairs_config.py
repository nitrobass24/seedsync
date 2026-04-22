# Copyright 2017, Inderpreet Singh, All rights reserved.

import copy
import json
import logging
import threading
import uuid
from typing import Any, cast

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
            raise TypeError(f"id must be a string, got {type(pair_id).__name__}")
        if not isinstance(name, str):
            raise TypeError(f"name must be a string, got {type(name).__name__}")
        if not isinstance(remote_path, str):
            raise TypeError(f"remote_path must be a string, got {type(remote_path).__name__}")
        if not isinstance(local_path, str):
            raise TypeError(f"local_path must be a string, got {type(local_path).__name__}")
        if not isinstance(enabled, bool):
            raise TypeError(f"enabled must be a boolean, got {type(enabled).__name__}")
        if not isinstance(auto_queue, bool):
            raise TypeError(f"auto_queue must be a boolean, got {type(auto_queue).__name__}")
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
            return NotImplemented
        return self.to_dict() == other.to_dict()

    def __repr__(self) -> str:
        return f"PathPair({self.to_dict()})"


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
                raise ValueError(f"PathPair with id '{pair.id}' already exists")
            if any(p.name == pair.name for p in self._pairs):
                raise ValueError(f"PathPair with name '{pair.name}' already exists")
            self._pairs.append(pair)

    def update_pair(self, pair: PathPair):
        with self._lock:
            for i, p in enumerate(self._pairs):
                if p.id == pair.id:
                    if any(other.name == pair.name and other.id != pair.id for other in self._pairs):
                        raise ValueError(f"PathPair with name '{pair.name}' already exists")
                    self._pairs[i] = pair
                    return
            raise ValueError(f"PathPair with id '{pair.id}' not found")

    def remove_pair(self, pair_id: str):
        with self._lock:
            new_pairs = [p for p in self._pairs if p.id != pair_id]
            if len(new_pairs) == len(self._pairs):
                raise ValueError(f"PathPair with id '{pair_id}' not found")
            self._pairs = new_pairs

    @classmethod
    def from_str(cls, content: str) -> "PathPairsConfig":
        try:
            raw: Any = json.loads(content)
        except json.JSONDecodeError as e:
            raise PersistError(f"Error parsing PathPairsConfig: {e!s}") from e

        if not isinstance(raw, dict):
            raise PersistError("Expected JSON object in PathPairsConfig")
        data = cast(dict[str, Any], raw)
        config = PathPairsConfig()
        raw_pairs = data.get("path_pairs", [])
        if not isinstance(raw_pairs, list):
            raise PersistError("Expected 'path_pairs' to be a list")
        pairs_list = cast(list[dict[str, str | bool]], raw_pairs)
        for pair_dict in pairs_list:
            try:
                config.add_pair(PathPair.from_dict(pair_dict))
            except (KeyError, TypeError, ValueError) as e:
                raise PersistError(f"Malformed path pair entry: {e}") from e
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
