# Copyright 2017, Inderpreet Singh, All rights reserved.

import unittest
from unittest.mock import MagicMock

from controller.persist_keys import KEY_SEP
from controller.persist_sync import PersistSync


class TestPersistSync(unittest.TestCase):
    """Mirrors the assertions in test_model_updater to prove the extracted
    PersistSync.sync() runs the identical pair-filtering logic."""

    def _make_pair_context(self, pair_id):
        pc = MagicMock()
        pc.pair_id = pair_id
        return pc

    def _make_persist(
        self, downloaded=None, extracted=None, extract_failed=None, validated=None, corrupt=None, move_failed=None
    ):
        persist = MagicMock()
        persist.downloaded_file_names = downloaded or set()
        persist.extracted_file_names = extracted or set()
        persist.extract_failed_file_names = extract_failed or set()
        persist.validated_file_names = validated or set()
        persist.corrupt_file_names = corrupt or set()
        persist.move_failed_file_names = move_failed or set()
        return persist

    def test_filters_keys_by_pair_id_prefix(self):
        pc_abc = self._make_pair_context("abc")
        pc_xyz = self._make_pair_context("xyz")
        persist = self._make_persist(
            downloaded={f"abc{KEY_SEP}movie.mkv", f"xyz{KEY_SEP}show.avi"},
            extracted={f"abc{KEY_SEP}movie.mkv"},
        )

        PersistSync([pc_abc, pc_xyz], persist).sync()

        pc_abc.model_builder.set_downloaded_files.assert_called_once_with({"movie.mkv"})
        pc_abc.model_builder.set_extracted_files.assert_called_once_with({"movie.mkv"})
        pc_xyz.model_builder.set_downloaded_files.assert_called_once_with({"show.avi"})
        pc_xyz.model_builder.set_extracted_files.assert_called_once_with(set())

    def test_none_pair_id_gets_unprefixed_keys(self):
        pc_default = self._make_pair_context(None)
        pc_abc = self._make_pair_context("abc")
        persist = self._make_persist(downloaded={"plain_file.txt", f"abc{KEY_SEP}namespaced.mkv"})

        PersistSync([pc_default, pc_abc], persist).sync()

        pc_default.model_builder.set_downloaded_files.assert_called_once_with({"plain_file.txt"})
        pc_abc.model_builder.set_downloaded_files.assert_called_once_with({"namespaced.mkv"})

    def test_handles_legacy_colon_separator_keys(self):
        pc_abc = self._make_pair_context("abc")
        persist = self._make_persist(downloaded={"abc:legacy_file.mkv"})

        PersistSync([pc_abc], persist).sync()

        pc_abc.model_builder.set_downloaded_files.assert_called_once_with({"legacy_file.mkv"})

    def test_default_pair_excludes_legacy_colon_keys(self):
        pc_default = self._make_pair_context(None)
        pc_abc = self._make_pair_context("abc")
        persist = self._make_persist(downloaded={"abc:legacy.mkv", "plain.txt"})

        PersistSync([pc_default, pc_abc], persist).sync()

        pc_default.model_builder.set_downloaded_files.assert_called_once_with({"plain.txt"})
        pc_abc.model_builder.set_downloaded_files.assert_called_once_with({"legacy.mkv"})

    def test_all_persist_categories_are_distributed(self):
        pc_abc = self._make_pair_context("abc")
        persist = self._make_persist(
            downloaded={f"abc{KEY_SEP}file.mkv"},
            extracted={f"abc{KEY_SEP}file.mkv"},
            extract_failed={f"abc{KEY_SEP}bad.zip"},
            validated={f"abc{KEY_SEP}good.mkv"},
            corrupt={f"abc{KEY_SEP}corrupt.mkv"},
            move_failed={f"abc{KEY_SEP}stuck.mkv"},
        )

        PersistSync([pc_abc], persist).sync()

        pc_abc.model_builder.set_downloaded_files.assert_called_once_with({"file.mkv"})
        pc_abc.model_builder.set_extracted_files.assert_called_once_with({"file.mkv"})
        pc_abc.model_builder.set_extract_failed_files.assert_called_once_with({"bad.zip"})
        pc_abc.model_builder.set_validated_files.assert_called_once_with({"good.mkv"})
        pc_abc.model_builder.set_corrupt_files.assert_called_once_with({"corrupt.mkv"})
        pc_abc.model_builder.set_move_failed_files.assert_called_once_with({"stuck.mkv"})

    def test_filter_keys_for_pair_static(self):
        result = PersistSync._filter_keys_for_pair(
            {f"abc{KEY_SEP}a.mkv", f"xyz{KEY_SEP}b.mkv"}, "abc", (f"xyz{KEY_SEP}", "xyz:")
        )
        self.assertEqual({"a.mkv"}, result)
