# Copyright 2017, Inderpreet Singh, All rights reserved.

import os
import shutil
import stat
import tempfile
import unittest

from common import ConfigSecretError, ConfigSecretStore, ENCRYPTED_PREFIX, KEY_FILE_NAME


class TestConfigSecretStore(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="test_config_secrets")
        self.settings_path = os.path.join(self.temp_dir, "settings.cfg")
        self.key_path = os.path.join(self.temp_dir, KEY_FILE_NAME)

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_creates_key_file_with_restricted_permissions(self):
        ConfigSecretStore.for_config_file(self.settings_path, create_if_missing=True)

        self.assertTrue(os.path.isfile(self.key_path))
        self.assertEqual(0o600, stat.S_IMODE(os.stat(self.key_path).st_mode))

    def test_encrypt_and_decrypt_round_trip(self):
        store = ConfigSecretStore.for_config_file(self.settings_path, create_if_missing=True)

        encrypted = store.encrypt("super-secret")
        decrypted, was_encrypted, needs_migration = store.decrypt_if_needed(encrypted)

        self.assertTrue(encrypted.startswith(ENCRYPTED_PREFIX))
        self.assertEqual("super-secret", decrypted)
        self.assertTrue(was_encrypted)
        self.assertFalse(needs_migration)

    def test_plaintext_value_is_marked_for_migration(self):
        store = ConfigSecretStore.for_config_file(self.settings_path, create_if_missing=True)

        value, was_encrypted, needs_migration = store.decrypt_if_needed("legacy-plaintext")

        self.assertEqual("legacy-plaintext", value)
        self.assertFalse(was_encrypted)
        self.assertTrue(needs_migration)

    def test_empty_value_passthrough(self):
        store = ConfigSecretStore.for_config_file(self.settings_path, create_if_missing=True)

        value, was_encrypted, needs_migration = store.decrypt_if_needed("")

        self.assertEqual("", value)
        self.assertFalse(was_encrypted)
        self.assertFalse(needs_migration)

    def test_missing_key_file_raises(self):
        with self.assertRaises(ConfigSecretError):
            ConfigSecretStore.for_config_file(self.settings_path)

    def test_invalid_key_file_raises(self):
        with open(self.key_path, "wb") as f:
            f.write(b"not-a-valid-key")

        with self.assertRaises(ConfigSecretError):
            ConfigSecretStore.for_config_file(self.settings_path)

    def test_existing_key_file_permissions_are_corrected(self):
        ConfigSecretStore.for_config_file(self.settings_path, create_if_missing=True)
        os.chmod(self.key_path, 0o644)

        ConfigSecretStore.for_config_file(self.settings_path)

        self.assertEqual(0o600, stat.S_IMODE(os.stat(self.key_path).st_mode))
