# Copyright 2017, Inderpreet Singh, All rights reserved.

"""Persist-state synchronization to per-pair model builders.

Extracted from ModelUpdater so the same collaborator can be injected into
both CommandPipeline (which clears persist entries on extract/validate) and
ModelUpdater (which pushes persist state every update cycle), removing the
construction-order placeholder lambda that previously stood in for the
callback. The logic is moved verbatim — this is a structural extraction,
not a refactor.
"""

from __future__ import annotations

from .controller_persist import ControllerPersist
from .pair_context import PairContext
from .persist_keys import KEY_SEP


class PersistSync:
    """Push current persist state to all pair model builders, filtered by pair_id."""

    def __init__(self, pair_contexts: list[PairContext], persist: ControllerPersist):
        self._pair_contexts = pair_contexts
        self._persist = persist

    def sync(self):
        """Push current persist state to all pair model builders, filtered by pair_id."""
        namespaced_prefixes = tuple(
            f"{other_pc.pair_id}{sep}" for other_pc in self._pair_contexts if other_pc.pair_id for sep in (KEY_SEP, ":")
        )
        for pc in self._pair_contexts:
            pc.model_builder.set_downloaded_files(
                self._filter_keys_for_pair(self._persist.downloaded_file_names, pc.pair_id, namespaced_prefixes)
            )
            pc.model_builder.set_extracted_files(
                self._filter_keys_for_pair(self._persist.extracted_file_names, pc.pair_id, namespaced_prefixes)
            )
            pc.model_builder.set_extract_failed_files(
                self._filter_keys_for_pair(self._persist.extract_failed_file_names, pc.pair_id, namespaced_prefixes)
            )
            pc.model_builder.set_validated_files(
                self._filter_keys_for_pair(self._persist.validated_file_names, pc.pair_id, namespaced_prefixes)
            )
            pc.model_builder.set_corrupt_files(
                self._filter_keys_for_pair(self._persist.corrupt_file_names, pc.pair_id, namespaced_prefixes)
            )
            pc.model_builder.set_move_failed_files(
                self._filter_keys_for_pair(self._persist.move_failed_file_names, pc.pair_id, namespaced_prefixes)
            )

    @staticmethod
    def _filter_keys_for_pair(keys: set[str], pair_id: str | None, namespaced_prefixes: tuple[str, ...]) -> set[str]:
        """Filter and strip persist keys that belong to a specific pair.

        For pairs with a pair_id, matches keys with the current separator or
        legacy colon prefix. For the default pair (pair_id=None), matches keys
        that don't start with any other pair's prefix.
        """
        result: set[str] = set()
        if pair_id:
            prefix = f"{pair_id}{KEY_SEP}"
            legacy_prefix = f"{pair_id}:"
            for key in keys:
                if key.startswith(prefix):
                    result.add(key[len(prefix) :])
                elif key.startswith(legacy_prefix):
                    result.add(key[len(legacy_prefix) :])
        else:
            for key in keys:
                if not key.startswith(namespaced_prefixes):
                    result.add(key)
        return result
