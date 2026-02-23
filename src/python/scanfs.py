# Copyright 2017, Inderpreet Singh, All rights reserved.
#
# Standalone Python fallback scanner for SeedSync.
#
# Replicates the binary output of the compiled scanfs executable when the
# binary cannot run on the remote server (e.g. glibc version incompatibility
# on older Debian/Ubuntu systems).
#
# Usage:  python3 scanfs.py <path>
# Output: pickled List[system.file.SystemFile] written to stdout (binary)
#
# IMPORTANT: This script is self-contained and has no external dependencies
# beyond the Python 3 standard library.  It is uploaded to the remote server
# and executed there, so it must not import anything from the SeedSync package.

import argparse
import os
import pickle
import re
import sys
from datetime import datetime

_LFTP_STATUS_SUFFIX = ".lftp-pget-status"


class SystemFile:
    """
    Mirrors system.file.SystemFile exactly so that pickle output is compatible
    with the local SeedSync process.

    Python name-mangling turns ``self.__foo`` into ``self._SystemFile__foo``
    regardless of which module the class lives in, so instances created here
    carry the same __dict__ keys as instances created by the real class.
    Setting ``__module__`` makes pickle encode the class reference as
    ``system.file.SystemFile``; the local unpickler then imports that module,
    finds the real class, and reconstructs objects transparently.
    """

    def __init__(self, name, size, is_dir=False, time_created=None, time_modified=None):
        if size < 0:
            raise ValueError("File size must be greater than zero")
        self.__name = name
        self.__size = size
        self.__is_dir = is_dir
        self.__timestamp_created = time_created
        self.__timestamp_modified = time_modified
        self.__children = []

    @property
    def name(self):
        return self.__name

    @property
    def size(self):
        return self.__size

    @property
    def is_dir(self):
        return self.__is_dir

    @property
    def children(self):
        return self.__children

    def add_child(self, child):
        if not self.__is_dir:
            raise TypeError("Cannot add children to a file")
        self.__children.append(child)


# Override the module so pickle encodes instances as 'system.file.SystemFile'.
# The local SeedSync process has system.file importable, and the real
# SystemFile.__dict__ keys match ours (same name-mangling, same attribute names).
SystemFile.__module__ = "system.file"

# Register synthetic module entries so pickle can verify the class is
# "importable" at pickle time on the remote server (where system.file
# does not actually exist on disk).
import types as _types
_fake_system = _types.ModuleType("system")
_fake_system_file = _types.ModuleType("system.file")
_fake_system_file.SystemFile = SystemFile
sys.modules.setdefault("system", _fake_system)
sys.modules.setdefault("system.file", _fake_system_file)


def _lftp_status_file_size(status):
    """Return the actual file size encoded in an lftp pget status file."""
    size_pattern = re.compile(r"^size=(\d+)$")
    pos_pattern = re.compile(r"^\d+\.pos=(\d+)$")
    limit_pattern = re.compile(r"^\d+\.limit=(\d+)$")

    lines = [s.strip() for s in status.splitlines()]
    lines = [ln for ln in lines if ln]
    if not lines:
        return 0

    m = size_pattern.search(lines[0])
    if not m:
        return 0
    total_size = int(m.group(1))
    lines.pop(0)

    empty_size = 0
    while lines:
        if len(lines) < 2:
            return 0
        m_pos = pos_pattern.search(lines[0])
        m_limit = limit_pattern.search(lines[1])
        if not m_pos or not m_limit:
            return 0
        empty_size += int(m_limit.group(1)) - int(m_pos.group(1))
        lines.pop(0)
        lines.pop(0)

    return total_size - empty_size


def _scan_entry(entry):
    """Build a SystemFile from a single os.scandir DirEntry."""
    name = entry.name.encode("utf-8", "surrogateescape").decode("utf-8", "replace")

    if entry.is_dir(follow_symlinks=False):
        children = _scan_path(entry.path)
        size = sum(c.size for c in children)
        st = entry.stat()
        time_created = None
        try:
            time_created = datetime.fromtimestamp(st.st_birthtime)
        except AttributeError:
            pass
        time_modified = datetime.fromtimestamp(st.st_mtime)
        f = SystemFile(name, size, is_dir=True,
                       time_created=time_created, time_modified=time_modified)
        for child in children:
            f.add_child(child)
        return f
    else:
        st = entry.stat()
        size = st.st_size
        # If a partial lftp download status file exists, use it for the real size
        lftp_status_path = entry.path + _LFTP_STATUS_SUFFIX
        if os.path.isfile(lftp_status_path):
            try:
                with open(lftp_status_path, "r") as fh:
                    parsed_size = _lftp_status_file_size(fh.read())
                if parsed_size > 0:
                    size = parsed_size
            except OSError:
                pass
                pass
        time_created = None
        try:
            time_created = datetime.fromtimestamp(st.st_birthtime)
        except AttributeError:
            pass
        time_modified = datetime.fromtimestamp(st.st_mtime)
        return SystemFile(name, size, is_dir=False,
                          time_created=time_created, time_modified=time_modified)


def _scan_path(path):
    """Recursively scan *path* and return a sorted list of SystemFile objects."""
    results = []
    try:
        entries = list(os.scandir(path))
    except OSError:
        return results

    for entry in entries:
        # Always exclude lftp status files (mirrors SystemScanner default behaviour)
        if entry.name.endswith(_LFTP_STATUS_SUFFIX):
            continue
        try:
            f = _scan_entry(entry)
        except (FileNotFoundError, OSError):
            continue
        results.append(f)

    results.sort(key=lambda x: x.name)
    return results


if __name__ == "__main__":
    if sys.hexversion < 0x03050000:
        sys.exit("Python 3.5 or newer is required to run this program.")

    parser = argparse.ArgumentParser(description="File size scanner (Python fallback)")
    parser.add_argument("path", help="Path of the root directory to scan")
    args = parser.parse_args()

    if not os.path.isdir(args.path):
        sys.exit("SystemScannerError: Path does not exist or is not a directory: {}".format(
            args.path
        ))

    try:
        root_files = _scan_path(args.path)
    except Exception as exc:
        sys.exit("SystemScannerError: {}".format(str(exc)))

    sys.stdout.buffer.write(pickle.dumps(root_files))
