# Copyright 2017, Inderpreet Singh, All rights reserved.

import json
import os
import tempfile
import unittest

from common import Config, IntegrationsConfig, PathPairsConfig
from seedsync import Seedsync


class TestSeedsync(unittest.TestCase):
    def test_args_config(self):
        argv = []
        argv.append("-c")
        argv.append("/path/to/config")
        argv.append("--html")
        argv.append("/path/to/html")
        argv.append("--scanfs")
        argv.append("/path/to/scanfs")
        args = Seedsync._parse_args(argv)
        self.assertIsNotNone(args)
        self.assertEqual("/path/to/config", args.config_dir)

        argv = []
        argv.append("--config_dir")
        argv.append("/path/to/config")
        argv.append("--html")
        argv.append("/path/to/html")
        argv.append("--scanfs")
        argv.append("/path/to/scanfs")
        args = Seedsync._parse_args(argv)
        self.assertIsNotNone(args)
        self.assertEqual("/path/to/config", args.config_dir)

        argv = []
        with self.assertRaises(SystemExit):
            Seedsync._parse_args(argv)

    def test_args_html(self):
        argv = []
        argv.append("-c")
        argv.append("/path/to/config")
        argv.append("--scanfs")
        argv.append("/path/to/scanfs")
        argv.append("--html")
        argv.append("/path/to/html")
        args = Seedsync._parse_args(argv)
        self.assertIsNotNone(args)
        self.assertEqual("/path/to/html", args.html)

    def test_args_scanfs(self):
        argv = []
        argv.append("-c")
        argv.append("/path/to/config")
        argv.append("--html")
        argv.append("/path/to/html")
        argv.append("--scanfs")
        argv.append("/path/to/scanfs")
        args = Seedsync._parse_args(argv)
        self.assertIsNotNone(args)
        self.assertEqual("/path/to/scanfs", args.scanfs)

    def test_args_logdir(self):
        argv = []
        argv.append("-c")
        argv.append("/path/to/config")
        argv.append("--logdir")
        argv.append("/path/to/logdir")
        argv.append("--html")
        argv.append("/path/to/html")
        argv.append("--scanfs")
        argv.append("/path/to/scanfs")
        args = Seedsync._parse_args(argv)
        self.assertIsNotNone(args)
        self.assertEqual("/path/to/logdir", args.logdir)

        argv = []
        argv.append("-c")
        argv.append("/path/to/config")
        argv.append("--html")
        argv.append("/path/to/html")
        argv.append("--scanfs")
        argv.append("/path/to/scanfs")
        args = Seedsync._parse_args(argv)
        self.assertIsNotNone(args)
        self.assertIsNone(args.logdir)

    def test_args_debug(self):
        argv = []
        argv.append("-c")
        argv.append("/path/to/config")
        argv.append("--html")
        argv.append("/path/to/html")
        argv.append("--scanfs")
        argv.append("/path/to/scanfs")
        argv.append("-d")
        args = Seedsync._parse_args(argv)
        self.assertIsNotNone(args)
        self.assertTrue(args.debug)

        argv = []
        argv.append("-c")
        argv.append("/path/to/config")
        argv.append("--debug")
        argv.append("--html")
        argv.append("/path/to/html")
        argv.append("--scanfs")
        argv.append("/path/to/scanfs")
        args = Seedsync._parse_args(argv)
        self.assertIsNotNone(args)
        self.assertTrue(args.debug)

        argv = []
        argv.append("-c")
        argv.append("/path/to/config")
        argv.append("--html")
        argv.append("/path/to/html")
        argv.append("--scanfs")
        argv.append("/path/to/scanfs")
        args = Seedsync._parse_args(argv)
        self.assertIsNotNone(args)
        self.assertFalse(args.debug)

    def test_default_config(self):
        config = Seedsync._create_default_config()
        # Test that default config doesn't have any uninitialized values
        config_dict = config.as_dict()
        for section, inner_config in config_dict.items():
            for key in inner_config:
                self.assertIsNotNone(inner_config[key], msg=f"{section}.{key} is uninitialized")

        # Test that default config is a valid config
        config_dict = config.as_dict()
        config2 = Config.from_dict(config_dict)
        config2_dict = config2.as_dict()
        self.assertEqual(config_dict, config2_dict)

    def test_default_config_round_trip_str(self):
        """Creating default config, converting to string, and parsing back should not raise"""
        config = Seedsync._create_default_config()
        config_str = config.to_str()
        config2 = Config.from_str(config_str)
        self.assertEqual(config.as_dict(), config2.as_dict())

    def test_detect_incomplete_config(self):
        # Test a complete config
        config = Seedsync._create_default_config()
        incomplete_value = config.lftp.remote_address
        config.lftp.remote_address = "value"
        config.lftp.remote_password = "value"
        config.lftp.remote_username = "value"
        config.lftp.remote_path = "value"
        config.lftp.local_path = "value"
        config.lftp.remote_path_to_scan_script = "value"
        self.assertFalse(Seedsync._detect_incomplete_config(config))

        # Test incomplete configs
        config.lftp.remote_address = incomplete_value
        self.assertTrue(Seedsync._detect_incomplete_config(config))
        config.lftp.remote_address = "value"

        config.lftp.remote_username = incomplete_value
        self.assertTrue(Seedsync._detect_incomplete_config(config))
        config.lftp.remote_username = "value"

        config.lftp.remote_path = incomplete_value
        self.assertTrue(Seedsync._detect_incomplete_config(config))
        config.lftp.remote_path = "value"

        config.lftp.local_path = incomplete_value
        self.assertTrue(Seedsync._detect_incomplete_config(config))
        config.lftp.local_path = "value"

        config.lftp.remote_path_to_scan_script = incomplete_value
        self.assertTrue(Seedsync._detect_incomplete_config(config))
        config.lftp.remote_path_to_scan_script = "value"


class TestLoadIntegrationsConfig(unittest.TestCase):
    """Migration of legacy [Integrations] settings to integrations.json."""

    def setUp(self):
        self._tmpdir_obj = tempfile.TemporaryDirectory()
        self.tmpdir = self._tmpdir_obj.name
        self.config_path = os.path.join(self.tmpdir, "settings.cfg")
        self.path_pairs_path = os.path.join(self.tmpdir, "path_pairs.json")
        self.integrations_path = os.path.join(self.tmpdir, "integrations.json")

    def tearDown(self):
        self._tmpdir_obj.cleanup()

    def _write_settings_with_integrations(self):
        with open(self.config_path, "w") as f:
            f.write(
                "[Integrations]\n"
                "sonarr_url = http://sonarr.local\n"
                "sonarr_api_key = sk-key\n"
                "sonarr_enabled = True\n"
                "radarr_url = \n"
                "radarr_api_key = \n"
                "radarr_enabled = False\n"
            )

    def _path_pairs_with_one(self) -> PathPairsConfig:
        from common import PathPair

        ppc = PathPairsConfig()
        ppc.add_pair(PathPair(name="TV", remote_path="/r", local_path="/l"))
        return ppc

    def test_migration_persists_path_pairs_before_integrations(self):
        """If a crash happens between integrations.json and path_pairs.json, we
        must have written path_pairs.json first so the next boot can re-run the
        migration cleanly. Otherwise we'd end up with instances that no pair
        references.
        """
        self._write_settings_with_integrations()
        ppc = self._path_pairs_with_one()
        ic = Seedsync._load_integrations_config(self.integrations_path, self.path_pairs_path, self.config_path, ppc)

        self.assertEqual(1, len(ic.instances))
        # path_pairs.json was written with the new instance attached
        with open(self.path_pairs_path) as f:
            persisted = json.load(f)
        attached = persisted["path_pairs"][0]["arr_target_ids"]
        self.assertEqual([ic.instances[0].id], attached)

    def test_existing_integrations_json_skips_migration(self):
        IntegrationsConfig().to_file(self.integrations_path)
        self._write_settings_with_integrations()
        ppc = self._path_pairs_with_one()
        ic = Seedsync._load_integrations_config(self.integrations_path, self.path_pairs_path, self.config_path, ppc)
        # Empty file already on disk → returned as-is, no migration
        self.assertEqual([], ic.instances)
        self.assertEqual([], ppc.pairs[0].arr_target_ids)

    def test_no_integrations_section_returns_empty_config(self):
        with open(self.config_path, "w") as f:
            f.write("[Lftp]\nremote_address = host\n")
        ppc = self._path_pairs_with_one()
        ic = Seedsync._load_integrations_config(self.integrations_path, self.path_pairs_path, self.config_path, ppc)
        self.assertEqual([], ic.instances)
        # path_pairs.json not rewritten when nothing to migrate
        self.assertFalse(os.path.exists(self.path_pairs_path))


class TestBackfillConfigDefaults(unittest.TestCase):
    """Tests for Seedsync._backfill_config_defaults()."""

    def test_none_fields_are_filled_with_defaults(self):
        """A config with None fields gets them filled with defaults and returns True."""
        config = Seedsync._create_default_config()
        # Simulate an upgrade: set some fields to None
        config.lftp.use_ssh_key = None
        config.controller.use_staging = None
        config.autoqueue.enabled = None

        changed = Seedsync._backfill_config_defaults(config)

        self.assertTrue(changed)
        # Verify that None fields were filled with default values
        defaults = Seedsync._create_default_config()
        self.assertEqual(defaults.lftp.use_ssh_key, config.lftp.use_ssh_key)
        self.assertEqual(defaults.controller.use_staging, config.controller.use_staging)
        self.assertEqual(defaults.autoqueue.enabled, config.autoqueue.enabled)

    def test_fully_populated_config_returns_false(self):
        """A fully populated config returns False and nothing changes."""
        config = Seedsync._create_default_config()
        original_dict = config.as_dict()

        changed = Seedsync._backfill_config_defaults(config)

        self.assertFalse(changed)
        self.assertEqual(original_dict, config.as_dict())


class TestLoadPathPairsConfig(unittest.TestCase):
    """Tests for Seedsync._load_path_pairs_config()."""

    def setUp(self):
        self._tmpdir_obj = tempfile.TemporaryDirectory()
        self.tmpdir = self._tmpdir_obj.name
        self.path_pairs_path = os.path.join(self.tmpdir, "path_pairs.json")

    def tearDown(self):
        self._tmpdir_obj.cleanup()

    def _make_config_with_paths(self, remote_path, local_path):
        config = Seedsync._create_default_config()
        config.lftp.remote_path = remote_path
        config.lftp.local_path = local_path
        return config

    def test_happy_path_migration(self):
        """path_pairs.json absent, valid remote_path/local_path -> returns config with one 'Default' pair."""
        config = self._make_config_with_paths("/remote/data", "/local/data")
        ppc = Seedsync._load_path_pairs_config(self.path_pairs_path, config)

        self.assertEqual(1, len(ppc.pairs))
        self.assertEqual("Default", ppc.pairs[0].name)
        self.assertEqual("/remote/data", ppc.pairs[0].remote_path)
        self.assertEqual("/local/data", ppc.pairs[0].local_path)
        # File should have been persisted
        self.assertTrue(os.path.isfile(self.path_pairs_path))

    def test_no_migration_with_dummy_values(self):
        """path_pairs.json absent, dummy sentinel values -> returns empty config."""
        config = self._make_config_with_paths("<replace me>", "<replace me>")
        ppc = Seedsync._load_path_pairs_config(self.path_pairs_path, config)

        self.assertEqual(0, len(ppc.pairs))
        # File should NOT have been persisted
        self.assertFalse(os.path.isfile(self.path_pairs_path))

    def test_clean_load_from_existing_file(self):
        """path_pairs.json exists and is valid -> loads from file."""
        from common import PathPair, PathPairsConfig

        ppc = PathPairsConfig()
        ppc.add_pair(PathPair(name="Movies", remote_path="/r/movies", local_path="/l/movies"))
        ppc.to_file(self.path_pairs_path)

        config = self._make_config_with_paths("/other/remote", "/other/local")
        loaded = Seedsync._load_path_pairs_config(self.path_pairs_path, config)

        self.assertEqual(1, len(loaded.pairs))
        self.assertEqual("Movies", loaded.pairs[0].name)

    def test_corrupt_file_backs_up_and_migrates(self):
        """path_pairs.json exists with bad content -> backs up and falls through to migration."""
        with open(self.path_pairs_path, "w") as f:
            f.write("NOT VALID JSON {{{")

        config = self._make_config_with_paths("/remote/data", "/local/data")
        ppc = Seedsync._load_path_pairs_config(self.path_pairs_path, config)

        # Should have fallen through to migration
        self.assertEqual(1, len(ppc.pairs))
        self.assertEqual("Default", ppc.pairs[0].name)
        # Backup file should exist
        backup_files = [f for f in os.listdir(self.tmpdir) if f.endswith(".bak")]
        self.assertTrue(len(backup_files) > 0, "Expected a backup file to be created")
