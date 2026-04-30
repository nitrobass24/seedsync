# Copyright 2017, Inderpreet Singh, All rights reserved.

import copy
import json
import threading
import uuid
from typing import Any, cast

from .persist import Persist, PersistError

_KINDS = ("sonarr", "radarr")
_CURRENT_VERSION = 1


class ArrInstance:
    """A single Sonarr/Radarr instance the user has configured."""

    KIND_SONARR = "sonarr"
    KIND_RADARR = "radarr"
    ALLOWED_KINDS = _KINDS

    def __init__(
        self,
        instance_id: str | None = None,
        name: str = "",
        kind: str = KIND_SONARR,
        url: str = "",
        api_key: str = "",
        enabled: bool = True,
    ):
        if kind not in _KINDS:
            raise ValueError(f"kind must be one of {_KINDS}, got {kind!r}")
        self.id = instance_id or str(uuid.uuid4())
        self.name = name
        self.kind = kind
        self.url = url
        self.api_key = api_key
        self.enabled = enabled

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "kind": self.kind,
            "url": self.url,
            "api_key": self.api_key,
            "enabled": self.enabled,
        }

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "ArrInstance":
        instance_id = d["id"]
        name = d.get("name", "")
        kind = d.get("kind", "")
        url = d.get("url", "")
        api_key = d.get("api_key", "")
        enabled = d.get("enabled", True)
        for field, value in (
            ("id", instance_id),
            ("name", name),
            ("kind", kind),
            ("url", url),
            ("api_key", api_key),
        ):
            if not isinstance(value, str):
                raise TypeError(f"{field} must be a string, got {type(value).__name__}")
        if not isinstance(enabled, bool):
            raise TypeError(f"enabled must be a boolean, got {type(enabled).__name__}")
        if kind not in _KINDS:
            raise ValueError(f"kind must be one of {_KINDS}, got {kind!r}")
        return ArrInstance(
            instance_id=instance_id,
            name=name,
            kind=kind,
            url=url,
            api_key=api_key,
            enabled=enabled,
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ArrInstance):
            return NotImplemented
        return self.to_dict() == other.to_dict()

    def __repr__(self) -> str:
        d = self.to_dict()
        d["api_key"] = "********" if d["api_key"] else ""
        return f"ArrInstance({d})"


class IntegrationsConfig(Persist):
    """
    Manages integrations.json — the list of configured *arr instances.
    """

    def __init__(self):
        self._lock = threading.RLock()
        self._instances: list[ArrInstance] = []

    @property
    def instances(self) -> list[ArrInstance]:
        with self._lock:
            return [copy.deepcopy(i) for i in self._instances]

    @instances.setter
    def instances(self, value: list[ArrInstance]):
        with self._lock:
            self._instances = list(value)

    def get_instance(self, instance_id: str) -> ArrInstance | None:
        with self._lock:
            for i in self._instances:
                if i.id == instance_id:
                    return copy.deepcopy(i)
            return None

    def add_instance(self, instance: ArrInstance):
        with self._lock:
            if any(i.id == instance.id for i in self._instances):
                raise ValueError(f"ArrInstance with id '{instance.id}' already exists")
            if instance.name and any(i.name == instance.name for i in self._instances):
                raise ValueError(f"ArrInstance with name '{instance.name}' already exists")
            self._instances.append(instance)

    def update_instance(self, instance: ArrInstance):
        with self._lock:
            for idx, existing in enumerate(self._instances):
                if existing.id == instance.id:
                    if instance.name and any(
                        other.name == instance.name and other.id != instance.id for other in self._instances
                    ):
                        raise ValueError(f"ArrInstance with name '{instance.name}' already exists")
                    self._instances[idx] = instance
                    return
            raise ValueError(f"ArrInstance with id '{instance.id}' not found")

    def remove_instance(self, instance_id: str):
        with self._lock:
            new_instances = [i for i in self._instances if i.id != instance_id]
            if len(new_instances) == len(self._instances):
                raise ValueError(f"ArrInstance with id '{instance_id}' not found")
            self._instances = new_instances

    @classmethod
    def from_str(cls, content: str) -> "IntegrationsConfig":
        try:
            raw: Any = json.loads(content)
        except json.JSONDecodeError as e:
            raise PersistError(f"Error parsing IntegrationsConfig: {e!s}") from e

        if not isinstance(raw, dict):
            raise PersistError("Expected JSON object in IntegrationsConfig")
        data = cast(dict[str, Any], raw)
        config = IntegrationsConfig()
        raw_instances = data.get("instances", [])
        if not isinstance(raw_instances, list):
            raise PersistError("Expected 'instances' to be a list")
        for inst_dict in cast(list[dict[str, Any]], raw_instances):
            try:
                config.add_instance(ArrInstance.from_dict(inst_dict))
            except (KeyError, TypeError, ValueError) as e:
                raise PersistError(f"Malformed integrations entry: {e}") from e
        return config

    def to_str(self) -> str:
        with self._lock:
            data = {
                "version": _CURRENT_VERSION,
                "instances": [i.to_dict() for i in self._instances],
            }
        return json.dumps(data, indent=2)

    @staticmethod
    def migrate_from_legacy(
        sonarr_url: str,
        sonarr_api_key: str,
        sonarr_enabled: bool,
        radarr_url: str,
        radarr_api_key: str,
        radarr_enabled: bool,
    ) -> "IntegrationsConfig":
        """Build an IntegrationsConfig from the old flat [Integrations] section.

        Only creates an instance per service that has a URL configured; otherwise
        there's nothing meaningful to migrate.
        """
        config = IntegrationsConfig()
        if sonarr_url:
            config.add_instance(
                ArrInstance(
                    name="Sonarr",
                    kind=ArrInstance.KIND_SONARR,
                    url=sonarr_url,
                    api_key=sonarr_api_key,
                    enabled=sonarr_enabled,
                )
            )
        if radarr_url:
            config.add_instance(
                ArrInstance(
                    name="Radarr",
                    kind=ArrInstance.KIND_RADARR,
                    url=radarr_url,
                    api_key=radarr_api_key,
                    enabled=radarr_enabled,
                )
            )
        return config
