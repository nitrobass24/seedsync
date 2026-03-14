# Copyright 2017, Inderpreet Singh, All rights reserved.

import unittest
import sys
import copy
import logging
import os
import shutil
import tempfile
from argparse import Namespace
from unittest.mock import MagicMock, patch

from common import overrides, Config, ConfigSecretError, ENCRYPTED_PREFIX, KEY_FILE_NAME, PathPairsConfig
from seedsync import Seedsync


class TestSeedsync(unittest.TestCase):
    @overrides(unittest.TestCase)
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="test_seedsync")

    @overrides(unittest.TestCase)
    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def _make_args(self):
        return Namespace(
            config_dir=self.temp_dir,
            html="/path/to/html",
            scanfs="/path/to/scanfs",
            logdir=None,
            debug=False,
            exit=False,
        )

    def _build_seedsync(self):
        logger = logging.getLogger("test-seedsync-{}".format(id(self)))
        logger.handlers = []
        logger.addHandler(logging.NullHandler())
        logger.propagate = False

        with patch.object(Seedsync, "_parse_args", return_value=self._make_args()), \
                patch.object(Seedsync, "_create_logger", return_value=logger), \
                patch.object(Seedsync, "_load_path_pairs_config", return_value=PathPairsConfig()), \
                patch.object(Seedsync, "_load_persist", return_value=MagicMock()), \
                patch("signal.signal"):
            return Seedsync()

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
                self.assertIsNotNone(inner_config[key],
                                     msg="{}.{} is uninitialized".format(section, key))

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

    def test_startup_migrates_plaintext_sensitive_values_and_creates_key(self):
        config = Seedsync._create_default_config()
        config.lftp.remote_password = "plain-pass"
        config.web.api_key = "plain-key"

        settings_path = os.path.join(self.temp_dir, "settings.cfg")
        with open(settings_path, "w") as f:
            f.write(config.to_str())

        seedsync = self._build_seedsync()

        self.assertEqual("plain-pass", seedsync.context.config.lftp.remote_password)
        self.assertEqual("plain-key", seedsync.context.config.web.api_key)
        self.assertFalse(seedsync.context.config.needs_secret_migration)
        self.assertTrue(os.path.isfile(os.path.join(self.temp_dir, KEY_FILE_NAME)))

        with open(settings_path, "r") as f:
            content = f.read()
        self.assertIn("remote_password = {}".format(ENCRYPTED_PREFIX), content)
        self.assertIn("api_key = {}".format(ENCRYPTED_PREFIX), content)
        self.assertNotIn("plain-pass", content)
        self.assertNotIn("plain-key", content)

    def test_startup_loads_encrypted_config_with_matching_key(self):
        config = Seedsync._create_default_config()
        config.lftp.remote_password = "secret-pass"
        config.web.api_key = "secret-key"
        settings_path = os.path.join(self.temp_dir, "settings.cfg")
        config.to_file(settings_path)

        seedsync = self._build_seedsync()

        self.assertEqual("secret-pass", seedsync.context.config.lftp.remote_password)
        self.assertEqual("secret-key", seedsync.context.config.web.api_key)
        self.assertFalse(seedsync.context.config.needs_secret_migration)

    def test_startup_fails_fast_when_encryption_key_is_missing(self):
        config = Seedsync._create_default_config()
        config.lftp.remote_password = "secret-pass"
        config.web.api_key = "secret-key"
        settings_path = os.path.join(self.temp_dir, "settings.cfg")
        config.to_file(settings_path)
        os.remove(os.path.join(self.temp_dir, KEY_FILE_NAME))

        with open(settings_path, "r") as f:
            before = f.read()

        with self.assertRaises(ConfigSecretError):
            self._build_seedsync()

        with open(settings_path, "r") as f:
            after = f.read()
        self.assertEqual(before, after)

    def test_startup_fails_fast_when_encryption_key_is_invalid(self):
        config = Seedsync._create_default_config()
        config.lftp.remote_password = "secret-pass"
        settings_path = os.path.join(self.temp_dir, "settings.cfg")
        config.to_file(settings_path)

        with open(os.path.join(self.temp_dir, KEY_FILE_NAME), "wb") as f:
            f.write(b"invalid-key")

        with self.assertRaises(ConfigSecretError):
            self._build_seedsync()

    def test_startup_recovers_from_malformed_non_secret_config(self):
        settings_path = os.path.join(self.temp_dir, "settings.cfg")
        with open(settings_path, "w") as f:
            f.write("[Web\nport=88\n")

        seedsync = self._build_seedsync()

        self.assertTrue(os.path.isfile(settings_path))
        self.assertTrue(os.path.isfile(settings_path + ".1.bak"))
        self.assertTrue(os.path.isfile(os.path.join(self.temp_dir, KEY_FILE_NAME)))
        self.assertEqual(8800, seedsync.context.config.web.port)
