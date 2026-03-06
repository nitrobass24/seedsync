# Copyright 2017, Inderpreet Singh, All rights reserved.

from model import ModelFile


class ExtractRequest:
    """Bundles a ModelFile with the pair-specific paths needed for extraction."""

    def __init__(self, model_file: ModelFile,
                 local_path: str,
                 out_dir_path: str,
                 pair_id: str = None,
                 local_path_fallback: str = None,
                 out_dir_path_fallback: str = None):
        self.model_file = model_file
        self.pair_id = pair_id
        self.local_path = local_path
        self.out_dir_path = out_dir_path
        self.local_path_fallback = local_path_fallback
        self.out_dir_path_fallback = out_dir_path_fallback or out_dir_path
