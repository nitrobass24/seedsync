# Copyright 2017, Inderpreet Singh, All rights reserved.

import logging
import os
import stat
import tempfile
import unittest
from unittest.mock import MagicMock

from system.file_modes import apply_umask_modes


def _mode(path: str) -> int:
    return stat.S_IMODE(os.lstat(path).st_mode)


class TestApplyUmaskModes(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = os.path.join(self.tmp.name, "Show.S01")
        os.makedirs(os.path.join(self.root, "Sample"))
        for p in ("ep1.mkv", "Sample/sample.mkv"):
            with open(os.path.join(self.root, p), "w"):
                pass
        # lftp's own create modes, which no umask can widen (#811)
        os.chmod(self.root, 0o775)
        os.chmod(os.path.join(self.root, "Sample"), 0o775)
        os.chmod(os.path.join(self.root, "ep1.mkv"), 0o664)
        os.chmod(os.path.join(self.root, "Sample/sample.mkv"), 0o664)
        self.logger = logging.getLogger("test")

    def test_umask_000_gives_world_writable_tree(self):
        apply_umask_modes(self.root, 0o000, self.logger)

        self.assertEqual(0o777, _mode(self.root))
        self.assertEqual(0o777, _mode(os.path.join(self.root, "Sample")))
        self.assertEqual(0o666, _mode(os.path.join(self.root, "ep1.mkv")))
        self.assertEqual(0o666, _mode(os.path.join(self.root, "Sample/sample.mkv")))

    def test_umask_022_tightens(self):
        apply_umask_modes(self.root, 0o022, self.logger)

        self.assertEqual(0o755, _mode(self.root))
        self.assertEqual(0o644, _mode(os.path.join(self.root, "ep1.mkv")))

    def test_single_file_download(self):
        single = os.path.join(self.tmp.name, "single.mkv")
        with open(single, "w"):
            pass
        os.chmod(single, 0o664)

        apply_umask_modes(single, 0o000, self.logger)

        self.assertEqual(0o666, _mode(single))

    def test_symlinks_are_left_alone(self):
        target = os.path.join(self.tmp.name, "outside")
        os.makedirs(target)
        os.chmod(target, 0o700)
        os.symlink(target, os.path.join(self.root, "link"))

        apply_umask_modes(self.root, 0o000, self.logger)

        self.assertEqual(0o700, _mode(target))

    def test_missing_path_is_a_noop(self):
        logger = MagicMock()
        apply_umask_modes(os.path.join(self.tmp.name, "gone"), 0o000, logger)
        logger.warning.assert_not_called()

    def test_restrictive_umask_still_reaches_descendants(self):
        """0177 strips search permission from directories; the walk must visit
        the contents before locking the parent. Assert outside-in, re-opening
        each directory before looking inside it."""
        apply_umask_modes(self.root, 0o177, self.logger)

        self.assertEqual(0o600, _mode(self.root))
        os.chmod(self.root, 0o700)
        self.assertEqual(0o600, _mode(os.path.join(self.root, "ep1.mkv")))
        self.assertEqual(0o600, _mode(os.path.join(self.root, "Sample")))
        os.chmod(os.path.join(self.root, "Sample"), 0o700)
        self.assertEqual(0o600, _mode(os.path.join(self.root, "Sample/sample.mkv")))

    def test_directory_setgid_is_preserved(self):
        os.chmod(self.root, 0o2775)

        apply_umask_modes(self.root, 0o000, self.logger)

        self.assertEqual(0o2777, _mode(self.root))

    def test_apply_to_entries_only_touches_listed_paths(self):
        from system.file_modes import apply_umask_modes_to, relative_entries

        untouched = os.path.join(self.root, "preexisting.txt")
        with open(untouched, "w"):
            pass
        os.chmod(untouched, 0o600)
        entries = [e for e in relative_entries(self.root) if e[0] != "preexisting.txt"]

        apply_umask_modes_to(self.root, entries, 0o000, self.logger)

        self.assertEqual(0o600, _mode(untouched))
        self.assertEqual(0o666, _mode(os.path.join(self.root, "ep1.mkv")))
        self.assertEqual(0o777, _mode(os.path.join(self.root, "Sample")))
        self.assertEqual(0o777, _mode(self.root))
