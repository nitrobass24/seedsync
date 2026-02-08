# Copyright 2017, Inderpreet Singh, All rights reserved.


def escape_remote_path_single(path: str) -> str:
    """
    Escape a remote path using single quotes (no variable expansion).
    """
    return "'{}'".format(path)


def escape_remote_path_double(path: str) -> str:
    """
    Escape a remote path using double quotes (allows $HOME expansion).
    Converts ~ to $HOME for shell expansion.
    """
    if path.startswith("~"):
        path = "$HOME" + path[1:]
    return '"{}"'.format(path)
