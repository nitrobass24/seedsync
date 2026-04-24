# Copyright 2017, Inderpreet Singh, All rights reserved.

import unittest

from controller.persist_keys import KEY_SEP, persist_key, strip_persist_key


class TestPersistKey(unittest.TestCase):
    def test_key_sep_is_unit_separator(self):
        self.assertEqual("\x1f", KEY_SEP)

    def test_persist_key_no_pair_id(self):
        result = persist_key(None, "file.txt")
        self.assertEqual("file.txt", result)

    def test_persist_key_with_pair_id(self):
        result = persist_key("abc-123", "file.txt")
        self.assertEqual("abc-123\x1ffile.txt", result)

    def test_strip_persist_key_no_pair_id(self):
        result = strip_persist_key("file.txt", None)
        self.assertEqual("file.txt", result)

    def test_strip_persist_key_current_separator(self):
        result = strip_persist_key("abc-123\x1ffile.txt", "abc-123")
        self.assertEqual("file.txt", result)

    def test_strip_persist_key_legacy_colon_separator(self):
        result = strip_persist_key("abc-123:file.txt", "abc-123")
        self.assertEqual("file.txt", result)

    def test_strip_persist_key_wrong_pair_id_returns_key_unchanged(self):
        result = strip_persist_key("abc-123\x1ffile.txt", "other-id")
        self.assertEqual("abc-123\x1ffile.txt", result)

    def test_strip_persist_key_no_prefix_match_returns_key_unchanged(self):
        result = strip_persist_key("no-prefix-file.txt", "abc-123")
        self.assertEqual("no-prefix-file.txt", result)
