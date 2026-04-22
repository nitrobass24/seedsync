# Copyright 2017, Inderpreet Singh, All rights reserved.

import contextlib
import glob
import logging
import os
import shutil
import tempfile
from abc import ABC, abstractmethod
from datetime import datetime
from typing import TypeVar

from .error import AppError
from .localization import Localization

_logger = logging.getLogger(__name__)

_BACKUP_DIR_NAME = "backups"
_MAX_BACKUPS = 10


# Source: https://stackoverflow.com/a/39205612/8571324
T_Persist = TypeVar("T_Persist", bound="Persist")
T_Serializable = TypeVar("T_Serializable", bound="Serializable")


class Serializable(ABC):
    """
    Defines a class that is serializable to string.
    The string representation must be human readable (i.e. not pickle)
    """

    @classmethod
    @abstractmethod
    def from_str(cls: type[T_Serializable], content: str) -> T_Serializable:
        pass

    @abstractmethod
    def to_str(self) -> str:
        pass


class PersistError(AppError):
    """
    Exception indicating persist loading/saving error
    """

    pass


class Persist(Serializable):
    """
    Defines state that should be persisted between runs
    Provides utility methods to persist/load content to/from file
    Concrete implementations need to implement the from_str() and
    to_str() functionality
    """

    @classmethod
    def from_file(cls: type[T_Persist], file_path: str) -> T_Persist:
        if not os.path.isfile(file_path):
            raise AppError(Localization.Error.MISSING_FILE.format(file_path))
        with open(file_path) as f:
            return cls.from_str(f.read())

    def to_file(self, file_path: str):
        dir_name = os.path.dirname(file_path) or "."

        # Backup existing file before overwriting (best-effort; never abort the save)
        if os.path.isfile(file_path):
            try:
                self._backup_file(file_path, dir_name)
            except OSError as e:
                _logger.error("Failed to back up %s in %s: %s", file_path, dir_name, e)

        fd, tmp_path = tempfile.mkstemp(dir=dir_name, prefix=".tmp_persist_")
        try:
            with os.fdopen(fd, "w") as f:
                f.write(self.to_str())
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, file_path)
        except BaseException:
            with contextlib.suppress(OSError):
                os.unlink(tmp_path)
            raise

    @staticmethod
    def _backup_file(file_path: str, dir_name: str):
        """Copy the current file to backups/ with an ISO timestamp, then prune old backups."""
        backup_dir = os.path.join(dir_name, _BACKUP_DIR_NAME)
        os.makedirs(backup_dir, exist_ok=True)

        base_name = os.path.basename(file_path)
        name, ext = os.path.splitext(base_name)
        timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S-%f")
        backup_name = f"{name}-{timestamp}{ext}"
        backup_path = os.path.join(backup_dir, backup_name)

        shutil.copy2(file_path, backup_path)

        # Prune old backups, keeping only the most recent _MAX_BACKUPS
        pattern = os.path.join(backup_dir, f"{glob.escape(name)}-????-??-??T??-??-??-??????{glob.escape(ext)}")
        backups = sorted(glob.glob(pattern))
        for old_backup in backups[:-_MAX_BACKUPS]:
            with contextlib.suppress(OSError):
                os.remove(old_backup)

    @classmethod
    @abstractmethod
    def from_str(cls: type[T_Persist], content: str) -> T_Persist:
        pass

    @abstractmethod
    def to_str(self) -> str:
        pass
