# Copyright 2017, Inderpreet Singh, All rights reserved.

import json
import unittest

from common import PersistError
from controller import ControllerPersist


class TestControllerPersist(unittest.TestCase):
    def test_from_str(self):
        content = """
        {
            "downloaded": ["one", "two", "th ree", "fo.ur"],
            "extracted": ["fi\\"ve", "si@x", "se\\\\ven", "ei-ght"]
        }
        """
        persist = ControllerPersist.from_str(content)
        golden_downloaded = {"one", "two", "th ree", "fo.ur"}
        golden_extracted = {'fi"ve', "si@x", "se\\ven", "ei-ght"}
        self.assertEqual(golden_downloaded, persist.downloaded_file_names)
        self.assertEqual(golden_extracted, persist.extracted_file_names)

    def test_to_str(self):
        persist = ControllerPersist()
        persist.downloaded_file_names.add("one")
        persist.downloaded_file_names.add("two")
        persist.downloaded_file_names.add("th ree")
        persist.downloaded_file_names.add("fo.ur")
        persist.extracted_file_names.add('fi"ve')
        persist.extracted_file_names.add("si@x")
        persist.extracted_file_names.add("se\\ven")
        persist.extracted_file_names.add("ei-ght")
        dct = json.loads(persist.to_str())
        self.assertTrue("downloaded" in dct)
        self.assertEqual({"one", "two", "th ree", "fo.ur"}, set(dct["downloaded"]))
        self.assertTrue("extracted" in dct)
        self.assertEqual({'fi"ve', "si@x", "se\\ven", "ei-ght"}, set(dct["extracted"]))

    def test_to_and_from_str(self):
        persist = ControllerPersist()
        persist.downloaded_file_names.add("one")
        persist.downloaded_file_names.add("two")
        persist.downloaded_file_names.add("th ree")
        persist.downloaded_file_names.add("fo.ur")
        persist.extracted_file_names.add('fi"ve')
        persist.extracted_file_names.add("si@x")
        persist.extracted_file_names.add("se\\ven")
        persist.extracted_file_names.add("ei-ght")

        persist_actual = ControllerPersist.from_str(persist.to_str())
        self.assertEqual(persist.downloaded_file_names, persist_actual.downloaded_file_names)
        self.assertEqual(persist.extracted_file_names, persist_actual.extracted_file_names)

    def test_persist_read_error(self):
        # bad pattern
        content = """
        {
            "downloaded": [bad string],
            "extracted": []
        }
        """
        with self.assertRaises(PersistError):
            ControllerPersist.from_str(content)
        content = """
        {
            "downloaded": [],
            "extracted": [bad string]
        }
        """
        with self.assertRaises(PersistError):
            ControllerPersist.from_str(content)

        # empty json
        content = ""
        with self.assertRaises(PersistError):
            ControllerPersist.from_str(content)

        # missing keys
        content = """
        {
            "downloaded": []
        }
        """
        with self.assertRaises(PersistError):
            ControllerPersist.from_str(content)
        content = """
        {
            "extracted": []
        }
        """
        with self.assertRaises(PersistError):
            ControllerPersist.from_str(content)

        # malformed
        content = "{"
        with self.assertRaises(PersistError):
            ControllerPersist.from_str(content)

    def test_legacy_colon_keys_migrated_to_unit_separator(self):
        """Keys using the old 'uuid:name' format should be migrated to 'uuid\\x1fname'."""
        uuid1 = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
        content = json.dumps(
            {
                "downloaded": [f"{uuid1}:movie.mkv", "plain_file.txt"],
                "extracted": [f"{uuid1}:archive.rar"],
                "extract_failed": [f"{uuid1}:bad.zip"],
            }
        )
        persist = ControllerPersist.from_str(content)

        sep = "\x1f"
        self.assertEqual(
            {f"{uuid1}{sep}movie.mkv", "plain_file.txt"},
            persist.downloaded_file_names,
        )
        self.assertEqual(
            {f"{uuid1}{sep}archive.rar"},
            persist.extracted_file_names,
        )
        self.assertEqual(
            {f"{uuid1}{sep}bad.zip"},
            persist.extract_failed_file_names,
        )

    def test_legacy_colon_in_filename_greedy_match(self):
        """Greedy regex: 'uuid:movie:part1.mkv' becomes 'uuid\\x1fmovie:part1.mkv'."""
        uuid1 = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
        content = json.dumps(
            {
                "downloaded": [f"{uuid1}:movie:part1.mkv"],
                "extracted": [],
            }
        )
        persist = ControllerPersist.from_str(content)

        sep = "\x1f"
        self.assertEqual(
            {f"{uuid1}{sep}movie:part1.mkv"},
            persist.downloaded_file_names,
        )

    def test_plain_filename_with_colon_not_migrated(self):
        """A filename like 'movie:part1.mkv' without a UUID prefix should NOT be migrated."""
        content = json.dumps(
            {
                "downloaded": ["movie:part1.mkv"],
                "extracted": [],
            }
        )
        persist = ControllerPersist.from_str(content)
        self.assertEqual(
            {"movie:part1.mkv"},
            persist.downloaded_file_names,
        )

    def test_new_unit_separator_keys_unchanged(self):
        """Keys already using \\x1f should not be modified."""
        uuid1 = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
        sep = "\x1f"
        content = json.dumps(
            {
                "downloaded": [f"{uuid1}{sep}movie.mkv"],
                "extracted": [],
            }
        )
        persist = ControllerPersist.from_str(content)
        self.assertEqual(
            {f"{uuid1}{sep}movie.mkv"},
            persist.downloaded_file_names,
        )

    def test_validated_and_corrupt_round_trip(self):
        """Validated and corrupt keys should survive serialization round-trip."""
        persist = ControllerPersist()
        persist.downloaded_file_names.add("a")
        persist.extracted_file_names.add("b")
        persist.validated_file_names.add("c")
        persist.corrupt_file_names.add("d")

        persist_actual = ControllerPersist.from_str(persist.to_str())
        self.assertEqual({"a"}, persist_actual.downloaded_file_names)
        self.assertEqual({"b"}, persist_actual.extracted_file_names)
        self.assertEqual({"c"}, persist_actual.validated_file_names)
        self.assertEqual({"d"}, persist_actual.corrupt_file_names)

    def test_validated_and_corrupt_missing_keys_default_empty(self):
        """Old persist files without validated/corrupt keys should load with empty sets."""
        content = json.dumps(
            {
                "downloaded": ["a"],
                "extracted": ["b"],
            }
        )
        persist = ControllerPersist.from_str(content)
        self.assertEqual(set(), persist.validated_file_names)
        self.assertEqual(set(), persist.corrupt_file_names)

    def test_validated_corrupt_legacy_keys_migrated(self):
        """Legacy colon-separated keys in validated/corrupt should be migrated."""
        uuid1 = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
        content = json.dumps(
            {
                "downloaded": [],
                "extracted": [],
                "validated": [f"{uuid1}:movie.mkv"],
                "corrupt": [f"{uuid1}:bad.mkv"],
            }
        )
        persist = ControllerPersist.from_str(content)
        sep = "\x1f"
        self.assertEqual(
            {f"{uuid1}{sep}movie.mkv"},
            persist.validated_file_names,
        )
        self.assertEqual(
            {f"{uuid1}{sep}bad.mkv"},
            persist.corrupt_file_names,
        )
