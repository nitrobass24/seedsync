# Copyright 2017, Inderpreet Singh, All rights reserved.

import logging
import unittest

from controller.model_registry import ModelRegistry
from model import IModelListener, Model, ModelDiff, ModelFile


class _TestListener(IModelListener):
    """Simple listener that records events."""

    def __init__(self):
        self.added: list[ModelFile] = []
        self.removed: list[ModelFile] = []
        self.updated: list[tuple[ModelFile, ModelFile]] = []

    def file_added(self, file: ModelFile):
        self.added.append(file)

    def file_removed(self, file: ModelFile):
        self.removed.append(file)

    def file_updated(self, old_file: ModelFile, new_file: ModelFile):
        self.updated.append((old_file, new_file))


class TestModelRegistry(unittest.TestCase):
    def setUp(self):
        self.model = Model()
        logger = logging.getLogger("TestModelRegistry")
        logger.addHandler(logging.NullHandler())
        self.model.set_base_logger(logger)
        self.registry = ModelRegistry(self.model)

    def test_get_files_returns_deep_copies(self):
        f = ModelFile("test.txt", False)
        f.state = ModelFile.State.DEFAULT
        self.model.add_file(f)

        files = self.registry.get_files()
        self.assertEqual(1, len(files))
        self.assertEqual("test.txt", files[0].name)

        # Modify the returned copy
        files[0].state = ModelFile.State.DOWNLOADED

        # Original should be unchanged
        original = self.model.get_file("test.txt")
        self.assertEqual(ModelFile.State.DEFAULT, original.state)

    def test_get_files_returns_all_files(self):
        f1 = ModelFile("a.txt", False)
        f2 = ModelFile("b.txt", False)
        f3 = ModelFile("c.txt", True)
        self.model.add_file(f1)
        self.model.add_file(f2)
        self.model.add_file(f3)

        files = self.registry.get_files()
        names = {f.name for f in files}
        self.assertEqual({"a.txt", "b.txt", "c.txt"}, names)

    def test_get_file_returns_directly(self):
        f = ModelFile("test.txt", False)
        f.state = ModelFile.State.DEFAULT
        self.model.add_file(f)

        result = self.registry.get_file("test.txt")
        # Should be the same object, not a copy
        self.assertIs(f, result)

    def test_add_and_remove_listener(self):
        listener = _TestListener()
        self.registry.add_listener(listener)

        f = ModelFile("test.txt", False)
        self.model.add_file(f)
        self.assertEqual(1, len(listener.added))

        self.registry.remove_listener(listener)

        f2 = ModelFile("test2.txt", False)
        self.model.add_file(f2)
        # Should not have received the second add
        self.assertEqual(1, len(listener.added))

    def test_get_files_and_add_listener_is_atomic(self):
        f1 = ModelFile("existing.txt", False)
        self.model.add_file(f1)

        listener = _TestListener()
        files = self.registry.get_files_and_add_listener(listener)

        # Should return existing files
        self.assertEqual(1, len(files))
        self.assertEqual("existing.txt", files[0].name)

        # Listener should receive subsequent updates
        f2 = ModelFile("new.txt", False)
        self.model.add_file(f2)
        self.assertEqual(1, len(listener.added))
        self.assertEqual("new.txt", listener.added[0].name)

    def test_apply_diff_add_file(self):
        new_model = Model()
        logger = logging.getLogger("TestModelRegistry.new")
        logger.addHandler(logging.NullHandler())
        new_model.set_base_logger(logger)

        f = ModelFile("added.txt", False)
        new_model.add_file(f)

        diffs = self.registry.apply_diff(new_model)

        self.assertEqual(1, len(diffs))
        self.assertEqual(ModelDiff.Change.ADDED, diffs[0].change)
        self.assertEqual("added.txt", diffs[0].new_file.name)

        # Verify the model was updated
        result = self.registry.get_file("added.txt")
        self.assertEqual("added.txt", result.name)

    def test_apply_diff_remove_file(self):
        f = ModelFile("to_remove.txt", False)
        self.model.add_file(f)

        # New model is empty -- the file is removed
        new_model = Model()
        logger = logging.getLogger("TestModelRegistry.new")
        logger.addHandler(logging.NullHandler())
        new_model.set_base_logger(logger)

        diffs = self.registry.apply_diff(new_model)

        self.assertEqual(1, len(diffs))
        self.assertEqual(ModelDiff.Change.REMOVED, diffs[0].change)
        self.assertEqual("to_remove.txt", diffs[0].old_file.name)

    def test_apply_diff_update_file(self):
        f = ModelFile("update_me.txt", False)
        f.state = ModelFile.State.DEFAULT
        self.model.add_file(f)

        new_model = Model()
        logger = logging.getLogger("TestModelRegistry.new")
        logger.addHandler(logging.NullHandler())
        new_model.set_base_logger(logger)
        f_updated = ModelFile("update_me.txt", False)
        f_updated.state = ModelFile.State.DOWNLOADED
        new_model.add_file(f_updated)

        diffs = self.registry.apply_diff(new_model)

        self.assertEqual(1, len(diffs))
        self.assertEqual(ModelDiff.Change.UPDATED, diffs[0].change)
        self.assertEqual(ModelFile.State.DOWNLOADED, diffs[0].new_file.state)

        # Verify model is updated
        result = self.registry.get_file("update_me.txt")
        self.assertEqual(ModelFile.State.DOWNLOADED, result.state)
