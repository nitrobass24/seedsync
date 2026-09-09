# Copyright 2017, Inderpreet Singh, All rights reserved.

from dataclasses import dataclass

from model import ModelFile


@dataclass
class ExtractRequest:
    """Bundles a ModelFile with the pair-specific paths needed for extraction."""

    model_file: ModelFile
    local_path: str
    out_dir_path: str
    pair_id: str | None = None
    local_path_fallback: str | None = None
    out_dir_path_fallback: str | None = None
