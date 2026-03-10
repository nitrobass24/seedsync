# Copyright 2017, Inderpreet Singh, All rights reserved.

import unittest

from system import SystemFile
from controller import filter_excluded_files


class TestFilterExcludedFiles(unittest.TestCase):
    def test_empty_pattern_returns_all(self):
        files = [SystemFile("a.txt", 10, False), SystemFile("b.nfo", 20, False)]
        result = filter_excluded_files(files, "")
        self.assertEqual(["a.txt", "b.nfo"], [f.name for f in result])

    def test_none_pattern_returns_all(self):
        files = [SystemFile("a.txt", 10, False)]
        result = filter_excluded_files(files, None)
        self.assertEqual(["a.txt"], [f.name for f in result])

    def test_single_pattern(self):
        files = [
            SystemFile("movie.mkv", 100, False),
            SystemFile("info.nfo", 10, False),
            SystemFile("readme.txt", 5, False),
        ]
        result = filter_excluded_files(files, "*.nfo")
        self.assertEqual(["movie.mkv", "readme.txt"], [f.name for f in result])

    def test_multiple_patterns(self):
        files = [
            SystemFile("movie.mkv", 100, False),
            SystemFile("info.nfo", 10, False),
            SystemFile("readme.txt", 5, False),
            SystemFile("sub.srt", 15, False),
        ]
        result = filter_excluded_files(files, "*.nfo,*.txt")
        self.assertEqual(["movie.mkv", "sub.srt"], [f.name for f in result])

    def test_dotfile_pattern(self):
        files = [
            SystemFile(".hidden", 10, False),
            SystemFile("visible", 20, False),
            SystemFile(".config", 5, False),
        ]
        result = filter_excluded_files(files, ".*")
        self.assertEqual(["visible"], [f.name for f in result])

    def test_case_insensitive(self):
        files = [
            SystemFile("INFO.NFO", 10, False),
            SystemFile("movie.mkv", 100, False),
        ]
        result = filter_excluded_files(files, "*.nfo")
        self.assertEqual(["movie.mkv"], [f.name for f in result])

    def test_whitespace_in_patterns(self):
        files = [
            SystemFile("info.nfo", 10, False),
            SystemFile("readme.txt", 5, False),
            SystemFile("movie.mkv", 100, False),
        ]
        result = filter_excluded_files(files, " *.nfo , *.txt ")
        self.assertEqual(["movie.mkv"], [f.name for f in result])

    def test_directories_can_be_excluded(self):
        files = [
            SystemFile("Sample", 50, True),
            SystemFile("movie.mkv", 100, False),
        ]
        result = filter_excluded_files(files, "Sample")
        self.assertEqual(["movie.mkv"], [f.name for f in result])

    def test_wildcard_pattern(self):
        files = [
            SystemFile("sample_video", 50, True),
            SystemFile("movie.mkv", 100, False),
        ]
        result = filter_excluded_files(files, "sample*")
        self.assertEqual(["movie.mkv"], [f.name for f in result])

    def test_no_files_returns_empty(self):
        result = filter_excluded_files([], "*.nfo")
        self.assertEqual([], result)

    def test_whitespace_only_pattern_returns_all(self):
        files = [SystemFile("a.txt", 10, False)]
        result = filter_excluded_files(files, "  ,  , ")
        self.assertEqual(["a.txt"], [f.name for f in result])


class TestFilterExcludedFilesRecursive(unittest.TestCase):
    """Tests for recursive filtering of SystemFile children."""

    @staticmethod
    def _make_dir(name, children=None):
        d = SystemFile(name, 0, True)
        for c in (children or []):
            d.add_child(c)
        return d

    def test_child_file_excluded(self):
        """A file nested inside a directory should be removed when it matches."""
        d = self._make_dir("shows", [
            SystemFile("episode.mkv", 100, False),
            SystemFile("info.nfo", 10, False),
        ])
        result = filter_excluded_files([d], "*.nfo")
        self.assertEqual(1, len(result))
        self.assertEqual(["episode.mkv"], [c.name for c in result[0].children])

    def test_child_dir_excluded_removes_subtree(self):
        """A directory child that matches should be removed entirely."""
        sample_dir = self._make_dir("Sample", [
            SystemFile("sample.mkv", 50, False),
        ])
        d = self._make_dir("movie", [
            SystemFile("movie.mkv", 100, False),
            sample_dir,
        ])
        result = filter_excluded_files([d], "Sample")
        self.assertEqual(1, len(result))
        self.assertEqual(["movie.mkv"], [c.name for c in result[0].children])

    def test_deeply_nested_filtering(self):
        """Exclude patterns should apply at arbitrary depth."""
        inner = self._make_dir("season1", [
            SystemFile("ep1.mkv", 100, False),
            SystemFile("ep1.nfo", 5, False),
        ])
        outer = self._make_dir("show", [inner])
        result = filter_excluded_files([outer], "*.nfo")
        self.assertEqual(1, len(result))
        season = result[0].children[0]
        self.assertEqual("season1", season.name)
        self.assertEqual(["ep1.mkv"], [c.name for c in season.children])

    def test_top_level_dir_match_removes_entire_subtree(self):
        """When a top-level directory matches, the whole tree is gone."""
        d = self._make_dir("Sample", [
            SystemFile("a.mkv", 100, False),
        ])
        result = filter_excluded_files([d, SystemFile("keep.txt", 10, False)], "Sample")
        self.assertEqual(["keep.txt"], [f.name for f in result])

    def test_non_matching_dir_children_preserved(self):
        """Non-matching children should remain untouched."""
        d = self._make_dir("movies", [
            SystemFile("a.mkv", 100, False),
            SystemFile("b.mkv", 200, False),
        ])
        result = filter_excluded_files([d], "*.nfo")
        self.assertEqual(["a.mkv", "b.mkv"], [c.name for c in result[0].children])

    def test_empty_children_dir_unchanged(self):
        """A directory with no children should pass through unmodified."""
        d = self._make_dir("emptydir")
        result = filter_excluded_files([d], "*.nfo")
        self.assertEqual(1, len(result))
        self.assertEqual("emptydir", result[0].name)
        self.assertEqual([], result[0].children)

    def test_recursive_does_not_mutate_original(self):
        """Filtering should not modify the original SystemFile tree."""
        inner_file = SystemFile("info.nfo", 5, False)
        d = self._make_dir("show", [
            SystemFile("ep.mkv", 100, False),
            inner_file,
        ])
        original_child_count = len(d.children)
        filter_excluded_files([d], "*.nfo")
        self.assertEqual(original_child_count, len(d.children))

    def test_multiple_patterns_recursive(self):
        """Multiple comma-separated patterns should all apply recursively."""
        d = self._make_dir("show", [
            SystemFile("ep.mkv", 100, False),
            SystemFile("info.nfo", 5, False),
            SystemFile("readme.txt", 3, False),
            self._make_dir("Sample", [
                SystemFile("sample.mkv", 50, False),
            ]),
        ])
        result = filter_excluded_files([d], "*.nfo, *.txt, Sample")
        self.assertEqual(1, len(result))
        self.assertEqual(["ep.mkv"], [c.name for c in result[0].children])
