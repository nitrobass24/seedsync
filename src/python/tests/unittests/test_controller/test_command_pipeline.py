# Copyright 2017, Inderpreet Singh, All rights reserved.

import os
import unittest
from unittest.mock import MagicMock

from controller.command_pipeline import CommandPipeline
from controller.persist_keys import persist_key
from model import ModelFile


class TestCommandPipelineHelpers(unittest.TestCase):
    def _make_pipeline(self, pair_contexts=None):
        """Create a CommandPipeline with mocked collaborators."""
        if pair_contexts is None:
            pair_contexts = []
        registry = MagicMock()
        persist = MagicMock()
        context = MagicMock()
        password = None
        mp_logger = MagicMock()
        extract_process = MagicMock()
        validate_process = MagicMock()
        logger = MagicMock()
        sync_persist_callback = MagicMock()

        pipeline = CommandPipeline(
            pair_contexts=pair_contexts,
            registry=registry,
            persist=persist,
            context=context,
            password=password,
            mp_logger=mp_logger,
            extract_process=extract_process,
            validate_process=validate_process,
            logger=logger,
            sync_persist_callback=sync_persist_callback,
        )
        return pipeline

    def _make_pair_context(self, pair_id):
        """Create a simple mock PairContext with the given pair_id."""
        pc = MagicMock()
        pc.pair_id = pair_id
        return pc

    # --- find_pair_by_id ---

    def test_find_pair_by_id_none_returns_first_pair(self):
        pc1 = self._make_pair_context(None)
        pc2 = self._make_pair_context("second")
        pipeline = self._make_pipeline([pc1, pc2])

        result = pipeline.find_pair_by_id(None)
        self.assertIs(pc1, result)

    def test_find_pair_by_id_matching_id(self):
        pc1 = self._make_pair_context(None)
        pc2 = self._make_pair_context("abc")
        pipeline = self._make_pipeline([pc1, pc2])

        result = pipeline.find_pair_by_id("abc")
        self.assertIs(pc2, result)

    def test_find_pair_by_id_nonexistent_returns_none(self):
        pc1 = self._make_pair_context(None)
        pipeline = self._make_pipeline([pc1])

        result = pipeline.find_pair_by_id("nonexistent")
        self.assertIsNone(result)

    def test_find_pair_by_id_none_empty_list_returns_none(self):
        pipeline = self._make_pipeline([])

        result = pipeline.find_pair_by_id(None)
        self.assertIsNone(result)

    # --- get_pair_context_for_file ---

    def test_get_pair_context_for_file_matching(self):
        pc1 = self._make_pair_context(None)
        pc2 = self._make_pair_context("abc")
        pipeline = self._make_pipeline([pc1, pc2])

        file = ModelFile("test.txt", False, pair_id="abc")
        result = pipeline.get_pair_context_for_file(file)
        self.assertIs(pc2, result)

    def test_get_pair_context_for_file_no_match(self):
        pc1 = self._make_pair_context("xyz")
        pipeline = self._make_pipeline([pc1])

        file = ModelFile("test.txt", False, pair_id="abc")
        result = pipeline.get_pair_context_for_file(file)
        self.assertIsNone(result)

    # --- _pair_staging_dir ---

    def test_pair_staging_dir_staging_disabled(self):
        pc = self._make_pair_context(None)
        pipeline = self._make_pipeline([pc])
        pipeline._context.config.controller.use_staging = False
        pipeline._context.config.controller.staging_path = None

        result = pipeline._pair_staging_dir(pc)
        self.assertIsNone(result)

    def test_pair_staging_dir_no_pair_id(self):
        pc = self._make_pair_context(None)
        pipeline = self._make_pipeline([pc])
        pipeline._context.config.controller.use_staging = True
        pipeline._context.config.controller.staging_path = "/tmp/staging"

        result = pipeline._pair_staging_dir(pc)
        self.assertEqual("/tmp/staging", result)

    def test_pair_staging_dir_with_pair_id(self):
        pc = self._make_pair_context("abc-123")
        pipeline = self._make_pipeline([pc])
        pipeline._context.config.controller.use_staging = True
        pipeline._context.config.controller.staging_path = "/tmp/staging"

        result = pipeline._pair_staging_dir(pc)
        self.assertEqual(os.path.join("/tmp/staging", "abc-123"), result)

    # --- queue ---

    def test_queue_puts_command_on_queue(self):
        pipeline = self._make_pipeline([])
        command = MagicMock()

        pipeline.queue(command)

        self.assertFalse(pipeline.command_queue.empty())
        self.assertIs(command, pipeline.command_queue.get())

    # --- cleanup: move process failure handling (#510) ---

    def _make_move_process(self, pair_id, file_name, *, failed_results=None):
        """Create a fake finished MoveProcess for cleanup tests."""
        move_process = MagicMock()
        move_process.is_alive.return_value = False
        move_process.pair_id = pair_id
        move_process.file_name = file_name
        move_process.name = "MoveProcess"
        # No raised exception by default
        move_process.propagate_exception.return_value = None
        move_process.pop_failed.return_value = failed_results or []
        return move_process

    def test_cleanup_discards_key_when_move_reports_failure(self):
        """A move that reports a failure via pop_failed must discard its moved key
        and force a rescan so the move is retried."""
        pc = self._make_pair_context("pair-1")
        pipeline = self._make_pipeline([pc])

        move_key = persist_key("pair-1", "file.txt")
        pipeline.moved_file_keys.add(move_key)

        failure = MagicMock()
        failure.name = "file.txt"
        failure.error_message = "source does not exist"
        move_process = self._make_move_process("pair-1", "file.txt", failed_results=[failure])
        pipeline.active_move_processes.append(move_process)

        pipeline.cleanup()

        # Key discarded -> next force_scan re-spawns the move (retry)
        self.assertNotIn(move_key, pipeline.moved_file_keys)
        pc.local_scan_process.force_scan.assert_called_once()
        # Finished process removed from the active list
        self.assertEqual([], pipeline.active_move_processes)

    def test_cleanup_keeps_key_when_move_succeeds(self):
        """A move that reports no failure must keep its moved key (no retry)."""
        pc = self._make_pair_context("pair-1")
        pipeline = self._make_pipeline([pc])

        move_key = persist_key("pair-1", "file.txt")
        pipeline.moved_file_keys.add(move_key)

        move_process = self._make_move_process("pair-1", "file.txt", failed_results=[])
        pipeline.active_move_processes.append(move_process)

        pipeline.cleanup()

        # Successful move keeps the key so it isn't re-spawned
        self.assertIn(move_key, pipeline.moved_file_keys)
        # A rescan still happens to pick up the moved file
        pc.local_scan_process.force_scan.assert_called_once()
        self.assertEqual([], pipeline.active_move_processes)

    def test_cleanup_discards_key_when_move_raises(self):
        """A move that raises (propagate_exception) must also discard its key."""
        pc = self._make_pair_context("pair-1")
        pipeline = self._make_pipeline([pc])

        move_key = persist_key("pair-1", "file.txt")
        pipeline.moved_file_keys.add(move_key)

        move_process = self._make_move_process("pair-1", "file.txt")
        move_process.propagate_exception.side_effect = RuntimeError("boom")
        pipeline.active_move_processes.append(move_process)

        pipeline.cleanup()

        self.assertNotIn(move_key, pipeline.moved_file_keys)
        pc.local_scan_process.force_scan.assert_called_once()

    def test_cleanup_keeps_alive_move_process(self):
        """A still-running move process must remain in the active list untouched."""
        pc = self._make_pair_context("pair-1")
        pipeline = self._make_pipeline([pc])

        move_process = MagicMock()
        move_process.is_alive.return_value = True
        pipeline.active_move_processes.append(move_process)

        pipeline.cleanup()

        self.assertIn(move_process, pipeline.active_move_processes)
        move_process.pop_failed.assert_not_called()
