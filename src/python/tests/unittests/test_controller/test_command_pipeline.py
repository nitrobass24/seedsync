# Copyright 2017, Inderpreet Singh, All rights reserved.

import os
import unittest
from unittest.mock import MagicMock

from controller.command_pipeline import CommandPipeline
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
