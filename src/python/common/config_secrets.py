# Copyright 2017, Inderpreet Singh, All rights reserved.

import os
import tempfile
from typing import Tuple

from cryptography.fernet import Fernet, InvalidToken

from .error import AppError

KEY_FILE_NAME = ".encryption_key"
ENCRYPTED_PREFIX = "enc:"


class ConfigSecretError(AppError):
    """Raised when the config encryption key cannot be loaded or used."""
    pass


class ConfigSecretStore:
    def __init__(self, key_file_path: str, fernet: Fernet):
        self.key_file_path = key_file_path
        self._fernet = fernet

    @classmethod
    def for_config_file(cls, settings_path: str, create_if_missing: bool = False) -> "ConfigSecretStore":
        config_dir = os.path.dirname(settings_path) or "."
        key_file_path = os.path.join(config_dir, KEY_FILE_NAME)

        if os.path.isfile(key_file_path):
            key = cls._read_key_file(key_file_path)
        elif create_if_missing:
            key = cls._create_key_file(key_file_path)
        else:
            raise ConfigSecretError(
                "Missing encryption key file '{}' for encrypted config values".format(key_file_path)
            )

        cls._restrict_permissions(key_file_path)
        try:
            fernet = Fernet(key)
        except (TypeError, ValueError) as e:
            raise ConfigSecretError("Invalid encryption key file '{}': {}".format(key_file_path, str(e)))
        return cls(key_file_path=key_file_path, fernet=fernet)

    @staticmethod
    def _read_key_file(key_file_path: str) -> bytes:
        try:
            with open(key_file_path, "rb") as f:
                key = f.read().strip()
        except OSError as e:
            raise ConfigSecretError("Failed to read encryption key file '{}': {}".format(key_file_path, str(e)))
        if not key:
            raise ConfigSecretError("Encryption key file '{}' is empty".format(key_file_path))
        return key

    @staticmethod
    def _create_key_file(key_file_path: str) -> bytes:
        key_dir = os.path.dirname(key_file_path) or "."
        try:
            os.makedirs(key_dir, exist_ok=True)
        except OSError as e:
            raise ConfigSecretError(
                "Failed to create config directory for encryption key '{}': {}".format(key_file_path, str(e))
            )

        key = Fernet.generate_key()
        try:
            fd, tmp_path = tempfile.mkstemp(dir=key_dir, prefix=".tmp_encryption_key_")
        except OSError as e:
            raise ConfigSecretError(
                "Failed to create temporary encryption key file '{}': {}".format(key_file_path, str(e))
            )
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "wb") as f:
                f.write(key)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, key_file_path)
        except BaseException as e:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            if isinstance(e, OSError):
                raise ConfigSecretError(
                    "Failed to write encryption key file '{}': {}".format(key_file_path, str(e))
                )
            raise
        return key

    @staticmethod
    def _restrict_permissions(key_file_path: str):
        try:
            os.chmod(key_file_path, 0o600)
        except OSError as e:
            raise ConfigSecretError(
                "Failed to secure encryption key file '{}': {}".format(key_file_path, str(e))
            )

    def encrypt(self, plaintext: str) -> str:
        encrypted = self._fernet.encrypt(plaintext.encode("utf-8")).decode("utf-8")
        return "{}{}".format(ENCRYPTED_PREFIX, encrypted)

    def decrypt_if_needed(self, value: str) -> Tuple[str, bool, bool]:
        if value is None or value == "":
            return value, False, False
        if not value.startswith(ENCRYPTED_PREFIX):
            return value, False, True

        token = value[len(ENCRYPTED_PREFIX):]
        try:
            decrypted = self._fernet.decrypt(token.encode("utf-8")).decode("utf-8")
        except InvalidToken as e:
            raise ConfigSecretError(
                "Failed to decrypt encrypted config value from '{}'".format(self.key_file_path)
            ) from e
        return decrypted, True, False
