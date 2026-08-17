# Copyright 2017, Inderpreet Singh, All rights reserved.

import errno
import os
import shutil
import tempfile
import unittest
from unittest import mock

from controller.move.move_process import MoveFailedResult, MoveProcess


class TestMoveProcess(unittest.TestCase):
    def setUp(self):
        self.src_dir = tempfile.mkdtemp()
        self.dst_dir = tempfile.mkdtemp()
        self._processes = []

    def tearDown(self):
        for process in self._processes:
            process.close_queues()
        shutil.rmtree(self.src_dir, ignore_errors=True)
        shutil.rmtree(self.dst_dir, ignore_errors=True)

    def _make_process(self, **kwargs):
        # The failed-result PipeStream is synchronous in-process (no feeder
        # thread), so pop_failed() needs no fake in these single-process tests.
        process = MoveProcess(**kwargs)
        self._processes.append(process)
        return process

    def _run_process(self, process):
        """Helper to run a MoveProcess synchronously via run_once()."""
        process.run_once()

    def test_move_single_file(self):
        """A single file should be moved from source to dest"""
        # Create source file
        src_file = os.path.join(self.src_dir, "test.txt")
        with open(src_file, "w") as f:
            f.write("hello world")

        process = self._make_process(source_path=self.src_dir, dest_path=self.dst_dir, file_name="test.txt")
        self._run_process(process)

        # Source should be gone, dest should exist
        self.assertFalse(os.path.exists(src_file))
        dst_file = os.path.join(self.dst_dir, "test.txt")
        self.assertTrue(os.path.exists(dst_file))
        with open(dst_file) as f:
            self.assertEqual("hello world", f.read())

    def test_move_directory(self):
        """A directory tree should be moved from source to dest"""
        # Create source directory with nested structure
        src_subdir = os.path.join(self.src_dir, "mydir")
        os.makedirs(os.path.join(src_subdir, "subdir"))
        with open(os.path.join(src_subdir, "a.txt"), "w") as f:
            f.write("file_a")
        with open(os.path.join(src_subdir, "subdir", "b.txt"), "w") as f:
            f.write("file_b")

        process = self._make_process(source_path=self.src_dir, dest_path=self.dst_dir, file_name="mydir")
        self._run_process(process)

        # Source should be gone
        self.assertFalse(os.path.exists(src_subdir))

        # Dest should have the full tree
        dst_subdir = os.path.join(self.dst_dir, "mydir")
        self.assertTrue(os.path.isdir(dst_subdir))
        with open(os.path.join(dst_subdir, "a.txt")) as f:
            self.assertEqual("file_a", f.read())
        with open(os.path.join(dst_subdir, "subdir", "b.txt")) as f:
            self.assertEqual("file_b", f.read())

    def test_move_nonexistent_source(self):
        """Moving a nonexistent source should log error and not crash"""
        process = self._make_process(source_path=self.src_dir, dest_path=self.dst_dir, file_name="does_not_exist")
        # Should not raise
        self._run_process(process)

    def test_move_creates_dest_parent(self):
        """Dest parent directory should be created if it does not exist"""
        # Remove dst_dir so it doesn't exist
        shutil.rmtree(self.dst_dir)
        nested_dst = os.path.join(self.dst_dir, "nested", "path")

        src_file = os.path.join(self.src_dir, "test.txt")
        with open(src_file, "w") as f:
            f.write("content")

        process = self._make_process(source_path=self.src_dir, dest_path=nested_dst, file_name="test.txt")
        self._run_process(process)

        self.assertFalse(os.path.exists(src_file))
        self.assertTrue(os.path.exists(os.path.join(nested_dst, "test.txt")))

    def test_get_total_size_file(self):
        """_get_total_size should return file size for a single file"""
        path = os.path.join(self.src_dir, "sized.txt")
        with open(path, "w") as f:
            f.write("12345")
        size = MoveProcess._get_total_size(path)
        self.assertEqual(5, size)

    def test_get_total_size_directory(self):
        """_get_total_size should return sum of all file sizes in a directory"""
        subdir = os.path.join(self.src_dir, "tree")
        os.makedirs(os.path.join(subdir, "inner"))
        with open(os.path.join(subdir, "a.txt"), "w") as f:
            f.write("aaa")  # 3 bytes
        with open(os.path.join(subdir, "inner", "b.txt"), "w") as f:
            f.write("bbbbb")  # 5 bytes
        size = MoveProcess._get_total_size(subdir)
        self.assertEqual(8, size)

    def test_move_preserves_file_content(self):
        """File content should be identical after move"""
        content = "x" * 10000
        src_file = os.path.join(self.src_dir, "big.txt")
        with open(src_file, "w") as f:
            f.write(content)

        process = self._make_process(source_path=self.src_dir, dest_path=self.dst_dir, file_name="big.txt")
        self._run_process(process)

        dst_file = os.path.join(self.dst_dir, "big.txt")
        with open(dst_file) as f:
            self.assertEqual(content, f.read())

    def test_move_empty_directory(self):
        """An empty directory should be moved successfully"""
        src_empty = os.path.join(self.src_dir, "emptydir")
        os.makedirs(src_empty)

        process = self._make_process(source_path=self.src_dir, dest_path=self.dst_dir, file_name="emptydir")
        self._run_process(process)

        self.assertFalse(os.path.exists(src_empty))
        self.assertTrue(os.path.isdir(os.path.join(self.dst_dir, "emptydir")))
        # Happy path must not report any failure
        self.assertEqual([], process.pop_failed())

    # --- Failure reporting (#510) ---

    def test_move_nonexistent_source_reports_failure(self):
        """A vanished source must be reported on the failed queue, not silently dropped"""
        process = self._make_process(
            source_path=self.src_dir, dest_path=self.dst_dir, file_name="does_not_exist", pair_id="pair-1"
        )
        self._run_process(process)

        failures = process.pop_failed()
        self.assertEqual(1, len(failures))
        result = failures[0]
        self.assertIsInstance(result, MoveFailedResult)
        self.assertEqual("does_not_exist", result.name)
        self.assertEqual("pair-1", result.pair_id)
        self.assertIn("does not exist", result.error_message)

    def test_move_size_mismatch_reports_failure_and_keeps_source(self):
        """A forced size mismatch must report failure and leave the source intact"""
        src_subdir = os.path.join(self.src_dir, "mydir")
        os.makedirs(src_subdir)
        with open(os.path.join(src_subdir, "a.txt"), "w") as f:
            f.write("aaaa")

        process = self._make_process(
            source_path=self.src_dir, dest_path=self.dst_dir, file_name="mydir", pair_id="pair-2"
        )

        # Force the copied-size check to disagree with the source size.
        real_total = MoveProcess._get_total_size
        with (
            mock.patch.object(MoveProcess, "_get_copied_size", staticmethod(lambda src, dst: real_total(src) + 1)),
            mock.patch("controller.move.move_process.os.rename", side_effect=OSError(errno.EXDEV, "cross-device")),
        ):
            self._run_process(process)

        failures = process.pop_failed()
        self.assertEqual(1, len(failures))
        self.assertEqual("mydir", failures[0].name)
        self.assertEqual("pair-2", failures[0].pair_id)
        # Source must NOT be deleted when verification fails
        self.assertTrue(os.path.exists(src_subdir))

    def test_move_into_nonempty_dest_succeeds(self):
        """Merging into a pre-existing non-empty destination must succeed without false mismatch"""
        # Source tree
        src_subdir = os.path.join(self.src_dir, "mydir")
        os.makedirs(src_subdir)
        with open(os.path.join(src_subdir, "new.txt"), "w") as f:
            f.write("brand new content")

        # Pre-existing destination tree with an unrelated, larger file already present
        dst_subdir = os.path.join(self.dst_dir, "mydir")
        os.makedirs(dst_subdir)
        with open(os.path.join(dst_subdir, "old.txt"), "w") as f:
            f.write("x" * 9999)  # larger than the source so whole-dir size would mismatch

        process = self._make_process(source_path=self.src_dir, dest_path=self.dst_dir, file_name="mydir")
        # Force the cross-device copy path so the size verification runs.
        with mock.patch("controller.move.move_process.os.rename", side_effect=OSError(errno.EXDEV, "cross-device")):
            self._run_process(process)

        # No false mismatch -- move succeeds and source is removed
        self.assertEqual([], process.pop_failed())
        self.assertFalse(os.path.exists(src_subdir))
        self.assertTrue(os.path.exists(os.path.join(dst_subdir, "new.txt")))
        # Pre-existing destination file untouched
        self.assertTrue(os.path.exists(os.path.join(dst_subdir, "old.txt")))

    def test_move_rename_enotempty_falls_back_to_copy(self):
        """ENOTEMPTY from os.rename must fall back to copy+delete, not re-raise"""
        src_subdir = os.path.join(self.src_dir, "mydir")
        os.makedirs(src_subdir)
        with open(os.path.join(src_subdir, "a.txt"), "w") as f:
            f.write("payload")

        process = self._make_process(source_path=self.src_dir, dest_path=self.dst_dir, file_name="mydir")
        with mock.patch(
            "controller.move.move_process.os.rename",
            side_effect=OSError(errno.ENOTEMPTY, "directory not empty"),
        ):
            # Must not raise
            self._run_process(process)

        self.assertEqual([], process.pop_failed())
        self.assertFalse(os.path.exists(src_subdir))
        self.assertTrue(os.path.exists(os.path.join(self.dst_dir, "mydir", "a.txt")))

    def test_move_rename_unexpected_oserror_reraises(self):
        """An unexpected OSError from os.rename must still propagate"""
        src_file = os.path.join(self.src_dir, "test.txt")
        with open(src_file, "w") as f:
            f.write("content")

        process = self._make_process(source_path=self.src_dir, dest_path=self.dst_dir, file_name="test.txt")
        with mock.patch(
            "controller.move.move_process.os.rename",
            side_effect=OSError(errno.EACCES, "permission denied"),
        ):
            with self.assertRaises(OSError):
                self._run_process(process)

    def test_move_defers_when_lftp_temp_files_present(self):
        """A staging tree still holding *.lftp temp files is not finalized: the
        move must defer (recoverable failure) without copying or deleting, so it
        is retried once lftp finishes renaming."""
        src_subdir = os.path.join(self.src_dir, "mydir")
        os.makedirs(src_subdir)
        with open(os.path.join(src_subdir, "done.mkv"), "w") as f:
            f.write("finished")
        # An in-flight lftp temp file makes the tree non-quiescent.
        with open(os.path.join(src_subdir, "inprogress.mkv.lftp"), "w") as f:
            f.write("partial")

        process = self._make_process(
            source_path=self.src_dir, dest_path=self.dst_dir, file_name="mydir", pair_id="pair-3"
        )
        self._run_process(process)

        failures = process.pop_failed()
        self.assertEqual(1, len(failures))
        self.assertIn("not finalized", failures[0].error_message)
        # Nothing copied or deleted: source intact, dest not created.
        self.assertTrue(os.path.exists(src_subdir))
        self.assertFalse(os.path.exists(os.path.join(self.dst_dir, "mydir")))

    def test_move_copy_error_reports_failure_and_keeps_source(self):
        """A copy error (e.g. an lftp temp file renamed mid-copy) must be reported
        as a recoverable failure with the source kept — never raised/crashing the
        controller."""
        src_subdir = os.path.join(self.src_dir, "mydir")
        os.makedirs(src_subdir)
        with open(os.path.join(src_subdir, "a.txt"), "w") as f:
            f.write("payload")

        process = self._make_process(
            source_path=self.src_dir, dest_path=self.dst_dir, file_name="mydir", pair_id="pair-4"
        )
        with (
            mock.patch("controller.move.move_process.os.rename", side_effect=OSError(errno.EXDEV, "cross-device")),
            mock.patch("controller.move.move_process.shutil.copytree", side_effect=shutil.Error("boom")),
        ):
            # Must not raise.
            self._run_process(process)

        failures = process.pop_failed()
        self.assertEqual(1, len(failures))
        self.assertIn("copy failed", failures[0].error_message)
        # Source must remain intact.
        self.assertTrue(os.path.exists(src_subdir))

    def test_get_copied_size_ignores_preexisting_dest_files(self):
        """_get_copied_size sums only files that exist in the source subtree"""
        src_subdir = os.path.join(self.src_dir, "mydir")
        os.makedirs(os.path.join(src_subdir, "inner"))
        with open(os.path.join(src_subdir, "a.txt"), "w") as f:
            f.write("aaa")  # 3
        with open(os.path.join(src_subdir, "inner", "b.txt"), "w") as f:
            f.write("bb")  # 2

        dst_subdir = os.path.join(self.dst_dir, "mydir")
        os.makedirs(os.path.join(dst_subdir, "inner"))
        # Mirror the source files
        with open(os.path.join(dst_subdir, "a.txt"), "w") as f:
            f.write("aaa")  # 3
        with open(os.path.join(dst_subdir, "inner", "b.txt"), "w") as f:
            f.write("bb")  # 2
        # Plus an unrelated pre-existing file that must NOT be counted
        with open(os.path.join(dst_subdir, "preexisting.txt"), "w") as f:
            f.write("ignored entirely")

        self.assertEqual(5, MoveProcess._get_copied_size(src_subdir, dst_subdir))
