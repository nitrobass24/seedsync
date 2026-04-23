# Copyright 2017, Inderpreet Singh, All rights reserved.

"""Thread-safe model and listener registry.

Encapsulates the Model, its lock, and listener management. Extracted from
controller.py as part of the controller decomposition (#394 Phase 2D).
"""

from __future__ import annotations

import copy
from threading import RLock

from model import IModelListener, Model, ModelDiff, ModelDiffUtil, ModelFile


class ModelRegistry:
    """Owns the Model instance and its lock.

    Public API methods (get_files, add_listener, etc.) are thread-safe.
    The ``apply_diff`` method is also thread-safe and returns the diffs
    so the caller can process side effects outside the lock.

    Direct model access (``get_file``, ``get_all_files``) is provided for
    the controller thread which doesn't need locking (single-threaded access).
    """

    def __init__(self, model: Model):
        self._model = model
        self._lock = RLock()

    # --- Thread-safe public API (used by external callers) ---

    def get_files(self) -> list[ModelFile]:
        """Return a deep copy of all model files (thread-safe)."""
        with self._lock:
            return [copy.deepcopy(f) for f in self._model.get_all_files()]

    def add_listener(self, listener: IModelListener) -> None:
        """Add a model listener (thread-safe)."""
        with self._lock:
            self._model.add_listener(listener)

    def remove_listener(self, listener: IModelListener) -> None:
        """Remove a model listener (thread-safe)."""
        with self._lock:
            self._model.remove_listener(listener)

    def get_files_and_add_listener(self, listener: IModelListener) -> list[ModelFile]:
        """Add a listener and return current files atomically (thread-safe)."""
        with self._lock:
            self._model.add_listener(listener)
            return [copy.deepcopy(f) for f in self._model.get_all_files()]

    # --- Mutation API (thread-safe, called from controller thread) ---

    def apply_diff(self, new_model: Model) -> list[ModelDiff]:
        """Diff the current model against new_model, apply changes, and return the diffs.

        The diff computation and model mutation happen atomically under the lock.
        Listeners are notified during mutation (inside the lock).
        The returned diffs can be used by the caller for side-effect processing
        outside the lock.
        """
        with self._lock:
            diffs = ModelDiffUtil.diff_models(self._model, new_model)
            for diff in diffs:
                if diff.change == ModelDiff.Change.ADDED:
                    assert diff.new_file is not None
                    self._model.add_file(diff.new_file)
                elif diff.change == ModelDiff.Change.REMOVED:
                    assert diff.old_file is not None
                    self._model.remove_file(diff.old_file.name, pair_id=diff.old_file.pair_id)
                elif diff.change == ModelDiff.Change.UPDATED:
                    assert diff.new_file is not None
                    self._model.update_file(diff.new_file)
            return diffs

    # --- Direct access (controller thread only, no lock needed) ---

    def get_file(self, name: str, pair_id: str | None = None) -> ModelFile:
        """Get a single file by name. Not thread-safe — controller thread only."""
        return self._model.get_file(name, pair_id=pair_id)

    def get_all_files(self) -> list[ModelFile]:
        """Get all files (no copy). Not thread-safe — controller thread only."""
        return self._model.get_all_files()
