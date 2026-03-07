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
