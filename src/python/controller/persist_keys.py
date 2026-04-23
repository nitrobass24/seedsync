# Copyright 2017, Inderpreet Singh, All rights reserved.

"""Persist key construction and parsing.

Persist keys namespace file names by pair_id using an ASCII Unit Separator
(\\x1f) delimiter. These functions are used by both controller.py and
controller_persist.py. Extracted from controller.py as part of the
controller decomposition (#394 Phase 1B).
"""

# ASCII Unit Separator — safe composite-key delimiter that cannot appear in filenames
KEY_SEP = "\x1f"


def persist_key(pair_id: str | None, name: str) -> str:
    """Build a namespaced persist key: 'pair_id<US>name' or plain 'name' for default pair."""
    return f"{pair_id}{KEY_SEP}{name}" if pair_id else name


def strip_persist_key(key: str, pair_id: str | None) -> str:
    """Strip pair_id prefix from a persist key to get the bare file name.

    Handles both the current unit-separator (\\x1f) and the legacy colon (':')
    delimiter so that old persisted keys are still correctly parsed.
    """
    if not pair_id:
        return key
    # Try the current separator first, then legacy colon
    for sep in (KEY_SEP, ":"):
        prefix = f"{pair_id}{sep}"
        if key.startswith(prefix):
            return key[len(prefix) :]
    return key
