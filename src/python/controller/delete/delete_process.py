# Copyright 2017, Inderpreet Singh, All rights reserved.

import os
import shutil

from common import AppOneShotProcess, escape_remote_path_double, escape_remote_path_single
from ssh import Sshcp


def _is_contained(base_path: str, target_path: str) -> bool:
    """Return True if the resolved target_path is strictly inside resolved base_path."""
    real_base = os.path.realpath(base_path)
    real_target = os.path.realpath(target_path)
    try:
        common = os.path.commonpath([real_base, real_target])
    except ValueError:
        return False
    return common == real_base and real_target != real_base


def _resolve_child_path(base_path: str, relative_path: str) -> str | None:
    """Resolve relative_path under base_path without following a final symlink.

    Ancestor components are resolved, so a symlinked directory cannot be used to
    reach outside base_path. The final component is deliberately left unresolved:
    a local-only symlink must be unlinked where it sits, not followed to its
    target (resolving it would flag a link pointing outside as traversal and
    leave it undeletable).

    Returns the resolved path, or None if it escapes base_path.
    """
    name = os.path.basename(relative_path)
    if name in ("", ".", ".."):
        return None
    real_base = os.path.realpath(base_path)
    real_parent = os.path.realpath(os.path.join(real_base, os.path.dirname(relative_path)))
    try:
        common = os.path.commonpath([real_base, real_parent])
    except ValueError:
        return None
    if common != real_base:
        return None
    return os.path.join(real_parent, name)


class DeleteLocalProcess(AppOneShotProcess):
    def __init__(self, local_path: str, file_name: str):
        super().__init__(name=self.__class__.__name__)
        self.__local_path = local_path
        self.__file_name = file_name

    def run_once(self):
        file_path = os.path.join(self.__local_path, self.__file_name)
        if not _is_contained(self.__local_path, file_path):
            self.logger.error(f"Path traversal blocked: {file_path} escapes {self.__local_path}")
            return
        self.logger.debug(f"Deleting local file {self.__file_name}")
        if not os.path.exists(file_path):
            self.logger.error(f"Failed to delete non-existing file: {file_path}")
        else:
            if os.path.isfile(file_path):
                os.remove(file_path)
            else:
                shutil.rmtree(file_path, ignore_errors=True)


class CleanupLocalProcess(AppOneShotProcess):
    """
    Deletes each of ``relative_paths`` beneath ``<local_path>/<file_name>``. Each
    path is containment-checked against that base and skipped (with an error log)
    if it escapes. Symlinks are unlinked, never followed, so a link is removed
    without touching whatever it points at. The folder itself is never removed.
    The caller is responsible for choosing only local-only paths; ``local_path``
    may be a staging dir.

    Raises RuntimeError if any path fails to delete, so the caller never treats
    a partial cleanup as a full success.
    """

    def __init__(self, local_path: str, file_name: str, relative_paths: list[str]):
        super().__init__(name=self.__class__.__name__)
        self.__local_path = local_path
        self.__file_name = file_name
        self.__relative_paths = relative_paths

    def run_once(self):
        base_path = os.path.join(self.__local_path, self.__file_name)
        self.logger.debug(f"Cleaning up local-only contents of {self.__file_name}")
        failures: list[str] = []
        for relative_path in self.__relative_paths:
            file_path = _resolve_child_path(base_path, relative_path)
            if file_path is None:
                self.logger.error(f"Path traversal blocked: {relative_path} escapes {base_path}")
                failures.append(f"{relative_path}: escapes base path")
                continue
            # lexists, not exists: a dangling symlink is still ours to remove.
            if not os.path.lexists(file_path):
                self.logger.error(f"Failed to delete non-existing file: {file_path}")
                failures.append(f"{relative_path}: does not exist")
                continue
            try:
                # islink first, so a symlink to a directory is unlinked rather
                # than handed to rmtree (which refuses it).
                if os.path.islink(file_path) or os.path.isfile(file_path):
                    os.unlink(file_path)
                else:
                    shutil.rmtree(file_path)
            except OSError as exc:
                self.logger.error(f"Failed to delete {file_path}: {exc!s}")
                failures.append(f"{relative_path}: {exc!s}")
        if failures:
            raise RuntimeError(f"Failed to clean up {len(failures)} path(s): {'; '.join(failures)}")


class DeleteRemoteProcess(AppOneShotProcess):
    def __init__(
        self,
        remote_address: str,
        remote_username: str,
        remote_password: str | None,
        remote_port: int,
        remote_path: str,
        file_name: str,
    ):
        super().__init__(name=self.__class__.__name__)
        self.__remote_path = remote_path
        self.__file_name = file_name
        self.__ssh = Sshcp(host=remote_address, port=remote_port, user=remote_username, password=remote_password)

    def run_once(self):
        self.__ssh.set_base_logger(self.logger)
        # Reject path traversal in filename (defense-in-depth)
        normalized = os.path.normpath(self.__file_name)
        if (
            not normalized
            or normalized == os.curdir
            or normalized == os.pardir
            or normalized.startswith(".." + os.sep)
            or os.path.isabs(normalized)
        ):
            self.logger.error(f"Path traversal blocked in remote delete: {self.__file_name}")
            return
        file_path = os.path.join(self.__remote_path, self.__file_name)
        self.logger.info(f"Deleting remote file: {self.__file_name}")
        if file_path.startswith("~"):
            escaped_path = escape_remote_path_double(file_path)
        else:
            escaped_path = escape_remote_path_single(file_path)
        out = self.__ssh.shell(f"rm -rf {escaped_path}")
        self.logger.debug(f"Remote delete output: {out.decode()}")
        self.logger.info(f"Successfully deleted remote file: {self.__file_name}")
