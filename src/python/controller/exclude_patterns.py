# Copyright 2017, Inderpreet Singh, All rights reserved.

"""Exclude-pattern filtering for remote and local file lists.

Pure functions — no state, no side effects. Extracted from controller.py
as part of the controller decomposition (#394 Phase 1A).
"""

from __future__ import annotations

import fnmatch
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from system import SystemFile


def parse_exclude_patterns(exclude_patterns_str: str) -> list[str]:
    """Parse a comma-separated exclude pattern string into a list of individual patterns.

    Trailing slashes are preserved so callers can distinguish directory-only
    patterns from file patterns when needed.
    """
    if not exclude_patterns_str or not exclude_patterns_str.strip():
        return []
    patterns: list[str] = []
    for p in exclude_patterns_str.split(","):
        p = p.strip()
        if p:
            patterns.append(p)
    return patterns


def filter_excluded_files(files: list[SystemFile], exclude_patterns_str: str) -> list[SystemFile]:
    """Filter a list of files, removing any that match the exclude patterns.

    Patterns are comma-separated globs. A trailing ``/`` restricts matching to
    directories only.  Matching is case-insensitive.  Directory matches drop the
    entire subtree.
    """
    parsed = parse_exclude_patterns(exclude_patterns_str)
    if not parsed:
        return files
    patterns = [(p.rstrip("/"), p.endswith("/")) for p in parsed]
    result: list[SystemFile] = []
    for f in files:
        if _matches_exclude(f.name, f.is_dir, patterns):
            continue
        if f.is_dir:
            f = _filter_children(f, patterns)
        result.append(f)
    return result


def _matches_exclude(name: str, is_dir: bool, patterns: list[tuple[str, bool]]) -> bool:
    """Return True if *name* matches any of the exclude patterns (case-insensitive).

    Each pattern is a (glob, dir_only) tuple.  When dir_only is True the
    pattern only matches directories.
    """
    name_lower = name.lower()
    return any(fnmatch.fnmatch(name_lower, p.lower()) and (not dir_only or is_dir) for p, dir_only in patterns)


def _filter_children(file: SystemFile, patterns: list[tuple[str, bool]]) -> SystemFile:
    """Return a copy of *file* with excluded children (and their subtrees) removed.

    If a directory child matches a pattern the entire subtree is dropped.
    Non-matching directory children are recursed into so their own children
    are filtered as well.  Directory sizes are preserved from the original file.
    """
    from system import SystemFile  # avoid circular import at module level

    kept_children: list[SystemFile] = []
    for child in file.children:
        if _matches_exclude(child.name, child.is_dir, patterns):
            continue  # drop matched child (and its subtree)
        if child.is_dir:
            child = _filter_children(child, patterns)
        kept_children.append(child)

    filtered = SystemFile(
        name=file.name,
        size=file.size,
        is_dir=file.is_dir,
        time_created=file.timestamp_created,
        time_modified=file.timestamp_modified,
    )
    for child in kept_children:
        filtered.add_child(child)
    return filtered
