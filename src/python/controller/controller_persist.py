# Copyright 2017, Inderpreet Singh, All rights reserved.

import json
import re
from typing import override

from common import Constants, Persist, PersistError

from .persist_keys import KEY_SEP

# Matches a UUID-style pair_id followed by the legacy ':' separator.
# Used to migrate old persist keys from 'pair_id:name' to 'pair_id\x1fname'.
_LEGACY_KEY_RE = re.compile(
    r"^([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}):(.*)",
    re.IGNORECASE,
)


class ControllerPersist(Persist):
    """
    Persisting state for controller
    """

    # (json key, required) in on-disk order; attribute name is f"{key}_file_names"
    _KEYS = (
        ("downloaded", True),
        ("extracted", True),
        ("extract_failed", False),
        ("validated", False),
        ("corrupt", False),
        ("move_failed", False),
    )

    def __init__(self):
        self.downloaded_file_names: set[str] = set()
        self.extracted_file_names: set[str] = set()
        self.extract_failed_file_names: set[str] = set()
        self.validated_file_names: set[str] = set()
        self.corrupt_file_names: set[str] = set()
        self.move_failed_file_names: set[str] = set()

    def all_sets(self) -> dict[str, set[str]]:
        """The six persisted key sets, keyed by json key."""
        return {key: getattr(self, f"{key}_file_names") for key, _ in self._KEYS}

    @staticmethod
    def _migrate_legacy_keys(keys: set[str]) -> set[str]:
        """Replace legacy 'pair_id:name' keys with 'pair_id\\x1fname' keys."""
        migrated: set[str] = set()
        for key in keys:
            m = _LEGACY_KEY_RE.match(key)
            if m:
                migrated.add(f"{m.group(1)}{KEY_SEP}{m.group(2)}")
            else:
                migrated.add(key)
        return migrated

    @classmethod
    @override
    def from_str(cls: type["ControllerPersist"], content: str) -> "ControllerPersist":
        persist = cls()
        try:
            dct = json.loads(content)
            for key, required in cls._KEYS:
                values = dct[key] if required else dct.get(key, [])
                # Migrate any legacy colon-separated keys to unit-separator keys
                setattr(persist, f"{key}_file_names", cls._migrate_legacy_keys(set(values)))
            return persist
        except (json.decoder.JSONDecodeError, KeyError) as e:
            raise PersistError(f"Error parsing ControllerPersist - {type(e).__name__}: {e!s}") from e

    @override
    def to_str(self) -> str:
        dct = {key: list(values) for key, values in self.all_sets().items()}
        return json.dumps(dct, indent=Constants.JSON_PRETTY_PRINT_INDENT)
