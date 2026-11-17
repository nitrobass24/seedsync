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

    # --- Nested names: multi-level dest parents + staging prune ---

    def test_move_nested_name_creates_dest_parents_and_prunes_empty_staging_dirs(self):
        """A nested name's move must create every missing dest parent level and,
        once the source is gone, remove the staging dirs it emptied up to (not
        including) source_path."""
        nested_dir = os.path.join(self.src_dir, "Top", "Sub")
        os.makedirs(nested_dir)
        src_file = os.path.join(nested_dir, "f.bin")
        with open(src_file, "w") as f:
            f.write("data")

        process = self._make_process(source_path=self.src_dir, dest_path=self.dst_dir, file_name="Top/Sub/f.bin")
        self._run_process(process)

        dst_file = os.path.join(self.dst_dir, "Top", "Sub", "f.bin")
        self.assertTrue(os.path.exists(dst_file))
        with open(dst_file) as f:
            self.assertEqual("data", f.read())
        self.assertFalse(os.path.exists(os.path.join(self.src_dir, "Top", "Sub")))
        self.assertFalse(os.path.exists(os.path.join(self.src_dir, "Top")))
        self.assertTrue(os.path.exists(self.src_dir))
        self.assertEqual([], process.pop_failed())

    def test_move_nested_prune_stops_at_nonempty_sibling(self):
        """Pruning stops at the first staging dir still holding something, such
        as a sibling file from another job - that dir (and its ancestors) must
        survive."""
        nested_dir = os.path.join(self.src_dir, "Top", "Sub")
        os.makedirs(nested_dir)
        src_file = os.path.join(nested_dir, "f.bin")
        with open(src_file, "w") as f:
            f.write("data")
        sibling_file = os.path.join(self.src_dir, "Top", "sibling.txt")
        with open(sibling_file, "w") as f:
            f.write("keepme")

        process = self._make_process(source_path=self.src_dir, dest_path=self.dst_dir, file_name="Top/Sub/f.bin")
        self._run_process(process)

        self.assertFalse(os.path.exists(os.path.join(self.src_dir, "Top", "Sub")))
        self.assertTrue(os.path.exists(os.path.join(self.src_dir, "Top")))
        self.assertTrue(os.path.exists(sibling_file))

    def test_move_nested_prune_keeps_dir_a_queued_sibling_needs(self):
        """A queued nested job's parent dir is made when it's queued, and pget
        won't recreate it, so an emptied dir it needs must survive the prune."""
        nested_dir = os.path.join(self.src_dir, "Top", "Sub")
        os.makedirs(nested_dir)
        with open(os.path.join(nested_dir, "a.bin"), "w") as f:
            f.write("data")

        process = self._make_process(
            source_path=self.src_dir,
            dest_path=self.dst_dir,
            file_name="Top/Sub/a.bin",
            keep_parents_of=frozenset({"Top/Sub/b.bin"}),
        )
        self._run_process(process)

        self.assertEqual([], process.pop_failed())
        self.assertTrue(os.path.exists(os.path.join(self.dst_dir, "Top", "Sub", "a.bin")))
        self.assertTrue(os.path.isdir(nested_dir))

    def test_move_nested_via_copy_delete_prunes_empty_staging_dirs(self):
        """The copy+delete fallback path must prune the same as the rename path."""
        nested_dir = os.path.join(self.src_dir, "Top", "Sub")
        os.makedirs(nested_dir)
        src_file = os.path.join(nested_dir, "f.bin")
        with open(src_file, "w") as f:
            f.write("data")

        process = self._make_process(source_path=self.src_dir, dest_path=self.dst_dir, file_name="Top/Sub/f.bin")
        with mock.patch("controller.move.move_process.os.rename", side_effect=OSError(errno.EXDEV, "cross-device")):
            self._run_process(process)

        dst_file = os.path.join(self.dst_dir, "Top", "Sub", "f.bin")
        self.assertTrue(os.path.exists(dst_file))
        self.assertFalse(os.path.exists(os.path.join(self.src_dir, "Top", "Sub")))
        self.assertFalse(os.path.exists(os.path.join(self.src_dir, "Top")))
        self.assertEqual([], process.pop_failed())

    # --- expected_size: skip (not fail) an in-flight nested download (#811) ---

    def test_expected_size_larger_than_source_skips_move_without_failure(self):
        """A nested job's lftp process ending early (e.g. a Stop) leaves a
        smaller-than-expected source; the move must be skipped, not failed, and
        the source left untouched for a later re-queue to resume."""
        src_file = os.path.join(self.src_dir, "test.txt")
        with open(src_file, "w") as f:
            f.write("12345")  # 5 bytes

        process = self._make_process(
            source_path=self.src_dir, dest_path=self.dst_dir, file_name="test.txt", expected_size=100
        )
        self._run_process(process)

        self.assertEqual([], process.pop_failed())
        self.assertTrue(os.path.exists(src_file))
        self.assertFalse(os.path.exists(os.path.join(self.dst_dir, "test.txt")))

    def test_expected_size_set_with_temp_files_skips_without_failure(self):
        """With expected_size set, lftp temp files present also means skip (not
        the recoverable-failure path used when expected_size is None)."""
        src_subdir = os.path.join(self.src_dir, "mydir")
        os.makedirs(src_subdir)
        with open(os.path.join(src_subdir, "done.mkv"), "w") as f:
            f.write("finished")
        with open(os.path.join(src_subdir, "inprogress.mkv.lftp"), "w") as f:
            f.write("partial")

        process = self._make_process(
            source_path=self.src_dir, dest_path=self.dst_dir, file_name="mydir", expected_size=1000
        )
        self._run_process(process)

        self.assertEqual([], process.pop_failed())
        self.assertTrue(os.path.exists(src_subdir))
        self.assertFalse(os.path.exists(os.path.join(self.dst_dir, "mydir")))

    def test_move_applies_umask_modes_at_destination(self):
        """#811: lftp leaves 0664/0775 in staging; the moved copy gets 0666/0777 & ~umask."""
        import stat

        src_tree = os.path.join(self.src_dir, "Show.S01")
        os.makedirs(src_tree)
        src_file = os.path.join(src_tree, "ep1.mkv")
        with open(src_file, "w") as f:
            f.write("x")
        os.chmod(src_tree, 0o775)
        os.chmod(src_file, 0o664)

        process = self._make_process(
            source_path=self.src_dir, dest_path=self.dst_dir, file_name="Show.S01", umask=0o000
        )
        self._run_process(process)

        dst_tree = os.path.join(self.dst_dir, "Show.S01")
        self.assertEqual(0o777, stat.S_IMODE(os.stat(dst_tree).st_mode))
        self.assertEqual(0o666, stat.S_IMODE(os.stat(os.path.join(dst_tree, "ep1.mkv")).st_mode))

    # --- nested_expected_sizes: leave a stopped nested job's partial in staging ---

    def test_top_level_move_leaves_incomplete_nested_download_in_staging(self):
        """Repro: a top-level staging->final move used to carry a stopped nested
        partial out of staging into the final dir. With nested_expected_sizes set,
        the complete sibling must still move while the nested partial under it
        stays in staging for its own job to resume."""
        top_dir = os.path.join(self.src_dir, "Top")
        os.makedirs(os.path.join(top_dir, "Sub"))
        with open(os.path.join(top_dir, "a.bin"), "w") as f:
            f.write("complete")
        with open(os.path.join(top_dir, "Sub", "big.bin"), "w") as f:
            f.write("short")  # 5 bytes, far under expected

        process = self._make_process(
            source_path=self.src_dir,
            dest_path=self.dst_dir,
            file_name="Top",
            nested_expected_sizes={"Sub/big.bin": 1000},
        )
        self._run_process(process)

        self.assertEqual([], process.pop_failed())
        self.assertTrue(os.path.exists(os.path.join(self.dst_dir, "Top", "a.bin")))
        self.assertTrue(os.path.exists(os.path.join(self.src_dir, "Top", "Sub", "big.bin")))
        self.assertFalse(os.path.exists(os.path.join(self.dst_dir, "Top", "Sub", "big.bin")))
        # Sub holds only the partial, so no empty Sub is created at the destination
        self.assertFalse(os.path.exists(os.path.join(self.dst_dir, "Top", "Sub")))

    def test_top_level_move_leaves_temp_named_nested_partial_in_staging(self):
        """With lftp temp files on, a stopped nested file exists only as
        '<name>.lftp'. It is the incomplete entry: left behind, and it doesn't
        defer the rest of the tree."""
        top_dir = os.path.join(self.src_dir, "Top")
        os.makedirs(os.path.join(top_dir, "Sub"))
        with open(os.path.join(top_dir, "a.bin"), "w") as f:
            f.write("complete")
        with open(os.path.join(top_dir, "Sub", "big.bin.lftp"), "w") as f:
            f.write("short")

        process = self._make_process(
            source_path=self.src_dir,
            dest_path=self.dst_dir,
            file_name="Top",
            nested_expected_sizes={"Sub/big.bin": 1000},
        )
        self._run_process(process)

        self.assertEqual([], process.pop_failed())
        self.assertTrue(os.path.exists(os.path.join(self.dst_dir, "Top", "a.bin")))
        self.assertTrue(os.path.exists(os.path.join(self.src_dir, "Top", "Sub", "big.bin.lftp")))
        self.assertFalse(os.path.exists(os.path.join(self.dst_dir, "Top", "Sub")))

    def test_top_level_move_moves_everything_when_nested_download_complete(self):
        """A nested download whose size has caught up to expected moves along
        with the rest of the tree; nothing is left behind."""
        top_dir = os.path.join(self.src_dir, "Top")
        os.makedirs(os.path.join(top_dir, "Sub"))
        with open(os.path.join(top_dir, "a.bin"), "w") as f:
            f.write("complete")
        with open(os.path.join(top_dir, "Sub", "big.bin"), "w") as f:
            f.write("12345")  # 5 bytes, matches expected

        process = self._make_process(
            source_path=self.src_dir,
            dest_path=self.dst_dir,
            file_name="Top",
            nested_expected_sizes={"Sub/big.bin": 5},
        )
        self._run_process(process)

        self.assertEqual([], process.pop_failed())
        self.assertTrue(os.path.exists(os.path.join(self.dst_dir, "Top", "a.bin")))
        self.assertTrue(os.path.exists(os.path.join(self.dst_dir, "Top", "Sub", "big.bin")))
        self.assertFalse(os.path.exists(os.path.join(self.src_dir, "Top")))

    def test_nested_expected_size_none_leaves_download_in_staging(self):
        """An unresolved nested row (ModelError during lookup in the pipeline)
        maps to a None size here, which is always treated as incomplete."""
        top_dir = os.path.join(self.src_dir, "Top")
        os.makedirs(os.path.join(top_dir, "Sub"))
        with open(os.path.join(top_dir, "a.bin"), "w") as f:
            f.write("complete")
        with open(os.path.join(top_dir, "Sub", "big.bin"), "w") as f:
            f.write("anything")

        process = self._make_process(
            source_path=self.src_dir,
            dest_path=self.dst_dir,
            file_name="Top",
            nested_expected_sizes={"Sub/big.bin": None},
        )
        self._run_process(process)

        self.assertEqual([], process.pop_failed())
        self.assertTrue(os.path.exists(os.path.join(self.dst_dir, "Top", "a.bin")))
        self.assertTrue(os.path.exists(os.path.join(self.src_dir, "Top", "Sub", "big.bin")))

    def test_nested_lftp_temp_file_in_listed_path_skipped_without_deferral(self):
        """An lftp temp file inside a listed (incomplete) nested path must not
        defer the whole move."""
        top_dir = os.path.join(self.src_dir, "Top")
        os.makedirs(os.path.join(top_dir, "Sub2"))
        with open(os.path.join(top_dir, "a.bin"), "w") as f:
            f.write("complete")
        with open(os.path.join(top_dir, "Sub2", "x.bin.lftp"), "w") as f:
            f.write("partial")

        process = self._make_process(
            source_path=self.src_dir,
            dest_path=self.dst_dir,
            file_name="Top",
            nested_expected_sizes={"Sub2": 999},
        )
        self._run_process(process)

        self.assertEqual([], process.pop_failed())
        self.assertTrue(os.path.exists(os.path.join(self.dst_dir, "Top", "a.bin")))
        self.assertTrue(os.path.exists(os.path.join(self.src_dir, "Top", "Sub2", "x.bin.lftp")))

    def test_temp_file_outside_listed_nested_paths_still_defers(self):
        """A temp file outside any listed nested path still defers the whole
        move as a recoverable failure (existing behaviour, preserved alongside
        the nested-skip list)."""
        top_dir = os.path.join(self.src_dir, "Top")
        os.makedirs(top_dir)
        with open(os.path.join(top_dir, "a.bin"), "w") as f:
            f.write("complete")
        with open(os.path.join(top_dir, "stray.mkv.lftp"), "w") as f:
            f.write("partial")

        process = self._make_process(
            source_path=self.src_dir,
            dest_path=self.dst_dir,
            file_name="Top",
            nested_expected_sizes={},
            pair_id="pair-5",
        )
        self._run_process(process)

        failures = process.pop_failed()
        self.assertEqual(1, len(failures))
        self.assertIn("not finalized", failures[0].error_message)
        self.assertTrue(os.path.exists(top_dir))
        self.assertFalse(os.path.exists(os.path.join(self.dst_dir, "Top")))

    def test_nested_expected_sizes_entry_missing_from_staging_is_ignored(self):
        """A listed nested path that no longer exists in staging (already moved
        or never downloaded) is ignored - the top-level move proceeds normally."""
        top_dir = os.path.join(self.src_dir, "Top")
        os.makedirs(top_dir)
        with open(os.path.join(top_dir, "a.bin"), "w") as f:
            f.write("complete")

        process = self._make_process(
            source_path=self.src_dir,
            dest_path=self.dst_dir,
            file_name="Top",
            nested_expected_sizes={"Sub/big.bin": 1000},
        )
        self._run_process(process)

        self.assertEqual([], process.pop_failed())
        self.assertTrue(os.path.exists(os.path.join(self.dst_dir, "Top", "a.bin")))
        self.assertFalse(os.path.exists(os.path.join(self.src_dir, "Top")))

    def test_sibling_subtree_without_exclusions_moves_whole_via_rename(self):
        """A subtree containing no incomplete nested path moves as one rename
        of the whole subtree, not file-by-file."""
        top_dir = os.path.join(self.src_dir, "Top")
        other_dir = os.path.join(top_dir, "Other")
        os.makedirs(other_dir)
        with open(os.path.join(other_dir, "c.bin"), "w") as f:
            f.write("complete")
        sub_dir = os.path.join(top_dir, "Sub")
        os.makedirs(sub_dir)
        with open(os.path.join(sub_dir, "big.bin"), "w") as f:
            f.write("short")

        process = self._make_process(
            source_path=self.src_dir,
            dest_path=self.dst_dir,
            file_name="Top",
            nested_expected_sizes={"Sub/big.bin": 1000},
        )
        dst_other = os.path.join(self.dst_dir, "Top", "Other")
        with mock.patch("controller.move.move_process.os.rename", side_effect=os.rename) as mock_rename:
            self._run_process(process)

        self.assertTrue(os.path.exists(os.path.join(dst_other, "c.bin")))
        self.assertIn(mock.call(other_dir, dst_other), mock_rename.call_args_list)
        self.assertEqual([], process.pop_failed())

    def test_cross_device_move_tree_leaves_partial_and_moves_rest(self):
        """EXDEV from os.rename inside the tree move must fall back to
        copy+delete per subtree, still leaving the incomplete nested path
        behind."""
        top_dir = os.path.join(self.src_dir, "Top")
        os.makedirs(top_dir)
        with open(os.path.join(top_dir, "a.bin"), "w") as f:
            f.write("complete")
        sub_dir = os.path.join(top_dir, "Sub")
        os.makedirs(sub_dir)
        with open(os.path.join(sub_dir, "big.bin"), "w") as f:
            f.write("short")

        process = self._make_process(
            source_path=self.src_dir,
            dest_path=self.dst_dir,
            file_name="Top",
            nested_expected_sizes={"Sub/big.bin": 1000},
        )
        with mock.patch("controller.move.move_process.os.rename", side_effect=OSError(errno.EXDEV, "cross-device")):
            self._run_process(process)

        self.assertEqual([], process.pop_failed())
        self.assertTrue(os.path.exists(os.path.join(self.dst_dir, "Top", "a.bin")))
        self.assertTrue(os.path.exists(os.path.join(self.src_dir, "Top", "Sub", "big.bin")))
        self.assertFalse(os.path.exists(os.path.join(self.dst_dir, "Top", "Sub", "big.bin")))

    def test_merge_into_existing_destination_leaves_other_files_alone(self):
        """#811: a staged tree merged into an existing folder must not widen the
        modes of files that were already there."""
        import stat

        src_tree = os.path.join(self.src_dir, "Show.S01")
        os.makedirs(src_tree)
        with open(os.path.join(src_tree, "ep2.mkv"), "w") as f:
            f.write("x")
        os.chmod(os.path.join(src_tree, "ep2.mkv"), 0o664)
        dst_tree = os.path.join(self.dst_dir, "Show.S01")
        os.makedirs(dst_tree)
        private = os.path.join(dst_tree, "notes.txt")
        with open(private, "w") as f:
            f.write("mine")
        os.chmod(private, 0o600)
        os.chmod(dst_tree, 0o700)

        with mock.patch("os.rename", side_effect=OSError(errno.EXDEV, "cross-device")):
            process = self._make_process(
                source_path=self.src_dir, dest_path=self.dst_dir, file_name="Show.S01", umask=0o000
            )
            self._run_process(process)

        # Pre-existing content keeps its modes (copytree's copystat would have
        # put the source's 0775 on the directory; the UMASK pass must not widen it)
        self.assertEqual(0o700, stat.S_IMODE(os.stat(dst_tree).st_mode))
        self.assertEqual(0o600, stat.S_IMODE(os.stat(private).st_mode))
        # The moved file gets the UMASK treatment
        self.assertEqual(0o666, stat.S_IMODE(os.stat(os.path.join(dst_tree, "ep2.mkv")).st_mode))

    def test_partial_tree_move_applies_umask_only_to_what_it_moved(self):
        """#811 with a nested partial left behind: dirs the tree move creates at
        the destination and the files it moves get the UMASK modes; a destination
        dir that was already there keeps its own."""
        import stat

        top_dir = os.path.join(self.src_dir, "Top")
        os.makedirs(os.path.join(top_dir, "New", "Sub"))
        with open(os.path.join(top_dir, "New", "a.bin"), "w") as f:
            f.write("complete")
        with open(os.path.join(top_dir, "New", "Sub", "big.bin"), "w") as f:
            f.write("short")
        os.chmod(os.path.join(top_dir, "New", "a.bin"), 0o664)
        dst_top = os.path.join(self.dst_dir, "Top")
        os.makedirs(dst_top)
        os.chmod(dst_top, 0o700)

        process = self._make_process(
            source_path=self.src_dir,
            dest_path=self.dst_dir,
            file_name="Top",
            umask=0o000,
            nested_expected_sizes={"New/Sub/big.bin": 1000},
        )
        self._run_process(process)

        self.assertEqual([], process.pop_failed())
        self.assertTrue(os.path.exists(os.path.join(self.src_dir, "Top", "New", "Sub", "big.bin")))
        self.assertEqual(0o700, stat.S_IMODE(os.stat(dst_top).st_mode))
        self.assertEqual(0o777, stat.S_IMODE(os.stat(os.path.join(dst_top, "New")).st_mode))
        self.assertEqual(0o666, stat.S_IMODE(os.stat(os.path.join(dst_top, "New", "a.bin")).st_mode))

    def test_single_file_move_applies_umask_mode(self):
        """#811: a moved single file gets 0666 & ~umask. Its only entry is ".",
        which used to make the chmod target "file/." and fail with ENOTDIR."""
        import stat

        src_file = os.path.join(self.src_dir, "movie.mkv")
        with open(src_file, "w") as f:
            f.write("x")
        os.chmod(src_file, 0o664)

        process = self._make_process(
            source_path=self.src_dir, dest_path=self.dst_dir, file_name="movie.mkv", umask=0o027
        )
        self._run_process(process)

        self.assertEqual([], process.pop_failed())
        self.assertEqual(0o640, stat.S_IMODE(os.stat(os.path.join(self.dst_dir, "movie.mkv")).st_mode))
