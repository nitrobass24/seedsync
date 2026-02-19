# Copyright 2017, Inderpreet Singh, All rights reserved.


def escape_remote_path_single(path: str) -> str:
    """
    Escape a remote path using single quotes (no variable expansion).
    Single quotes within the path are escaped using the shell '\\'' trick.
    """
    escaped = path.replace("'", "'\\''")
    return "'{}'".format(escaped)


def escape_remote_path_double(path: str) -> str:
    """
    Escape a remote path using double quotes (allows $HOME expansion).
    Converts ~ to $HOME for shell expansion.
    """
    if path.startswith("~"):
        path = "$HOME" + path[1:]
    return '"{}"'.format(path)
