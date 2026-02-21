# Copyright 2017, Inderpreet Singh, All rights reserved.

import unittest

from common import escape_remote_path_single, escape_remote_path_double


class TestEscapeRemotePathSingle(unittest.TestCase):
    def test_wraps_path_in_single_quotes(self):
        self.assertEqual("'/some/path'", escape_remote_path_single("/some/path"))

    def test_does_not_expand_tilde(self):
        self.assertEqual("'~/data/torrents'", escape_remote_path_single("~/data/torrents"))

    def test_handles_path_with_spaces(self):
        self.assertEqual("'/some/path with spaces'", escape_remote_path_single("/some/path with spaces"))

    def test_handles_empty_path(self):
        self.assertEqual("''", escape_remote_path_single(""))

    def test_handles_single_quote_in_path(self):
        self.assertEqual("'/some/Don'\\''t Look Now'",
                         escape_remote_path_single("/some/Don't Look Now"))


class TestEscapeRemotePathDouble(unittest.TestCase):
    def test_wraps_path_in_double_quotes(self):
        self.assertEqual('"/some/path"', escape_remote_path_double("/some/path"))

    def test_converts_tilde_to_home(self):
        self.assertEqual('"$HOME/data/torrents"', escape_remote_path_double("~/data/torrents"))

    def test_only_converts_leading_tilde(self):
        self.assertEqual('"/some/path/~file"', escape_remote_path_double("/some/path/~file"))

    def test_handles_tilde_only(self):
        self.assertEqual('"$HOME"', escape_remote_path_double("~"))

    def test_handles_path_with_spaces(self):
        self.assertEqual('"/some/path with spaces"', escape_remote_path_double("/some/path with spaces"))

    def test_handles_empty_path(self):
        self.assertEqual('""', escape_remote_path_double(""))
