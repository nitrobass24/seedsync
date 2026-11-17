# Copyright 2017, Inderpreet Singh, All rights reserved.

import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch

from controller.model_updater import ModelUpdater
from controller.persist_keys import KEY_SEP, persist_key
from controller.scan.scanner_process import ScannerResult
from lftp import LftpJobStatus
from model import ModelDiff, ModelError, ModelFile


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


class TestDetectLftpCompletionsNestedFiltering(unittest.TestCase):
    """Nested (path-containing) lftp job names must never reach the active-scan
    fast path: ActiveScanner/ModelBuilder.set_active_files would otherwise treat
    a nested full_path as its own top-level SystemFile, injecting a fake
    top-level entry into the model. This is unconditional (not toggle-gated) -
    it's a correctness fix in the active-file pipeline, not an opt-in feature."""

    def _make_pair_context(self, pair_id=None):
        pc = MagicMock()
        pc.pair_id = pair_id
        pc.prev_downloading_file_names = set()
        pc.pending_completion = set()
        return pc

    def _make_updater(self, pair_contexts, persist=None):
        pipeline = MagicMock()
        registry = MagicMock()
        extract_process = MagicMock()
        validate_process = MagicMock()
        context = MagicMock()
        logger = MagicMock()

        return ModelUpdater(
            pair_contexts=pair_contexts,
            persist=persist or MagicMock(),
            pipeline=pipeline,
            registry=registry,
            extract_process=extract_process,
            validate_process=validate_process,
            context=context,
            password=None,
            logger=logger,
        )

    @staticmethod
    def _status(name, state=LftpJobStatus.State.RUNNING):
        return LftpJobStatus(job_id=1, job_type=LftpJobStatus.Type.PGET, state=state, name=name, flags="")

    def test_nested_names_excluded_from_active_downloading(self):
        pc = self._make_pair_context("pair-1")
        updater = self._make_updater([pc])
        statuses = [self._status("TopLevel"), self._status("TopDir/nested_file.rar")]

        updater._detect_lftp_completions(pc, statuses)

        self.assertEqual(["TopLevel"], pc.active_downloading_file_names)

    def test_top_level_only_names_all_included(self):
        pc = self._make_pair_context("pair-1")
        updater = self._make_updater([pc])
        statuses = [self._status("A"), self._status("B")]

        updater._detect_lftp_completions(pc, statuses)

        self.assertEqual({"A", "B"}, set(pc.active_downloading_file_names))

    def test_prev_downloading_file_names_still_tracks_nested_names(self):
        """The completion-detection bookkeeping (separate from the active-scan
        fast path) must still see nested names, so a nested job's completion is
        still detected and persisted."""
        pc = self._make_pair_context("pair-1")
        updater = self._make_updater([pc])
        statuses = [self._status("TopDir/nested_file.rar")]

        updater._detect_lftp_completions(pc, statuses)

        self.assertEqual({"TopDir/nested_file.rar"}, pc.prev_downloading_file_names)
        self.assertEqual([], pc.active_downloading_file_names)

    def test_pending_completion_excludes_nested_names_on_job_completion(self):
        """pending_completion feeds active_files -> active_scanner the same way
        active_downloading_file_names does (see _update_pair_state). A nested
        name slipping through here got stat'd as a literal top-level path and
        injected a phantom top-level entry distinct from the correctly nested
        row - the exact bug this class of test guards against, just at the
        completion edge instead of the still-running edge."""
        pc = self._make_pair_context("pair-1")
        pc.prev_downloading_file_names = {"TopDir/nested_file.rar", "TopLevel"}
        persist = MagicMock()
        persist.downloaded_file_names = set()
        updater = self._make_updater([pc], persist)
        statuses = []  # neither job is still running -> both just completed

        updater._detect_lftp_completions(pc, statuses)

        self.assertEqual({"TopLevel"}, pc.pending_completion)

    def test_staged_nested_names_fed_to_active_scanner(self):
        """The active scanner is rooted at staging when staging is on, so a
        nested download still there (e.g. a stopped partial) is stat'd like a
        top-level one in pending_completion, and its row shows its size."""
        pc = self._make_pair_context("pair-1")
        pc.staged_nested = {"TopDir/nested_file.rar"}
        pc.active_extracting_file_names = []
        for proc in (pc.remote_scan_process, pc.local_scan_process, pc.active_scan_process):
            proc.pop_latest_result.return_value = None
        pc.lftp.status.return_value = []
        updater = self._make_updater([pc])

        updater._update_pair_model_state(pc, None, None)

        pc.active_scanner.set_active_files.assert_called_once_with(["TopDir/nested_file.rar"])

    def test_nested_completion_not_added_to_downloaded_file_names(self):
        """Nothing reads a nested persist key (model_builder's persist-authority
        check matches top-level names only) and nothing ever removes one, so
        persisting it would just grow the persist file forever. Nested
        completions are picked up by the regular recursive local scan instead."""
        pc = self._make_pair_context("pair-1")
        pc.prev_downloading_file_names = {"TopDir/nested_file.rar"}
        persist = MagicMock()
        persist.downloaded_file_names = set()
        updater = self._make_updater([pc], persist)
        statuses = []

        updater._detect_lftp_completions(pc, statuses)

        self.assertNotIn(persist_key("pair-1", "TopDir/nested_file.rar"), persist.downloaded_file_names)
        self.assertEqual(set(), pc.pending_completion)

    def test_top_level_completion_added_to_downloaded_file_names(self):
        pc = self._make_pair_context("pair-1")
        pc.prev_downloading_file_names = {"TopLevel"}
        persist = MagicMock()
        persist.downloaded_file_names = set()
        updater = self._make_updater([pc], persist)
        statuses = []

        updater._detect_lftp_completions(pc, statuses)

        self.assertIn(persist_key("pair-1", "TopLevel"), persist.downloaded_file_names)
        self.assertEqual({"TopLevel"}, pc.pending_completion)


class TestSpawnNestedMoves(unittest.TestCase):
    """A nested job's lftp job ending (completion or Stop) triggers its
    staging->final move directly, since it has no DOWNLOADED diff to drive it."""

    def _make_pair_context(self, pair_id=None):
        pc = MagicMock()
        pc.pair_id = pair_id
        pc.prev_downloading_file_names = set()
        pc.pending_completion = set()
        pc.pending_nested_moves = set()
        pc.remote_scan_in_model = True
        return pc

    def _make_updater(self, pair_contexts, persist=None, *, use_staging=True, staging_path="/tmp/staging"):
        pipeline = MagicMock()
        registry = MagicMock()
        extract_process = MagicMock()
        validate_process = MagicMock()
        context = MagicMock()
        context.config.controller.use_staging = use_staging
        context.config.controller.staging_path = staging_path
        logger = MagicMock()

        updater = ModelUpdater(
            pair_contexts=pair_contexts,
            persist=persist or MagicMock(),
            pipeline=pipeline,
            registry=registry,
            extract_process=extract_process,
            validate_process=validate_process,
            context=context,
            password=None,
            logger=logger,
        )
        return updater, pipeline, registry

    def _make_persist(self):
        persist = MagicMock()
        persist.downloaded_file_names = set()
        return persist

    def _running(self, name):
        return LftpJobStatus(0, LftpJobStatus.Type.PGET, LftpJobStatus.State.RUNNING, name, "")

    def test_pending_nested_move_spawned_once_lftp_no_longer_lists_it(self):
        pc = self._make_pair_context("pair-1")
        pc.pending_nested_moves = {"Top/leaf.rar"}
        updater, pipeline, registry = self._make_updater([pc], self._make_persist())
        resolved = MagicMock()
        resolved.remote_size = 12345
        registry.resolve_full_path.return_value = resolved

        updater._detect_lftp_completions(pc, [])

        registry.resolve_full_path.assert_called_once_with("Top/leaf.rar", pair_id="pair-1")
        pipeline.spawn_move_process.assert_called_once_with("Top/leaf.rar", pc, expected_size=12345)
        self.assertEqual(set(), pc.pending_nested_moves)

    def test_job_never_seen_running_still_spawns_move(self):
        """A job that finishes between two status polls (a small file, or one
        already complete in staging) never shows as running; the queue-driven
        pending set still moves it."""
        pc = self._make_pair_context("pair-1")
        pc.pending_nested_moves = {"Top/leaf.rar"}
        pc.prev_downloading_file_names = set()
        updater, pipeline, registry = self._make_updater([pc], self._make_persist())
        registry.resolve_full_path.return_value.remote_size = 10

        updater._detect_lftp_completions(pc, [])

        pipeline.spawn_move_process.assert_called_once_with("Top/leaf.rar", pc, expected_size=10)

    def test_pending_nested_move_waits_while_lftp_lists_it(self):
        pc = self._make_pair_context("pair-1")
        pc.pending_nested_moves = {"Top/leaf.rar"}
        updater, pipeline, registry = self._make_updater([pc], self._make_persist())

        updater._detect_lftp_completions(pc, [self._running("Top/leaf.rar")])

        pipeline.spawn_move_process.assert_not_called()
        self.assertEqual({"Top/leaf.rar"}, pc.pending_nested_moves)

    def test_pending_nested_move_with_unresolvable_row_stays_in_staging(self):
        """The row can be gone by the time this runs (e.g. a remote delete
        raced the completion). Without a remote size a stopped partial can't be
        told from a finished download, so nothing is moved."""
        pc = self._make_pair_context("pair-1")
        pc.pending_nested_moves = {"Top/leaf.rar"}
        updater, pipeline, registry = self._make_updater([pc], self._make_persist())
        registry.resolve_full_path.side_effect = ModelError("not found")

        updater._detect_lftp_completions(pc, [])

        pipeline.spawn_move_process.assert_not_called()
        self.assertEqual(set(), pc.pending_nested_moves)

    def test_pending_nested_move_with_no_remote_size_stays_in_staging(self):
        pc = self._make_pair_context("pair-1")
        pc.pending_nested_moves = {"Top/leaf.rar"}
        updater, pipeline, registry = self._make_updater([pc], self._make_persist())
        registry.resolve_full_path.return_value.remote_size = None

        updater._detect_lftp_completions(pc, [])

        pipeline.spawn_move_process.assert_not_called()

    def test_completion_without_pending_entry_spawns_nothing(self):
        """Only names queued under staging are moved: a nested job ending with
        staging off, or any top-level job, never enters the pending set."""
        pc = self._make_pair_context("pair-1")
        pc.prev_downloading_file_names = {"Top/leaf.rar", "TopLevel"}
        updater, pipeline, registry = self._make_updater([pc], self._make_persist())

        updater._detect_lftp_completions(pc, [])

        pipeline.spawn_move_process.assert_not_called()
        registry.resolve_full_path.assert_not_called()

    def test_pending_nested_move_waits_until_the_remote_scan_is_in_the_model(self):
        """After a restart, pending moves come back before the first remote
        scan. Until a model built from it is in the registry the row can't be
        resolved, and the move would be dropped for an unknown size."""
        pc = self._make_pair_context("pair-1")
        pc.remote_scan_in_model = False
        pc.pending_nested_moves = {"Top/leaf.rar"}
        updater, pipeline, registry = self._make_updater([pc], self._make_persist())

        updater._detect_lftp_completions(pc, [])

        registry.resolve_full_path.assert_not_called()
        pipeline.spawn_move_process.assert_not_called()
        self.assertEqual({"Top/leaf.rar"}, pc.pending_nested_moves)

    def test_remote_scan_marked_in_model_once_a_model_is_built_with_it(self):
        received = self._make_pair_context("pair-1")
        received.remote_scan_received = True
        received.remote_scan_in_model = False
        waiting = self._make_pair_context("pair-2")
        waiting.remote_scan_received = False
        waiting.remote_scan_in_model = False
        updater, _pipeline, _registry = self._make_updater([received, waiting], self._make_persist())

        updater._note_remote_scans_in_model()

        self.assertTrue(received.remote_scan_in_model)
        self.assertFalse(waiting.remote_scan_in_model)


class TestPruneAbsentNestedMoveFailures(unittest.TestCase):
    """Nested move_failed keys never reach downloaded_file_names (the prune
    that drives _prune_absent_persist_entries), so they get their own pass."""

    def _make_pair_context(self, pair_id=None):
        pc = MagicMock()
        pc.pair_id = pair_id
        return pc

    def _make_updater(self, pair_contexts, persist):
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
        updater._persist_sync = MagicMock()
        return updater, registry

    def _make_persist(self, move_failed):
        persist = MagicMock()
        persist.move_failed_file_names = move_failed
        return persist

    def test_unresolvable_nested_key_removed(self):
        pc = self._make_pair_context("pair-1")
        fail_key = persist_key("pair-1", "Top/leaf.rar")
        persist = self._make_persist({fail_key})
        updater, registry = self._make_updater([pc], persist)
        registry.resolve_full_path.side_effect = ModelError("gone")

        updater._prune_absent_nested_move_failures()

        registry.resolve_full_path.assert_called_once_with("Top/leaf.rar", pair_id="pair-1")
        self.assertNotIn(fail_key, persist.move_failed_file_names)

    def test_resolvable_nested_key_kept(self):
        pc = self._make_pair_context("pair-1")
        fail_key = persist_key("pair-1", "Top/leaf.rar")
        persist = self._make_persist({fail_key})
        updater, registry = self._make_updater([pc], persist)
        registry.resolve_full_path.return_value = MagicMock()

        updater._prune_absent_nested_move_failures()

        self.assertIn(fail_key, persist.move_failed_file_names)

    def test_top_level_key_untouched(self):
        pc = self._make_pair_context("pair-1")
        fail_key = persist_key("pair-1", "TopLevel")
        persist = self._make_persist({fail_key})
        updater, registry = self._make_updater([pc], persist)

        updater._prune_absent_nested_move_failures()

        registry.resolve_full_path.assert_not_called()
        self.assertIn(fail_key, persist.move_failed_file_names)


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

    def test_retry_count_dropped_when_key_cleared_without_requeue_diff(self):
        """A nested re-queue clears move_failed_file_names directly
        (CommandPipeline._handle_queue), with no requeue diff to reset the
        retry count, so the count must be dropped here instead - otherwise a
        later failure on the same name would start part-way through the budget."""
        pc = self._make_pair_context("pair-1")
        fail_key = persist_key("pair-1", "Top/leaf.rar")
        persist = self._make_persist(move_failed=set())  # cleared by the re-queue
        updater, pipeline = self._make_updater([pc], persist)
        updater._move_retry_counts[fail_key] = ModelUpdater.MAX_MOVE_RETRIES

        updater._retry_failed_moves()

        self.assertNotIn(fail_key, updater._move_retry_counts)

    def test_retry_count_kept_while_key_still_failed(self):
        pc = self._make_pair_context("pair-1")
        fail_key = persist_key("pair-1", "file.txt")
        persist = self._make_persist(move_failed={fail_key})
        updater, pipeline = self._make_updater([pc], persist)
        updater._move_retry_counts[fail_key] = 1

        updater._retry_failed_moves()

        self.assertIn(fail_key, updater._move_retry_counts)

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


class TestUpdatePairContextScanResults(unittest.TestCase):
    """A failed scan carries no files. Applying it would make every download
    look deleted (local) or prune persist records and later re-queue every
    download (remote); and it must not count as "received", which opens the
    absent-persist prune gate."""

    def _make_pc(self, local_scan=None, remote_scan=None):
        pc = MagicMock()
        pc.pair_id = "pair-1"
        pc.remote_scan_received = False
        pc.local_scan_received = False
        pc.remote_scan_process.pop_latest_result.return_value = remote_scan
        pc.local_scan_process.pop_latest_result.return_value = local_scan
        pc.active_scan_process.pop_latest_result.return_value = None
        pc.lftp.status.return_value = []
        pc.active_downloading_file_names = []
        pc.active_extracting_file_names = []
        pc.pending_completion = set()
        return pc

    def _make_updater(self, pc):
        return ModelUpdater(
            pair_contexts=[pc],
            persist=MagicMock(),
            pipeline=MagicMock(),
            registry=MagicMock(),
            extract_process=MagicMock(),
            validate_process=MagicMock(),
            context=MagicMock(),
            password=None,
            logger=MagicMock(),
        )

    def test_failed_local_scan_is_not_applied_to_the_model(self):
        scan = ScannerResult(timestamp=datetime.now(), files=[], failed=True, error_message="unreadable")
        pc = self._make_pc(scan)

        self._make_updater(pc)._update_pair_model_state(pc, None, None)

        pc.model_builder.set_local_files.assert_not_called()
        self.assertFalse(pc.local_scan_received)
        self.assertIs(scan, pc.latest_local_scan)

    def test_successful_local_scan_is_applied_to_the_model(self):
        scan = ScannerResult(timestamp=datetime.now(), files=[])
        pc = self._make_pc(scan)

        self._make_updater(pc)._update_pair_model_state(pc, None, None)

        pc.model_builder.set_local_files.assert_called_once_with([])
        self.assertTrue(pc.local_scan_received)

    def test_failed_remote_scan_keeps_the_last_listing_and_the_prune_gate(self):
        scan = ScannerResult(timestamp=datetime.now(), files=[], failed=True, error_message="path missing")
        pc = self._make_pc(remote_scan=scan)

        self._make_updater(pc)._update_pair_model_state(pc, None, None)

        pc.model_builder.set_remote_files.assert_not_called()
        self.assertFalse(pc.remote_scan_received)
        self.assertIs(scan, pc.latest_remote_scan)  # still surfaced in status

    def test_last_failed_remote_scan_is_kept_on_a_cycle_with_no_new_result(self):
        """The cleanup guard checks pc.latest_remote_scan.failed; a quiet cycle
        must not reset it to None while the listing is still untrusted."""
        failed = ScannerResult(timestamp=datetime.now(), files=[], failed=True, error_message="path missing")
        pc = self._make_pc(remote_scan=None)
        pc.latest_remote_scan = failed

        self._make_updater(pc)._update_pair_model_state(pc, None, None)

        self.assertIs(failed, pc.latest_remote_scan)

    def test_successful_remote_scan_is_applied_to_the_model(self):
        scan = ScannerResult(timestamp=datetime.now(), files=[])
        pc = self._make_pc(remote_scan=scan)
        updater = self._make_updater(pc)
        updater._context.config.general.exclude_patterns = []

        updater._update_pair_model_state(pc, None, None)

        pc.model_builder.set_remote_files.assert_called_once_with([])
        self.assertTrue(pc.remote_scan_received)


class TestHandleDownloadedFileUmask(unittest.TestCase):
    """#811: lftp creates 0664/0775 whatever the umask, so a completed download
    is chmod'ed to 0666/0777 & ~UMASK before any staging move."""

    def _run(self, umask, use_staging=False):
        pc = MagicMock()
        pc.pair_id = "pair-1"
        pc.local_path = "/downloads"
        context = MagicMock()
        context.args.umask = umask
        context.config.validate.enabled = False
        context.config.controller.use_staging = use_staging
        context.config.controller.staging_path = "/staging" if use_staging else None
        context.config.autoqueue.auto_extract = False
        updater = ModelUpdater(
            pair_contexts=[pc],
            persist=MagicMock(),
            pipeline=MagicMock(),
            registry=MagicMock(),
            extract_process=MagicMock(),
            validate_process=MagicMock(),
            context=context,
            password=None,
            logger=MagicMock(),
        )
        new_file = ModelFile("Show.S01", True)
        new_file.state = ModelFile.State.DOWNLOADED
        new_file.pair_id = "pair-1"
        diff = ModelDiff(ModelDiff.Change.ADDED, old_file=None, new_file=new_file)
        threads = []

        def run_inline(**kwargs):
            # A fake thread that runs the worker when start() is called, so the
            # test fails if the thread is built but never started.
            threads.append(kwargs)
            fake = MagicMock()
            fake.start.side_effect = lambda: kwargs["target"](*kwargs.get("args", ()))
            return fake

        with (
            patch("controller.model_updater.apply_umask_modes") as apply,
            patch("controller.model_updater.threading.Thread", side_effect=run_inline),
        ):
            updater._handle_downloaded_file(diff, pc)
        return apply, threads

    def test_applies_modes_off_the_controller_thread_when_umask_is_set(self):
        apply, threads = self._run(0o000)
        self.assertEqual(1, len(threads))
        self.assertTrue(threads[0]["daemon"])
        apply.assert_called_once()
        self.assertEqual(("/downloads/Show.S01", 0o000), apply.call_args[0][:2])

    def test_leaves_modes_to_the_move_process_when_staging_is_on(self):
        apply, threads = self._run(0o000, use_staging=True)
        apply.assert_not_called()
        self.assertEqual([], threads)

    def test_skips_when_umask_is_unset(self):
        apply, threads = self._run(None)
        apply.assert_not_called()
        self.assertEqual([], threads)


class TestHandleDownloadedFileOverlappingMove(unittest.TestCase):
    """A root can turn Downloaded while a nested download inside it is still
    in staging, its own move in flight. The root's move would race that one,
    so it is left to the nested move."""

    def _run(self, overlapping_move):
        pc = MagicMock()
        context = MagicMock()
        context.args.umask = None
        context.config.validate.enabled = False
        context.config.controller.use_staging = True
        context.config.controller.staging_path = "/staging"
        context.config.autoqueue.auto_extract = False
        pipeline = MagicMock()
        pipeline.find_overlapping_move.return_value = overlapping_move
        updater = ModelUpdater(
            pair_contexts=[pc],
            persist=MagicMock(),
            pipeline=pipeline,
            registry=MagicMock(),
            extract_process=MagicMock(),
            validate_process=MagicMock(),
            context=context,
            password=None,
            logger=MagicMock(),
        )
        new_file = ModelFile("Show", True)
        new_file.state = ModelFile.State.DOWNLOADED
        updater._handle_downloaded_file(ModelDiff(ModelDiff.Change.ADDED, old_file=None, new_file=new_file), pc)
        return pipeline, pc

    def test_root_move_skipped_while_a_nested_move_inside_it_is_in_flight(self):
        pipeline, pc = self._run("Show/Season 1")
        pipeline.find_overlapping_move.assert_called_once_with("Show", pc)
        pipeline.spawn_move_process.assert_not_called()

    def test_root_move_spawned_without_an_overlapping_move(self):
        pipeline, pc = self._run(None)
        pipeline.spawn_move_process.assert_called_once_with("Show", pc)
