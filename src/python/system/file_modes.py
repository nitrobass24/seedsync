# Copyright 2017, Inderpreet Singh, All rights reserved.

import logging
import os
import stat
from collections.abc import Iterable

# setgid/sticky on a directory come from its parent and decide the group of
# new files; UMASK is about rwx bits, so leave those alone.
_DIR_SPECIAL_BITS = stat.S_ISGID | stat.S_ISVTX


def _chmod(path: str, mode: int, logger: logging.Logger) -> None:
    try:
        if os.path.islink(path):
            return
        st = os.stat(path)
        current = stat.S_IMODE(st.st_mode)
        if stat.S_ISDIR(st.st_mode):
            mode |= current & _DIR_SPECIAL_BITS
        if current != mode:
            os.chmod(path, mode)
    except OSError as e:
        logger.warning(f"Could not set mode {mode:o} on {path}: {e}")


def apply_umask_modes(root: str, umask: int, logger: logging.Logger) -> None:
    """Set everything under root (inclusive) to 0666/0777 & ~umask.

    lftp creates files as 0664 and directories as 0775 before the umask is
    applied, so UMASK=000 can never yield the documented 666/777 through lftp
    alone (#811). Walks bottom-up so a restrictive umask (e.g. 0177) does not
    strip search permission from a directory before its contents are visited.
    Symlinks are left alone; a path that can't be changed is logged and skipped.
    """
    file_mode = 0o666 & ~umask
    dir_mode = 0o777 & ~umask
    if os.path.isdir(root) and not os.path.islink(root):
        for dirpath, _dirnames, filenames in os.walk(root, topdown=False):
            for name in filenames:
                _chmod(os.path.join(dirpath, name), file_mode, logger)
            _chmod(dirpath, dir_mode, logger)
    elif os.path.exists(root):
        _chmod(root, file_mode, logger)


def apply_umask_modes_to(base: str, entries: Iterable[tuple[str, bool]], umask: int, logger: logging.Logger) -> None:
    """Like apply_umask_modes, but only for the given (relative path, is_dir)
    entries under base -- used after a staged tree is merged into an existing
    destination so pre-existing files there keep their modes.
    """
    file_mode = 0o666 & ~umask
    dir_mode = 0o777 & ~umask
    # Deepest first, for the same reason apply_umask_modes walks bottom-up.
    for rel, is_dir in sorted(entries, key=lambda e: e[0].count(os.sep), reverse=True):
        _chmod(os.path.join(base, rel), dir_mode if is_dir else file_mode, logger)


def relative_entries(root: str) -> list[tuple[str, bool]]:
    """(relative path, is_dir) for root itself and everything under it."""
    if not os.path.isdir(root) or os.path.islink(root):
        return [(".", False)] if os.path.exists(root) else []
    entries: list[tuple[str, bool]] = [(".", True)]
    for dirpath, dirnames, filenames in os.walk(root):
        rel_dir = os.path.relpath(dirpath, root)
        for name in dirnames:
            entries.append((os.path.normpath(os.path.join(rel_dir, name)), True))
        for name in filenames:
            entries.append((os.path.normpath(os.path.join(rel_dir, name)), False))
    return entries
