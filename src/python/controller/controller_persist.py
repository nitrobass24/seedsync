# Copyright 2017, Inderpreet Singh, All rights reserved.

import json
import re

from common import Constants, Persist, PersistError, overrides

# Matches a UUID-style pair_id followed by the legacy ':' separator.
# Used to migrate old persist keys from 'pair_id:name' to 'pair_id\x1fname'.
_LEGACY_KEY_RE = re.compile(
    r"^([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}):(.*)",
    re.IGNORECASE,
)

# The new separator (ASCII Unit Separator) used by _persist_key in controller.py
_KEY_SEP = "\x1f"


class ControllerPersist(Persist):
    """
    Persisting state for controller
    """

    # Keys
    __KEY_DOWNLOADED_FILE_NAMES = "downloaded"
    __KEY_EXTRACTED_FILE_NAMES = "extracted"
    __KEY_EXTRACT_FAILED_FILE_NAMES = "extract_failed"
    __KEY_VALIDATED_FILE_NAMES = "validated"
    __KEY_CORRUPT_FILE_NAMES = "corrupt"

    def __init__(self):
        self.downloaded_file_names = set()
        self.extracted_file_names = set()
        self.extract_failed_file_names = set()
        self.validated_file_names = set()
        self.corrupt_file_names = set()

    @staticmethod
    def _migrate_legacy_keys(keys: set[str]) -> set[str]:
        """Replace legacy 'pair_id:name' keys with 'pair_id\\x1fname' keys."""
        migrated = set()
        for key in keys:
            m = _LEGACY_KEY_RE.match(key)
            if m:
                migrated.add("{}{}{}".format(m.group(1), _KEY_SEP, m.group(2)))
            else:
                migrated.add(key)
        return migrated

    @classmethod
    @overrides(Persist)
    def from_str(cls: type["ControllerPersist"], content: str) -> "ControllerPersist":
        persist = cls()
        try:
            dct = json.loads(content)
            persist.downloaded_file_names = set(dct[ControllerPersist.__KEY_DOWNLOADED_FILE_NAMES])
            persist.extracted_file_names = set(dct[ControllerPersist.__KEY_EXTRACTED_FILE_NAMES])
            persist.extract_failed_file_names = set(dct.get(ControllerPersist.__KEY_EXTRACT_FAILED_FILE_NAMES, []))
            persist.validated_file_names = set(dct.get(ControllerPersist.__KEY_VALIDATED_FILE_NAMES, []))
            persist.corrupt_file_names = set(dct.get(ControllerPersist.__KEY_CORRUPT_FILE_NAMES, []))
            # Migrate any legacy colon-separated keys to unit-separator keys
            persist.downloaded_file_names = ControllerPersist._migrate_legacy_keys(persist.downloaded_file_names)
            persist.extracted_file_names = ControllerPersist._migrate_legacy_keys(persist.extracted_file_names)
            persist.extract_failed_file_names = ControllerPersist._migrate_legacy_keys(
                persist.extract_failed_file_names
            )
            persist.validated_file_names = ControllerPersist._migrate_legacy_keys(persist.validated_file_names)
            persist.corrupt_file_names = ControllerPersist._migrate_legacy_keys(persist.corrupt_file_names)
            return persist
        except (json.decoder.JSONDecodeError, KeyError) as e:
            raise PersistError("Error parsing ControllerPersist - {}: {}".format(type(e).__name__, str(e)))

    @overrides(Persist)
    def to_str(self) -> str:
        dct = dict()
        dct[ControllerPersist.__KEY_DOWNLOADED_FILE_NAMES] = list(self.downloaded_file_names)
        dct[ControllerPersist.__KEY_EXTRACTED_FILE_NAMES] = list(self.extracted_file_names)
        dct[ControllerPersist.__KEY_EXTRACT_FAILED_FILE_NAMES] = list(self.extract_failed_file_names)
        dct[ControllerPersist.__KEY_VALIDATED_FILE_NAMES] = list(self.validated_file_names)
        dct[ControllerPersist.__KEY_CORRUPT_FILE_NAMES] = list(self.corrupt_file_names)
        return json.dumps(dct, indent=Constants.JSON_PRETTY_PRINT_INDENT)
