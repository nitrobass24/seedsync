# Copyright 2017, Inderpreet Singh, All rights reserved.

from __future__ import annotations

import datetime
import errno
import os
import shutil
from typing import override

from common import AppOneShotProcess, Constants, PipeStream


class MoveFailedResult:
    """Result reported when a staging->final move fails."""

    def __init__(
        self,
        timestamp: datetime.datetime,
        name: str,
        pair_id: str | None = None,
        error_message: str | None = None,
    ):
        self.timestamp = timestamp
        self.name = name
        self.pair_id = pair_id
        self.error_message = error_message


class MoveProcess(AppOneShotProcess):
    """
    One-shot process that moves a file or directory from source_path to dest_path.
    Tries os.rename() first (instant on same filesystem), falls back to
    shutil.copytree()/shutil.copy2() + size verification + source removal
    for cross-device moves.
    """

    def __init__(self, source_path: str, dest_path: str, file_name: str, pair_id: str | None = None):
        super().__init__(name=self.__class__.__name__)
        self.__source_path = source_path
        self.__dest_path = dest_path
        self.__file_name = file_name
        self._pair_id = pair_id
        self.__failed_result_stream = PipeStream()

    @property
    def file_name(self) -> str:
        return self.__file_name

    @property
    def pair_id(self) -> str | None:
        return self._pair_id

    @staticmethod
    def _get_total_size(path: str) -> int:
        """Walk the path and return total size in bytes."""
        if os.path.isfile(path):
            return os.path.getsize(path)
        total = 0
        for dirpath, _dirnames, filenames in os.walk(path):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                if os.path.exists(fp):
                    total += os.path.getsize(fp)
        return total

    @staticmethod
    def _get_copied_size(src: str, dst: str) -> int:
        """Sum the sizes at dst of only the files present in the src subtree.

        This deliberately ignores any pre-existing files under dst so that
        merging into a non-empty destination (dirs_exist_ok=True) does not
        produce a false size mismatch (issue #510).
        """
        if os.path.isfile(src):
            return os.path.getsize(dst) if os.path.exists(dst) else 0
        total = 0
        for dirpath, _dirnames, filenames in os.walk(src):
            rel_dir = os.path.relpath(dirpath, src)
            for f in filenames:
                dst_file = os.path.join(dst, rel_dir, f) if rel_dir != "." else os.path.join(dst, f)
                if os.path.exists(dst_file):
                    total += os.path.getsize(dst_file)
        return total

    @staticmethod
    def _has_lftp_temp_files(src: str) -> bool:
        """True if the source tree still contains lftp temp files (``*.lftp``).

        lftp writes each download to ``<name>.lftp`` and renames it to the final
        name on completion. A staging tree that still holds temp files has not
        been finalized — moving it would race lftp's in-flight rename.
        """
        suffix = Constants.LFTP_TEMP_FILE_SUFFIX
        if os.path.isfile(src):
            return src.endswith(suffix)
        return any(any(f.endswith(suffix) for f in filenames) for _root, _dirs, filenames in os.walk(src))

    def _report_failure(self, message: str) -> None:
        """Log and publish a move failure so the controller can surface it."""
        self.logger.error(message)
        self.__failed_result_stream.put(
            MoveFailedResult(
                timestamp=datetime.datetime.now(),
                name=self.__file_name,
                pair_id=self._pair_id,
                error_message=message,
            )
        )

    def run_once(self):
        src = os.path.join(self.__source_path, self.__file_name)
        dst = os.path.join(self.__dest_path, self.__file_name)

        if not os.path.exists(src):
            self._report_failure(f"Move failed: source does not exist: {src}")
            return

        # Defer while lftp is still finalizing the staging tree. lftp renames
        # "<name>.lftp" -> "<name>" on completion; copying (or renaming the
        # whole tree) while a rename is in flight races — copytree lists the
        # ".lftp" entry, lftp renames it, and the copy then fails with ENOENT
        # (which used to crash this process). A tree that still has temp files is
        # not ready, so report a recoverable failure and retry once lftp finishes.
        if self._has_lftp_temp_files(src):
            self._report_failure(
                f"Move deferred for {self.__file_name}: download not finalized "
                "(lftp temp files still present in staging). Will retry."
            )
            return

        self.logger.info(f"Moving {src} -> {dst}")

        # Ensure destination parent directory exists
        os.makedirs(self.__dest_path, exist_ok=True)

        # Try rename first (instant on same filesystem)
        try:
            os.rename(src, dst)
            self.logger.info(f"Move completed via rename: {self.__file_name}")
            return
        except OSError as e:
            if e.errno == errno.EXDEV:
                self.logger.debug("Cross-device move detected, falling back to copy+delete")
            elif e.errno in (errno.ENOTEMPTY, errno.EEXIST):
                # Destination already exists as a non-empty directory; rename
                # cannot merge, so fall back to copy+delete which merges trees.
                self.logger.debug("Destination not empty, falling back to copy+delete")
            else:
                raise

        # Cross-device fallback: copy, verify size, then remove source
        source_size = self._get_total_size(src)

        try:
            if os.path.isfile(src):
                shutil.copy2(src, dst)
            else:
                shutil.copytree(src, dst, dirs_exist_ok=True)
        except (shutil.Error, OSError) as e:
            # A *.lftp temp file can still be renamed by lftp during the copy (a
            # narrow window the pre-check above doesn't fully close). Report a
            # recoverable failure and keep the source intact so the move is
            # retried — never crash the controller.
            self._report_failure(f"Move copy failed for {self.__file_name}: {e}. Source NOT deleted.")
            return

        # Verify only the copied subtree (ignore pre-existing files under dst)
        copied_size = self._get_copied_size(src, dst)

        if source_size != copied_size:
            self._report_failure(
                f"Move size verification failed for {self.__file_name}: "
                f"source={source_size} copied={copied_size}. Source NOT deleted."
            )
            return

        # Size verified, remove source
        if os.path.isfile(src):
            os.remove(src)
        else:
            shutil.rmtree(src)

        self.logger.info(f"Move completed via copy+delete: {self.__file_name}")

    def pop_failed(self) -> list[MoveFailedResult]:
        """Process-safe method to retrieve any move failures."""
        return self.__failed_result_stream.pop_all()

    @override
    def close_queues(self):
        self.__failed_result_stream.close()
        super().close_queues()
