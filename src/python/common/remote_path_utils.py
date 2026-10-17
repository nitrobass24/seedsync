# Copyright 2017, Inderpreet Singh, All rights reserved.

import shlex


def escape_remote_path_single(path: str) -> str:
    """
    Escape a remote path using single quotes (no variable expansion).
    Single quotes within the path are escaped using the shell '\\'' trick.
    """
    escaped = path.replace("'", "'\\''")
    return f"'{escaped}'"


def escape_remote_path_double(path: str) -> str:
    """
    Quote a remote path so the remote shell expands a leading ~ or ~/ to $HOME
    and nothing else: "$HOME" stays in double quotes, the rest is shell-quoted
    (so quotes, $ and backticks in names stay literal). Any other path,
    including ~user, is shell-quoted as-is.
    """
    if path == "~":
        return '"$HOME"'
    if path.startswith("~/"):
        return '"$HOME"' + shlex.quote(path[1:])
    return shlex.quote(path)
