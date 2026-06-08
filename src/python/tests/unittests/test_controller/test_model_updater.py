# Copyright 2017, Inderpreet Singh, All rights reserved.

import unittest
from unittest.mock import MagicMock

from controller.model_updater import ModelUpdater
from controller.persist_keys import KEY_SEP, persist_key


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

    def _make_persist(
        self, downloaded=None, extracted=None, extract_failed=None, validated=None, corrupt=None, move_failed=None
    ):
        """Create a mock persist object with the given file name sets."""
        persist = MagicMock()
        persist.downloaded_file_names = downloaded or set()
        persist.extracted_file_names = extracted or set()
        persist.extract_failed_file_names = extract_failed or set()
        persist.validated_file_names = validated or set()
        persist.corrupt_file_names = corrupt or set()
        persist.move_failed_file_names = move_failed or set()
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

    def test_default_pair_excludes_legacy_colon_keys(self):
        pc_default = self._make_pair_context(None)
        pc_abc = self._make_pair_context("abc")

        persist = self._make_persist(
            downloaded={"abc:legacy.mkv", "plain.txt"},
        )

        updater = self._make_updater([pc_default, pc_abc], persist)
        updater.sync_persist_to_all_builders()

        # Default pair should NOT get the legacy-colon-prefixed key
        pc_default.model_builder.set_downloaded_files.assert_called_once_with({"plain.txt"})
        # abc pair should get it stripped
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

        updater = self._make_updater([pc_abc], persist)
        updater.sync_persist_to_all_builders()

        pc_abc.model_builder.set_downloaded_files.assert_called_once_with({"file.mkv"})
        pc_abc.model_builder.set_extracted_files.assert_called_once_with({"file.mkv"})
        pc_abc.model_builder.set_extract_failed_files.assert_called_once_with({"bad.zip"})
        pc_abc.model_builder.set_validated_files.assert_called_once_with({"good.mkv"})
        pc_abc.model_builder.set_corrupt_files.assert_called_once_with({"corrupt.mkv"})
        pc_abc.model_builder.set_move_failed_files.assert_called_once_with({"stuck.mkv"})


class TestRetryFailedMoves(unittest.TestCase):
    """In-session retry of failed staging->final moves (#536)."""

    def _make_pair_context(self, pair_id):
        pc = MagicMock()
        pc.pair_id = pair_id
        return pc

    def _make_updater(self, pair_contexts, persist, *, use_staging=True, staging_path="/tmp/staging"):
        pipeline = MagicMock()
        # moved_file_keys is a real set so the "already moving" check is realistic
        pipeline.moved_file_keys = set()
        registry = MagicMock()
        extract_process = MagicMock()
        validate_process = MagicMock()
        context = MagicMock()
        context.config.controller.use_staging = use_staging
        context.config.controller.staging_path = staging_path
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
        return updater, pipeline

    def _make_persist(self, move_failed=None):
        persist = MagicMock()
        persist.move_failed_file_names = move_failed if move_failed is not None else set()
        return persist

    def test_respawns_move_for_failed_file_on_cycle(self):
        """A file still in move_failed_file_names that is not currently moving must
        be re-spawned on the next update cycle (not only on restart)."""
        pc = self._make_pair_context("pair-1")
        fail_key = persist_key("pair-1", "file.txt")
        persist = self._make_persist(move_failed={fail_key})
        updater, pipeline = self._make_updater([pc], persist)

        updater._retry_failed_moves()

        pipeline.spawn_move_process.assert_called_once_with("file.txt", pc)

    def test_clears_move_failed_when_nothing_to_move(self):
        """A retry whose staging copy is gone (the move already completed in a
        prior session, or the file vanished) spawns no MoveProcess; treat that
        no-op as resolved and clear MOVE_FAILED instead of leaving the file stuck
        forever (no real move will ever complete to clear it) (#536 follow-up)."""
        pc = self._make_pair_context("pair-1")
        fail_key = persist_key("pair-1", "file.txt")
        persist = self._make_persist(move_failed={fail_key})
        updater, pipeline = self._make_updater([pc], persist)
        updater._persist_sync = MagicMock()  # isolate from real PersistSync wiring
        pipeline.spawn_move_process.return_value = False  # nothing in staging -> no-op

        updater._retry_failed_moves()

        pipeline.spawn_move_process.assert_called_once_with("file.txt", pc)
        self.assertNotIn(fail_key, persist.move_failed_file_names)

    def test_does_not_respawn_when_move_already_in_flight(self):
        """If the move's key is already in moved_file_keys (a move is in flight or
        just re-spawned), do not spawn another."""
        pc = self._make_pair_context("pair-1")
        fail_key = persist_key("pair-1", "file.txt")
        persist = self._make_persist(move_failed={fail_key})
        updater, pipeline = self._make_updater([pc], persist)
        pipeline.moved_file_keys.add(fail_key)

        updater._retry_failed_moves()

        pipeline.spawn_move_process.assert_not_called()

    def test_retry_budget_caps_respawns(self):
        """A permanently-failing move must stop re-spawning after MAX_MOVE_RETRIES
        so it doesn't loop forever."""
        pc = self._make_pair_context("pair-1")
        fail_key = persist_key("pair-1", "file.txt")
        persist = self._make_persist(move_failed={fail_key})
        updater, pipeline = self._make_updater([pc], persist)

        # Each cycle the move "fails" again, so the key never enters moved_file_keys.
        for _ in range(ModelUpdater.MAX_MOVE_RETRIES + 5):
            updater._retry_failed_moves()

        self.assertEqual(ModelUpdater.MAX_MOVE_RETRIES, pipeline.spawn_move_process.call_count)

    def test_no_retry_when_staging_disabled(self):
        """Without staging there are no moves to retry."""
        pc = self._make_pair_context("pair-1")
        fail_key = persist_key("pair-1", "file.txt")
        persist = self._make_persist(move_failed={fail_key})
        updater, pipeline = self._make_updater([pc], persist, use_staging=False, staging_path=None)

        updater._retry_failed_moves()

        pipeline.spawn_move_process.assert_not_called()

    def test_no_retry_when_no_failed_moves(self):
        pc = self._make_pair_context("pair-1")
        persist = self._make_persist(move_failed=set())
        updater, pipeline = self._make_updater([pc], persist)

        updater._retry_failed_moves()

        pipeline.spawn_move_process.assert_not_called()

    def test_default_pair_failed_move_retries(self):
        """A failed move on the default (pair_id=None) pair is also retried."""
        pc = self._make_pair_context(None)
        fail_key = persist_key(None, "file.txt")  # bare name for default pair
        persist = self._make_persist(move_failed={fail_key})
        updater, pipeline = self._make_updater([pc], persist)

        updater._retry_failed_moves()

        pipeline.spawn_move_process.assert_called_once_with("file.txt", pc)

    def test_respawn_resumes_when_move_clears_in_flight_key(self):
        """When a re-spawned move starts (key enters moved_file_keys) the budget
        is not consumed on subsequent cycles; once it succeeds and clears the
        failed set, no further spawns occur (clears state on success)."""
        pc = self._make_pair_context("pair-1")
        fail_key = persist_key("pair-1", "file.txt")
        persist = self._make_persist(move_failed={fail_key})
        updater, pipeline = self._make_updater([pc], persist)

        # Cycle 1: re-spawn, simulate the move starting (key added).
        updater._retry_failed_moves()
        self.assertEqual(1, pipeline.spawn_move_process.call_count)
        pipeline.moved_file_keys.add(fail_key)

        # Cycle 2: move in flight -> no new spawn.
        updater._retry_failed_moves()
        self.assertEqual(1, pipeline.spawn_move_process.call_count)

        # Move succeeds: finalize clears the failed set (simulated here).
        persist.move_failed_file_names.discard(fail_key)

        # Cycle 3: nothing left to retry.
        updater._retry_failed_moves()
        self.assertEqual(1, pipeline.spawn_move_process.call_count)
