# Copyright 2017, Inderpreet Singh, All rights reserved.

import unittest
import tempfile
import shutil
import os
from unittest.mock import patch

from common import overrides, Persist, AppError, Localization
from common.persist import _BACKUP_DIR_NAME, _MAX_BACKUPS


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


class TestPersistBackup(unittest.TestCase):
    @overrides(unittest.TestCase)
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="test_persist_backup")

    @overrides(unittest.TestCase)
    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_no_backup_when_file_does_not_exist(self):
        """No backup directory should be created for a new file"""
        file_path = os.path.join(self.temp_dir, "settings.cfg")
        persist = DummyPersist()
        persist.my_content = "new content"
        persist.to_file(file_path)

        backup_dir = os.path.join(self.temp_dir, _BACKUP_DIR_NAME)
        self.assertFalse(os.path.exists(backup_dir))

    def test_backup_created_on_overwrite(self):
        """Overwriting an existing file should create a backup"""
        file_path = os.path.join(self.temp_dir, "settings.cfg")
        with open(file_path, "w") as f:
            f.write("original content")

        persist = DummyPersist()
        persist.my_content = "new content"
        persist.to_file(file_path)

        backup_dir = os.path.join(self.temp_dir, _BACKUP_DIR_NAME)
        self.assertTrue(os.path.isdir(backup_dir))
        backups = os.listdir(backup_dir)
        self.assertEqual(1, len(backups))
        self.assertTrue(backups[0].startswith("settings-"))
        self.assertTrue(backups[0].endswith(".cfg"))

        # Backup should contain the old content
        with open(os.path.join(backup_dir, backups[0]), "r") as f:
            self.assertEqual("original content", f.read())

    def test_backup_uses_iso_timestamp(self):
        """Backup filename should contain ISO 8601 style timestamp"""
        file_path = os.path.join(self.temp_dir, "settings.cfg")
        with open(file_path, "w") as f:
            f.write("content")

        with patch("common.persist.datetime") as mock_dt:
            mock_dt.now.return_value.strftime.return_value = "2026-03-03T12-30-00-123456"
            persist = DummyPersist()
            persist.my_content = "new"
            persist.to_file(file_path)

        backup_dir = os.path.join(self.temp_dir, _BACKUP_DIR_NAME)
        backups = os.listdir(backup_dir)
        self.assertEqual(1, len(backups))
        self.assertEqual("settings-2026-03-03T12-30-00-123456.cfg", backups[0])

    def test_prune_keeps_only_max_backups(self):
        """Only the most recent _MAX_BACKUPS backups should be kept"""
        file_path = os.path.join(self.temp_dir, "settings.cfg")
        backup_dir = os.path.join(self.temp_dir, _BACKUP_DIR_NAME)
        os.makedirs(backup_dir)

        # Create _MAX_BACKUPS + 5 pre-existing backups with sequential timestamps
        for i in range(_MAX_BACKUPS + 5):
            backup_name = "settings-2026-01-{:02d}T00-00-00-000000.cfg".format(i + 1)
            with open(os.path.join(backup_dir, backup_name), "w") as f:
                f.write("backup {}".format(i))

        # Write the original file
        with open(file_path, "w") as f:
            f.write("current content")

        # Trigger a save which creates one more backup and prunes
        persist = DummyPersist()
        persist.my_content = "updated"
        persist.to_file(file_path)

        backups = sorted(os.listdir(backup_dir))
        self.assertEqual(_MAX_BACKUPS, len(backups))

    def test_multiple_saves_accumulate_backups(self):
        """Multiple saves should create multiple backup files"""
        file_path = os.path.join(self.temp_dir, "settings.cfg")
        backup_dir = os.path.join(self.temp_dir, _BACKUP_DIR_NAME)

        # First write (no backup since file doesn't exist yet)
        persist = DummyPersist()
        persist.my_content = "version 1"
        persist.to_file(file_path)
        self.assertFalse(os.path.exists(backup_dir))

        # Second write (backs up version 1)
        counter = [0]

        def unique_timestamp(*args, **kwargs):
            counter[0] += 1
            return "2026-03-03T12-00-{:02d}-000000".format(counter[0])

        with patch("common.persist.datetime") as mock_dt:
            mock_dt.now.return_value.strftime.side_effect = unique_timestamp
            persist.my_content = "version 2"
            persist.to_file(file_path)

            # Third write (backs up version 2)
            persist.my_content = "version 3"
            persist.to_file(file_path)

        backups = sorted(os.listdir(backup_dir))
        self.assertEqual(2, len(backups))

    def test_backup_with_no_extension(self):
        """Backup should work for files without extensions"""
        file_path = os.path.join(self.temp_dir, "persist")
        with open(file_path, "w") as f:
            f.write("original")

        persist = DummyPersist()
        persist.my_content = "new"
        persist.to_file(file_path)

        backup_dir = os.path.join(self.temp_dir, _BACKUP_DIR_NAME)
        backups = os.listdir(backup_dir)
        self.assertEqual(1, len(backups))
        self.assertTrue(backups[0].startswith("persist-"))
