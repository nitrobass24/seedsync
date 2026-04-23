# Copyright 2017, Inderpreet Singh, All rights reserved.

import unittest
from unittest.mock import MagicMock

from controller.model_updater import ModelUpdater
from controller.persist_keys import KEY_SEP


class TestSyncPersistToAllBuilders(unittest.TestCase):
    def _make_pair_context(self, pair_id):
        """Create a mock PairContext with a model_builder that records calls."""
        pc = MagicMock()
        pc.pair_id = pair_id
        return pc

    def _make_updater(self, pair_contexts, persist):
        """Create a ModelUpdater with mocked collaborators."""
        pipeline = MagicMock()
        registry = MagicMock()
        extract_process = MagicMock()
        validate_process = MagicMock()
        context = MagicMock()
        logger = MagicMock()

        updater = ModelUpdater(
            pair_contexts=pair_contexts,
            persist=persist,
            pipeline=pipeline,
            registry=registry,
            extract_process=extract_process,
            validate_process=validate_process,
            context=context,
            password=None,
            logger=logger,
        )
        return updater

    def _make_persist(self, downloaded=None, extracted=None, extract_failed=None, validated=None, corrupt=None):
        """Create a mock persist object with the given file name sets."""
        persist = MagicMock()
        persist.downloaded_file_names = downloaded or set()
        persist.extracted_file_names = extracted or set()
        persist.extract_failed_file_names = extract_failed or set()
        persist.validated_file_names = validated or set()
        persist.corrupt_file_names = corrupt or set()
        return persist

    def test_filters_downloaded_keys_by_pair_id_prefix(self):
        pc_abc = self._make_pair_context("abc")
        pc_xyz = self._make_pair_context("xyz")

        persist = self._make_persist(
            downloaded={f"abc{KEY_SEP}movie.mkv", f"xyz{KEY_SEP}show.avi"},
            extracted={f"abc{KEY_SEP}movie.mkv"},
        )

        updater = self._make_updater([pc_abc, pc_xyz], persist)
        updater.sync_persist_to_all_builders()

        # pc_abc should get only movie.mkv
        pc_abc.model_builder.set_downloaded_files.assert_called_once_with({"movie.mkv"})
        pc_abc.model_builder.set_extracted_files.assert_called_once_with({"movie.mkv"})

        # pc_xyz should get only show.avi
        pc_xyz.model_builder.set_downloaded_files.assert_called_once_with({"show.avi"})
        pc_xyz.model_builder.set_extracted_files.assert_called_once_with(set())

    def test_none_pair_id_gets_unprefixed_keys(self):
        pc_default = self._make_pair_context(None)
        pc_abc = self._make_pair_context("abc")

        persist = self._make_persist(
            downloaded={"plain_file.txt", f"abc{KEY_SEP}namespaced.mkv"},
        )

        updater = self._make_updater([pc_default, pc_abc], persist)
        updater.sync_persist_to_all_builders()

        # Default pair (None pair_id) should get plain_file.txt (no prefix)
        pc_default.model_builder.set_downloaded_files.assert_called_once_with({"plain_file.txt"})

        # abc pair should get namespaced.mkv
        pc_abc.model_builder.set_downloaded_files.assert_called_once_with({"namespaced.mkv"})

    def test_handles_legacy_colon_separator_keys(self):
        pc_abc = self._make_pair_context("abc")

        persist = self._make_persist(
            downloaded={"abc:legacy_file.mkv"},
            extracted={"abc:legacy_file.mkv"},
        )

        updater = self._make_updater([pc_abc], persist)
        updater.sync_persist_to_all_builders()

        # Should strip the legacy colon prefix and deliver the bare name
        pc_abc.model_builder.set_downloaded_files.assert_called_once_with({"legacy_file.mkv"})
        pc_abc.model_builder.set_extracted_files.assert_called_once_with({"legacy_file.mkv"})

    def test_all_persist_categories_are_distributed(self):
        pc_abc = self._make_pair_context("abc")

        persist = self._make_persist(
            downloaded={f"abc{KEY_SEP}file.mkv"},
            extracted={f"abc{KEY_SEP}file.mkv"},
            extract_failed={f"abc{KEY_SEP}bad.zip"},
            validated={f"abc{KEY_SEP}good.mkv"},
            corrupt={f"abc{KEY_SEP}corrupt.mkv"},
        )

        updater = self._make_updater([pc_abc], persist)
        updater.sync_persist_to_all_builders()

        pc_abc.model_builder.set_downloaded_files.assert_called_once_with({"file.mkv"})
        pc_abc.model_builder.set_extracted_files.assert_called_once_with({"file.mkv"})
        pc_abc.model_builder.set_extract_failed_files.assert_called_once_with({"bad.zip"})
        pc_abc.model_builder.set_validated_files.assert_called_once_with({"good.mkv"})
        pc_abc.model_builder.set_corrupt_files.assert_called_once_with({"corrupt.mkv"})
