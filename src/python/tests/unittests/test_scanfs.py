# Copyright 2017, Inderpreet Singh, All rights reserved.
#
# Tests for the standalone Python fallback scanner (scanfs.py).
#
# Two concerns are covered:
#
#   1. Pickle round-trip compatibility — scanfs.SystemFile instances must
#      survive pickling at protocol 2 and unpickling via the *real*
#      system.file.SystemFile class.  If the two classes ever diverge (an
#      attribute is added/renamed/removed in one but not the other) these
#      tests will fail before the regression reaches production.
#
#   2. Scanning logic — _scan_path must produce correctly structured,
#      sorted SystemFile trees for representative directory layouts.

import os
import pickle
import shutil
import sys
import tempfile
import unittest

# Import the real SystemFile BEFORE importing scanfs so that
# sys.modules["system.file"] is already set to the genuine module when scanfs
# runs its sys.modules.setdefault() calls (which then become no-ops).
from system.file import SystemFile as RealSystemFile

import scanfs  # noqa: E402  (imported after the real class intentionally)


# ---------------------------------------------------------------------------
# Helper: simulate the remote-side pickle environment
# ---------------------------------------------------------------------------

def _pickle_scanfs(obj):
    """
    Pickle *obj* (a scanfs.SystemFile instance) the way the remote server
    would — with sys.modules["system.file"].SystemFile pointing to
    scanfs.SystemFile so that pickle's same-object check passes.

    On the local side the real system.file.SystemFile is in sys.modules,
    so pickle.loads() will correctly reconstruct RealSystemFile instances.
    """
    sm = sys.modules.get("system.file")
    saved = getattr(sm, "SystemFile", None) if sm else None
    try:
        if sm is not None:
            sm.SystemFile = type(obj) if not isinstance(obj, list) else scanfs.SystemFile
        return pickle.dumps(obj, protocol=2)
    finally:
        if sm is not None and saved is not None:
            sm.SystemFile = saved


def _pickle_scanfs_list(lst):
    """Pickle a list of scanfs.SystemFile objects as the remote would."""
    sm = sys.modules.get("system.file")
    saved = getattr(sm, "SystemFile", None) if sm else None
    try:
        if sm is not None:
            sm.SystemFile = scanfs.SystemFile
        return pickle.dumps(lst, protocol=2)
    finally:
        if sm is not None and saved is not None:
            sm.SystemFile = saved


# ---------------------------------------------------------------------------
# Helpers shared by both test classes
# ---------------------------------------------------------------------------

def _touch(directory, *parts, size=0):
    """Create a file of *size* zero-bytes inside *directory*."""
    path = os.path.join(directory, *parts)
    with open(path, "wb") as f:
        f.write(b"\x00" * size)
    return path


def _mkdir(directory, *parts):
    """Create a subdirectory tree inside *directory*."""
    path = os.path.join(directory, *parts)
    os.makedirs(path, exist_ok=True)
    return path


# ---------------------------------------------------------------------------
# 1. Pickle round-trip tests
# ---------------------------------------------------------------------------

class TestScanfsPickleRoundTrip(unittest.TestCase):
    """
    Verify that scanfs.SystemFile instances are pickle-compatible with the
    real system.file.SystemFile class.

    The key property pickle requires is that the __dict__ keys of instances
    of both classes are identical (Python name-mangling uses only the class
    name, not the module, so the mangled keys are the same as long as the
    attribute names and class name stay the same).

    These tests act as an early-warning system: any attribute added, renamed,
    or removed in system/file.py::SystemFile without an equivalent change in
    scanfs.py::SystemFile will cause these tests to fail before the regression
    reaches production.  See the IMPORTANT comment in both source files.
    """

    # -- __dict__ key equivalence (primary drift detector) -------------------

    def test_file_dict_keys_match_real_system_file(self):
        """Instance __dict__ keys must be identical for pickle compatibility."""
        fallback = scanfs.SystemFile("check.txt", 1)
        real = RealSystemFile("check.txt", 1)
        self.assertEqual(set(vars(fallback).keys()), set(vars(real).keys()),
                         "scanfs.SystemFile and system.file.SystemFile have different "
                         "__dict__ keys — update one to match the other")

    def test_directory_dict_keys_match_real_system_file(self):
        fallback = scanfs.SystemFile("mydir", 0, is_dir=True)
        real = RealSystemFile("mydir", 0, is_dir=True)
        self.assertEqual(set(vars(fallback).keys()), set(vars(real).keys()))

    # -- Full pickle round-trips ---------------------------------------------

    def test_file_round_trip(self):
        fallback = scanfs.SystemFile("report.pdf", 2048)
        data = _pickle_scanfs(fallback)
        real = pickle.loads(data)

        self.assertIsInstance(real, RealSystemFile)
        self.assertEqual("report.pdf", real.name)
        self.assertEqual(2048, real.size)
        self.assertFalse(real.is_dir)
        self.assertEqual([], real.children)

    def test_directory_with_children_round_trip(self):
        parent = scanfs.SystemFile("season1", 0, is_dir=True)
        parent.add_child(scanfs.SystemFile("ep01.mkv", 1_000_000))
        parent.add_child(scanfs.SystemFile("ep02.mkv", 1_100_000))
        data = _pickle_scanfs(parent)
        real = pickle.loads(data)

        self.assertIsInstance(real, RealSystemFile)
        self.assertTrue(real.is_dir)
        self.assertEqual(2, len(real.children))
        for child in real.children:
            self.assertIsInstance(child, RealSystemFile)
        self.assertEqual("ep01.mkv", real.children[0].name)
        self.assertEqual("ep02.mkv", real.children[1].name)

    def test_list_of_files_round_trip(self):
        files = [
            scanfs.SystemFile("a.txt", 10),
            scanfs.SystemFile("b.txt", 20),
        ]
        data = _pickle_scanfs_list(files)
        real_files = pickle.loads(data)

        self.assertEqual(2, len(real_files))
        for obj in real_files:
            self.assertIsInstance(obj, RealSystemFile)

    def test_zero_size_file_round_trip(self):
        fallback = scanfs.SystemFile("empty.txt", 0)
        real = pickle.loads(_pickle_scanfs(fallback))
        self.assertEqual(0, real.size)

    def test_timestamps_survive_round_trip(self):
        from datetime import datetime
        created = datetime(2024, 1, 15, 10, 30, 0)
        modified = datetime(2024, 6, 1, 8, 0, 0)
        fallback = scanfs.SystemFile("dated.txt", 512,
                                     time_created=created,
                                     time_modified=modified)
        real = pickle.loads(_pickle_scanfs(fallback))
        self.assertEqual(created, real.timestamp_created)
        self.assertEqual(modified, real.timestamp_modified)


# ---------------------------------------------------------------------------
# 2. _scan_path integration tests
# ---------------------------------------------------------------------------

class TestScanfsIntegration(unittest.TestCase):
    """
    Run _scan_path against real temporary directories and verify the
    resulting SystemFile trees are correct and pickle correctly.
    """

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="test_scanfs_")

    def tearDown(self):
        shutil.rmtree(self.tmp)

    # -- Basic structure -----------------------------------------------------

    def test_empty_directory_returns_empty_list(self):
        files = scanfs._scan_path(self.tmp)
        self.assertEqual([], files)

    def test_single_file(self):
        _touch(self.tmp, "hello.txt", size=42)
        files = scanfs._scan_path(self.tmp)

        self.assertEqual(1, len(files))
        self.assertEqual("hello.txt", files[0].name)
        self.assertEqual(42, files[0].size)
        self.assertFalse(files[0].is_dir)

    def test_multiple_files_are_sorted(self):
        for name in ("charlie.txt", "alpha.txt", "bravo.txt"):
            _touch(self.tmp, name, size=1)
        files = scanfs._scan_path(self.tmp)

        names = [f.name for f in files]
        self.assertEqual(["alpha.txt", "bravo.txt", "charlie.txt"], names)

    def test_nested_directory(self):
        _mkdir(self.tmp, "subdir")
        _touch(self.tmp, "subdir", "file.bin", size=100)
        files = scanfs._scan_path(self.tmp)

        self.assertEqual(1, len(files))
        d = files[0]
        self.assertTrue(d.is_dir)
        self.assertEqual("subdir", d.name)
        self.assertEqual(100, d.size)
        self.assertEqual(1, len(d.children))
        self.assertEqual("file.bin", d.children[0].name)
        self.assertEqual(100, d.children[0].size)

    def test_directory_size_is_sum_of_children(self):
        _mkdir(self.tmp, "pkg")
        _touch(self.tmp, "pkg", "a.dat", size=300)
        _touch(self.tmp, "pkg", "b.dat", size=700)
        files = scanfs._scan_path(self.tmp)

        self.assertEqual(1000, files[0].size)

    # -- lftp status file handling -------------------------------------------

    def test_lftp_status_files_excluded_from_output(self):
        _touch(self.tmp, "movie.mkv", size=500)
        _touch(self.tmp, "movie.mkv.lftp-pget-status", size=20)
        files = scanfs._scan_path(self.tmp)

        names = [f.name for f in files]
        self.assertIn("movie.mkv", names)
        self.assertNotIn("movie.mkv.lftp-pget-status", names)

    # -- Symlink cycle guard -------------------------------------------------

    def test_symlink_cycle_does_not_recurse_infinitely(self):
        """A symlink that points back to an ancestor must not cause unbounded recursion."""
        _mkdir(self.tmp, "a")
        os.symlink(self.tmp, os.path.join(self.tmp, "a", "cycle"))
        # Must return without raising RecursionError
        files = scanfs._scan_path(self.tmp)
        self.assertIsNotNone(files)

    # -- Pickle output -------------------------------------------------------

    def test_scan_output_unpickles_as_real_system_file(self):
        _touch(self.tmp, "sample.dat", size=7)
        files = scanfs._scan_path(self.tmp)
        data = _pickle_scanfs_list(files)
        real_files = pickle.loads(data)

        self.assertEqual(1, len(real_files))
        self.assertIsInstance(real_files[0], RealSystemFile)
        self.assertEqual("sample.dat", real_files[0].name)
        self.assertEqual(7, real_files[0].size)

    def test_nested_scan_output_unpickles_fully(self):
        _mkdir(self.tmp, "show")
        _touch(self.tmp, "show", "ep1.mkv", size=500)
        files = scanfs._scan_path(self.tmp)
        data = _pickle_scanfs_list(files)
        real_files = pickle.loads(data)

        self.assertIsInstance(real_files[0], RealSystemFile)
        self.assertTrue(real_files[0].is_dir)
        child = real_files[0].children[0]
        self.assertIsInstance(child, RealSystemFile)
        self.assertEqual("ep1.mkv", child.name)


if __name__ == "__main__":
    unittest.main()
