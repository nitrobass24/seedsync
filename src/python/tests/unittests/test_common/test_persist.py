# Copyright 2017, Inderpreet Singh, All rights reserved.

import unittest
import tempfile
import shutil
import os

from unittest.mock import patch

from common import overrides, Persist, AppError, Localization


class DummyPersist(Persist):
    def __init__(self):
        self.my_content = None

    @classmethod
    @overrides(Persist)
    def from_str(cls: "DummyPersist", content: str) -> "DummyPersist":
        persist = DummyPersist()
        persist.my_content = content
        return persist

    @overrides(Persist)
    def to_str(self) -> str:
        return self.my_content


class TestPersist(unittest.TestCase):
    @overrides(unittest.TestCase)
    def setUp(self):
        # Create a temp directory
        self.temp_dir = tempfile.mkdtemp(prefix="test_persist")

    @overrides(unittest.TestCase)
    def tearDown(self):
        # Cleanup
        shutil.rmtree(self.temp_dir)

    def test_from_file(self):
        file_path = os.path.join(self.temp_dir, "persist")
        with open(file_path, "w") as f:
            f.write("some test content")
        persist = DummyPersist.from_file(file_path)
        self.assertEqual("some test content", persist.my_content)

    def test_from_file_non_existing(self):
        file_path = os.path.join(self.temp_dir, "persist")
        with self.assertRaises(AppError) as context:
            DummyPersist.from_file(file_path)
        self.assertEqual(Localization.Error.MISSING_FILE.format(file_path), str(context.exception))

    def test_to_file_non_existing(self):
        file_path = os.path.join(self.temp_dir, "persist")
        persist = DummyPersist()
        persist.my_content = "write out some content"
        persist.to_file(file_path)
        self.assertTrue(os.path.isfile(file_path))
        with open(file_path, "r") as f:
            self.assertEqual("write out some content", f.read())

    def test_to_file_overwrite(self):
        file_path = os.path.join(self.temp_dir, "persist")
        with open(file_path, "w") as f:
            f.write("pre-existing content")
            f.flush()
        persist = DummyPersist()
        persist.my_content = "write out some new content"
        persist.to_file(file_path)
        self.assertTrue(os.path.isfile(file_path))
        with open(file_path, "r") as f:
            self.assertEqual("write out some new content", f.read())

    def test_to_file_atomic_preserves_content_on_write_error(self):
        """If to_str() raises, the original file must not be corrupted"""
        file_path = os.path.join(self.temp_dir, "persist")
        with open(file_path, "w") as f:
            f.write("original content")

        persist = DummyPersist()
        persist.my_content = "new content"

        # Simulate an error during write by making os.fsync raise
        with patch("os.fsync", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                persist.to_file(file_path)

        # Original file should be untouched
        with open(file_path, "r") as f:
            self.assertEqual("original content", f.read())

        # No temp files should be left behind
        remaining = [f for f in os.listdir(self.temp_dir) if f.startswith(".tmp_persist_")]
        self.assertEqual([], remaining)

    def test_to_file_no_temp_file_left_on_success(self):
        """Successful write should not leave temp files behind"""
        file_path = os.path.join(self.temp_dir, "persist")
        persist = DummyPersist()
        persist.my_content = "some content"
        persist.to_file(file_path)

        remaining = [f for f in os.listdir(self.temp_dir) if f.startswith(".tmp_persist_")]
        self.assertEqual([], remaining)
