# Copyright 2017, Inderpreet Singh, All rights reserved.

import logging
import os
import stat


def apply_umask_modes(root: str, umask: int, logger: logging.Logger) -> None:
    """Set everything under root (inclusive) to 0666/0777 & ~umask.

    lftp creates files as 0664 and directories as 0775 before the umask is
    applied, so UMASK=000 can never yield the documented 666/777 through lftp
    alone (#811). This pass runs once per completed download. Symlinks are left
    alone; a path that can't be changed is logged and skipped.
    """
    file_mode = 0o666 & ~umask
    dir_mode = 0o777 & ~umask

    def chmod(path: str, mode: int) -> None:
        try:
            if os.path.islink(path):
                return
            if stat.S_IMODE(os.stat(path).st_mode) != mode:
                os.chmod(path, mode)
        except OSError as e:
            logger.warning(f"Could not set mode {mode:o} on {path}: {e}")

    if os.path.isdir(root) and not os.path.islink(root):
        chmod(root, dir_mode)
        for dirpath, dirnames, filenames in os.walk(root):
            for name in dirnames:
                chmod(os.path.join(dirpath, name), dir_mode)
            for name in filenames:
                chmod(os.path.join(dirpath, name), file_mode)
    elif os.path.exists(root):
        chmod(root, file_mode)
