# Copyright 2017, Inderpreet Singh, All rights reserved.

from __future__ import annotations

import contextlib
import datetime
import errno
import os
import shutil
import stat
from dataclasses import dataclass
from typing import override

from common import AppOneShotProcess, Constants, PipeStream
from system import apply_umask_modes_to, relative_entries


@dataclass
class MoveFailedResult:
    """Result reported when a staging->final move fails."""

    timestamp: datetime.datetime
    name: str
    pair_id: str | None = None
    error_message: str | None = None


class MoveProcess(AppOneShotProcess):
    """
    One-shot process that moves a file or directory from source_path to dest_path.
    Tries os.rename() first (instant on same filesystem), falls back to
    shutil.copytree()/shutil.copy2() + size verification + source removal
    for cross-device moves.
    """

    def __init__(
        self,
        source_path: str,
        dest_path: str,
        file_name: str,
        pair_id: str | None = None,
        umask: int | None = None,
        expected_size: int | None = None,
        nested_expected_sizes: dict[str, int | None] | None = None,
    ):
        super().__init__(name=self.__class__.__name__)
        self.__source_path = source_path
        self.__dest_path = dest_path
        self.__file_name = file_name
        self._pair_id = pair_id
        # When set, the moved tree is chmod'ed to 0666/0777 & ~umask here, in
        # this process, rather than on the controller thread (#811).
        self.__umask = umask
        # When set, a source smaller than this or still holding lftp temp files
        # is left in place, with no failure reported.
        self.__expected_size = expected_size
        # {path relative to file_name: expected size} of descendants to check
        # the same way; an incomplete one (or one of unknown size) is left in
        # place while the rest of the tree moves.
        self.__nested_expected_sizes = nested_expected_sizes or {}
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
    def _has_lftp_temp_files(src: str, skip: frozenset[str] = frozenset()) -> bool:
        """True if the source tree still contains lftp temp files (``*.lftp``),
        not counting anything under the paths in ``skip``.

        lftp writes each download to ``<name>.lftp`` and renames it to the final
        name on completion. A staging tree that still holds temp files has not
        been finalized — moving it would race lftp's in-flight rename.
        """
        suffix = Constants.LFTP_TEMP_FILE_SUFFIX
        if os.path.isfile(src):
            return src.endswith(suffix) and src not in skip
        for root, dirs, filenames in os.walk(src):
            dirs[:] = [d for d in dirs if os.path.join(root, d) not in skip]
            if any(f.endswith(suffix) and os.path.join(root, f) not in skip for f in filenames):
                return True
        return False

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

        if self.__expected_size is not None and (
            self._has_lftp_temp_files(src) or self._get_total_size(src) < self.__expected_size
        ):
            self.logger.info(f"Move skipped for {self.__file_name}: download incomplete, left in staging")
            return

        incomplete = self._incomplete_nested(src)

        # Defer while lftp is still finalizing the staging tree. lftp renames
        # "<name>.lftp" -> "<name>" on completion; copying (or renaming the
        # whole tree) while a rename is in flight races — copytree lists the
        # ".lftp" entry, lftp renames it, and the copy then fails with ENOENT
        # (which used to crash this process). A tree that still has temp files is
        # not ready, so report a recoverable failure and retry once lftp finishes.
        if self._has_lftp_temp_files(src, incomplete):
            self._report_failure(
                f"Move deferred for {self.__file_name}: download not finalized "
                "(lftp temp files still present in staging). Will retry."
            )
            return

        self.logger.info(f"Moving {src} -> {dst}")

        # Ensure the destination's parent exists (several levels for a nested name)
        os.makedirs(os.path.dirname(dst), exist_ok=True)

        if not incomplete:
            if not self._move_item(src, dst):
                return
        else:
            if not self._move_tree(src, dst, incomplete):
                return
            left = ", ".join(sorted(os.path.relpath(p, self.__source_path) for p in incomplete))
            self.logger.info(f"Left incomplete nested downloads in staging: {left}")
        self.__prune_empty_staging_parents(src)

    def _incomplete_nested(self, src: str) -> frozenset[str]:
        """Absolute staging paths of the listed nested downloads under src that
        aren't complete yet (temp files, short, or of unknown size)."""
        incomplete: set[str] = set()
        for rel, size in self.__nested_expected_sizes.items():
            path = os.path.join(src, rel)
            temp_path = path + Constants.LFTP_TEMP_FILE_SUFFIX
            if not os.path.exists(path) and os.path.isfile(temp_path):
                # An unfinished file with lftp temp files on: "<name>.lftp" until done
                incomplete.add(temp_path)
            elif os.path.exists(path) and (
                size is None or self._has_lftp_temp_files(path) or self._get_total_size(path) < size
            ):
                incomplete.add(path)
        return frozenset(incomplete)

    def _move_tree(self, src: str, dst: str, incomplete: frozenset[str]) -> bool:
        """Move src to dst, leaving the paths in ``incomplete`` (and the dirs
        holding them) in staging. Subtrees without one move whole."""
        if src in incomplete:
            return True
        if not any(p.startswith(src + os.sep) for p in incomplete):
            # Parents are made only once something lands in them, so a dir
            # holding nothing but incomplete downloads isn't created at dst.
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            return self._move_item(src, dst)
        created = not os.path.exists(dst)
        for entry in os.listdir(src):
            if not self._move_tree(os.path.join(src, entry), os.path.join(dst, entry), incomplete):
                return False
        if created and os.path.isdir(dst):
            # Made here by a child's makedirs; a dir that was already there keeps its mode
            self.__apply_modes(dst, [(".", True)])
        with contextlib.suppress(OSError):  # still holds an incomplete download
            os.rmdir(src)
        return True

    def _move_item(self, src: str, dst: str) -> bool:
        """Move one file or tree: rename, or copy + verify + delete across
        devices or onto a non-empty dir. Reports and returns False on failure."""
        name = os.path.relpath(src, self.__source_path)

        # What we are about to move, so the UMASK pass can be limited to it: a
        # copy that merges into an existing destination must leave the files
        # already there alone (#811). Directories that already exist at the
        # destination keep their own modes too: copytree would copystat the
        # source's onto them, and the UMASK pass must not widen them either.
        moved_entries = relative_entries(src) if self.__umask is not None else []
        existing_dir_modes = self._existing_dir_modes(dst)

        # Try rename first (instant on same filesystem)
        try:
            os.rename(src, dst)
            self.logger.info(f"Move completed via rename: {name}")
            self.__apply_modes(dst, moved_entries)
            return True
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
            self._report_failure(f"Move copy failed for {name}: {e}. Source NOT deleted.")
            return False

        # Verify only the copied subtree (ignore pre-existing files under dst)
        copied_size = self._get_copied_size(src, dst)

        if source_size != copied_size:
            self._report_failure(
                f"Move size verification failed for {name}: "
                f"source={source_size} copied={copied_size}. Source NOT deleted."
            )
            return False

        # Size verified, remove source
        if os.path.isfile(src):
            os.remove(src)
        else:
            shutil.rmtree(src)

        self.logger.info(f"Move completed via copy+delete: {name}")
        for rel, mode in existing_dir_modes.items():
            os.chmod(os.path.join(dst, rel), mode)
        self.__apply_modes(dst, [e for e in moved_entries if e[0] not in existing_dir_modes])
        return True

    @staticmethod
    def _existing_dir_modes(dst: str) -> dict[str, int]:
        """Modes of the directories already present under dst (merge case)."""
        if not os.path.isdir(dst) or os.path.islink(dst):
            return {}
        modes: dict[str, int] = {".": stat.S_IMODE(os.stat(dst).st_mode)}
        for dirpath, dirnames, _filenames in os.walk(dst):
            for name in dirnames:
                full = os.path.join(dirpath, name)
                if not os.path.islink(full):
                    modes[os.path.normpath(os.path.relpath(full, dst))] = stat.S_IMODE(os.stat(full).st_mode)
        return modes

    def __apply_modes(self, dst: str, moved_entries: list[tuple[str, bool]]) -> None:
        if self.__umask is not None:
            apply_umask_modes_to(dst, moved_entries, self.__umask, self.logger)

    def __prune_empty_staging_parents(self, src: str) -> None:
        """Remove the staging dirs a nested name's move emptied, up to (not
        including) source_path. Stops at the first one still holding something,
        such as another nested job's download."""
        parent = os.path.dirname(src)
        while os.path.normpath(parent) != os.path.normpath(self.__source_path):
            try:
                os.rmdir(parent)
            except OSError:
                return
            parent = os.path.dirname(parent)

    def pop_failed(self) -> list[MoveFailedResult]:
        """Process-safe method to retrieve any move failures."""
        return self.__failed_result_stream.pop_all()

    @override
    def close_queues(self):
        self.__failed_result_stream.close()
        super().close_queues()
