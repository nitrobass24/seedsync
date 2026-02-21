# Copyright 2017, Inderpreet Singh, All rights reserved.

import os
import shutil
import errno

from common import AppOneShotProcess


class MoveProcess(AppOneShotProcess):
    """
    One-shot process that moves a file or directory from source_path to dest_path.
    Tries os.rename() first (instant on same filesystem), falls back to
    shutil.copytree()/shutil.copy2() + size verification + source removal
    for cross-device moves.
    """
    def __init__(self, source_path: str, dest_path: str, file_name: str):
        super().__init__(name=self.__class__.__name__)
        self.__source_path = source_path
        self.__dest_path = dest_path
        self.__file_name = file_name

    @staticmethod
    def _get_total_size(path: str) -> int:
        """Walk the path and return total size in bytes."""
        if os.path.isfile(path):
            return os.path.getsize(path)
        total = 0
        for dirpath, dirnames, filenames in os.walk(path):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                if os.path.exists(fp):
                    total += os.path.getsize(fp)
        return total

    def run_once(self):
        src = os.path.join(self.__source_path, self.__file_name)
        dst = os.path.join(self.__dest_path, self.__file_name)

        if not os.path.exists(src):
            self.logger.error("Move failed: source does not exist: {}".format(src))
            return

        self.logger.info("Moving {} -> {}".format(src, dst))

        # Ensure destination parent directory exists
        os.makedirs(self.__dest_path, exist_ok=True)

        # Try rename first (instant on same filesystem)
        try:
            os.rename(src, dst)
            self.logger.info("Move completed via rename: {}".format(self.__file_name))
            return
        except OSError as e:
            if e.errno == errno.EXDEV:
                self.logger.debug("Cross-device move detected, falling back to copy+delete")
            else:
                raise

        # Cross-device fallback: copy, verify size, then remove source
        source_size = self._get_total_size(src)

        if os.path.isfile(src):
            shutil.copy2(src, dst)
        else:
            shutil.copytree(src, dst, dirs_exist_ok=True)

        dest_size = self._get_total_size(dst)

        if source_size != dest_size:
            self.logger.error(
                "Move size verification failed for {}: source={} dest={}. "
                "Source NOT deleted.".format(self.__file_name, source_size, dest_size)
            )
            return

        # Size verified, remove source
        if os.path.isfile(src):
            os.remove(src)
        else:
            shutil.rmtree(src)

        self.logger.info("Move completed via copy+delete: {}".format(self.__file_name))
