# Copyright 2017, Inderpreet Singh, All rights reserved.

from dataclasses import dataclass
from enum import Enum

# my libs
from .file import ModelFile
from .model import Model


@dataclass(frozen=True)
class ModelDiff:
    """
    Represents a single change in the model
    """

    class Change(Enum):
        ADDED = 0
        REMOVED = 1
        UPDATED = 2

    change: Change
    old_file: ModelFile | None
    new_file: ModelFile | None


class ModelDiffUtil:
    @staticmethod
    def diff_models(model_before: Model, model_after: Model) -> list[ModelDiff]:
        """
        Compare two models and generate their diff.
        Uses composite keys (pair_id:name) for correct multi-pair comparison.
        :param model_before:
        :param model_after:
        :return:
        """
        diffs: list[ModelDiff] = []

        # Build key->file maps
        before_map = {Model.file_key(f): f for f in model_before.get_all_files()}
        after_map = {Model.file_key(f): f for f in model_after.get_all_files()}

        keys_before = set(before_map.keys())
        keys_after = set(after_map.keys())

        # 'after minus before' gives added files
        for key in keys_after.difference(keys_before):
            diffs.append(ModelDiff(ModelDiff.Change.ADDED, None, after_map[key]))

        # 'before minus after' gives removed files
        for key in keys_before.difference(keys_after):
            diffs.append(ModelDiff(ModelDiff.Change.REMOVED, before_map[key], None))

        # 'before intersect after' gives potentially updated files
        for key in keys_before.intersection(keys_after):
            file_before = before_map[key]
            file_after = after_map[key]
            if file_before != file_after:
                diffs.append(ModelDiff(ModelDiff.Change.UPDATED, file_before, file_after))

        return diffs
