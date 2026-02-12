# Copyright 2017, Inderpreet Singh, All rights reserved.

import unittest
import os
import tempfile
import shutil

from controller.move.move_process import MoveProcess


class TestMoveProcess(unittest.TestCase):
    def setUp(self):
        self.src_dir = tempfile.mkdtemp()
        self.dst_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.src_dir, ignore_errors=True)
        shutil.rmtree(self.dst_dir, ignore_errors=True)

    def _run_process(self, process):
        """Helper to run a MoveProcess synchronously via run_once()."""
        process.run_once()

    def test_move_single_file(self):
        """A single file should be moved from source to dest"""
        # Create source file
        src_file = os.path.join(self.src_dir, "test.txt")
        with open(src_file, "w") as f:
            f.write("hello world")

        process = MoveProcess(
            source_path=self.src_dir,
            dest_path=self.dst_dir,
            file_name="test.txt"
        )
        self._run_process(process)

        # Source should be gone, dest should exist
        self.assertFalse(os.path.exists(src_file))
        dst_file = os.path.join(self.dst_dir, "test.txt")
        self.assertTrue(os.path.exists(dst_file))
        with open(dst_file, "r") as f:
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

        process = MoveProcess(
            source_path=self.src_dir,
            dest_path=self.dst_dir,
            file_name="mydir"
        )
        self._run_process(process)

        # Source should be gone
        self.assertFalse(os.path.exists(src_subdir))

        # Dest should have the full tree
        dst_subdir = os.path.join(self.dst_dir, "mydir")
        self.assertTrue(os.path.isdir(dst_subdir))
        with open(os.path.join(dst_subdir, "a.txt"), "r") as f:
            self.assertEqual("file_a", f.read())
        with open(os.path.join(dst_subdir, "subdir", "b.txt"), "r") as f:
            self.assertEqual("file_b", f.read())

    def test_move_nonexistent_source(self):
        """Moving a nonexistent source should log error and not crash"""
        process = MoveProcess(
            source_path=self.src_dir,
            dest_path=self.dst_dir,
            file_name="does_not_exist"
        )
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

        process = MoveProcess(
            source_path=self.src_dir,
            dest_path=nested_dst,
            file_name="test.txt"
        )
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

        process = MoveProcess(
            source_path=self.src_dir,
            dest_path=self.dst_dir,
            file_name="big.txt"
        )
        self._run_process(process)

        dst_file = os.path.join(self.dst_dir, "big.txt")
        with open(dst_file, "r") as f:
            self.assertEqual(content, f.read())

    def test_move_empty_directory(self):
        """An empty directory should be moved successfully"""
        src_empty = os.path.join(self.src_dir, "emptydir")
        os.makedirs(src_empty)

        process = MoveProcess(
            source_path=self.src_dir,
            dest_path=self.dst_dir,
            file_name="emptydir"
        )
        self._run_process(process)

        self.assertFalse(os.path.exists(src_empty))
        self.assertTrue(os.path.isdir(os.path.join(self.dst_dir, "emptydir")))
