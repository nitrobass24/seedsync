# Copyright 2017, Inderpreet Singh, All rights reserved.

import os
import subprocess
import tarfile
import zipfile

from common import AppError


class ExtractError(AppError):
    """
    Indicates an extraction error
    """
    pass


# Magic byte signatures for archive formats
_ARCHIVE_SIGNATURES = [
    (b'\x52\x61\x72\x21\x1A\x07\x01\x00', 'RAR5'),   # RAR5 (8 bytes, check before RAR4)
    (b'\x52\x61\x72\x21\x1A\x07\x00', 'RAR4'),        # RAR4 (7 bytes)
    (b'\x50\x4B\x03\x04', 'ZIP'),                      # ZIP (4 bytes)
    (b'\x37\x7A\xBC\xAF\x27\x1C', '7Z'),              # 7Z (6 bytes)
    (b'\x42\x5A\x68', 'BZIP2'),                        # BZIP2 (3 bytes)
    (b'\x1F\x8B', 'GZIP'),                             # GZIP (2 bytes)
]


class Extract:
    """
    Utility to extract archive files
    """
    @staticmethod
    def verify_archive(archive_path: str):
        """
        Lightweight verification that an archive file is complete and readable.
        Checks magic bytes and tail readability to catch truncated files
        (e.g. incomplete flushes on Docker volume mounts).
        Raises ExtractError on failure. Silently returns for unrecognized formats.
        """
        if not os.path.isfile(archive_path):
            raise ExtractError("Archive verification failed: file not found: {}".format(archive_path))

        file_size = os.path.getsize(archive_path)
        if file_size == 0:
            raise ExtractError("Archive verification failed: empty file: {}".format(archive_path))

        try:
            with open(archive_path, 'rb') as f:
                # Check magic bytes
                header = f.read(8)
                recognized = False
                for signature, name in _ARCHIVE_SIGNATURES:
                    if header[:len(signature)] == signature:
                        recognized = True
                        break

                if not recognized:
                    # Unrecognized format — skip verification
                    return

                # Tail readability check: seek to 1KB before EOF and read
                tail_offset = max(0, file_size - 1024)
                f.seek(tail_offset)
                tail_data = f.read()
                if len(tail_data) == 0:
                    raise ExtractError(
                        "Archive verification failed: truncated or corrupt file: {}".format(archive_path)
                    )
        except ExtractError:
            raise
        except OSError as e:
            raise ExtractError(
                "Archive verification failed: unable to read file: {}: {}".format(archive_path, e)
            )

    @staticmethod
    def _detect_format(archive_path: str) -> str:
        """
        Detect archive format using magic bytes.
        Returns format name ('ZIP', 'RAR4', 'RAR5', '7Z', 'GZIP', 'BZIP2', 'TAR')
        or None if unrecognized.
        """
        try:
            with open(archive_path, 'rb') as f:
                header = f.read(8)
            for signature, name in _ARCHIVE_SIGNATURES:
                if header[:len(signature)] == signature:
                    return name
        except OSError:
            return None
        # Also check if it's a plain tar (no magic bytes in _ARCHIVE_SIGNATURES)
        try:
            with tarfile.open(archive_path) as tf:
                return 'TAR'
        except (tarfile.TarError, OSError):
            pass
        return None

    @staticmethod
    def is_archive(archive_path: str) -> bool:
        if not os.path.isfile(archive_path):
            return False
        return Extract._detect_format(archive_path) is not None

    @staticmethod
    def is_archive_fast(archive_path: str) -> bool:
        """
        Fast version of is_archive that only looks at file extension
        May return false negatives
        :param archive_path:
        :return:
        """
        file_ext = os.path.splitext(os.path.basename(archive_path))[1]
        if file_ext:
            file_ext = file_ext[1:]  # remove the dot
            # noinspection SpellCheckingInspection
            return file_ext in [
                "7z",
                "bz2",
                "gz",
                "lz",
                "rar",
                "tar", "tgz", "tbz2",
                "zip", "zipx"
            ]
        else:
            return False

    @staticmethod
    def _check_member_path(member_name: str, real_out_dir: str):
        """Raise ExtractError if a member path would escape the output directory."""
        resolved = os.path.realpath(os.path.join(real_out_dir, member_name))
        if not resolved.startswith(real_out_dir + os.sep) and resolved != real_out_dir:
            raise ExtractError(
                "Zip-slip detected: member '{}' escapes target directory '{}'".format(
                    member_name, real_out_dir
                )
            )

    @staticmethod
    def _pre_validate_members(archive_path: str, out_dir_path: str):
        """
        Pre-validate archive members for zip and tar formats before extraction.
        Rejects symlinks, hardlinks, and path traversal.
        Returns True if pre-validation was performed, False if format is unsupported
        for pre-validation (fallback to post-extraction check).
        """
        real_out_dir = os.path.realpath(out_dir_path)

        if zipfile.is_zipfile(archive_path):
            with zipfile.ZipFile(archive_path, 'r') as zf:
                for info in zf.infolist():
                    # Reject symlinks (Unix mode S_IFLNK = 0xA000 in upper 16 bits of external_attr)
                    if (info.external_attr >> 16) & 0xF000 == 0xA000:
                        raise ExtractError(
                            "Symlink rejected in archive: '{}'".format(info.filename)
                        )
                    Extract._check_member_path(info.filename, real_out_dir)
            return True

        try:
            with tarfile.open(archive_path) as tf:
                for member in tf.getmembers():
                    if member.issym() or member.islnk():
                        raise ExtractError(
                            "Symlink/hardlink rejected in archive: '{}'".format(member.name)
                        )
                    Extract._check_member_path(member.name, real_out_dir)
            return True
        except tarfile.TarError:
            pass

        return False

    @staticmethod
    def extract_archive(archive_path: str, out_dir_path: str):
        fmt = Extract._detect_format(archive_path) if os.path.isfile(archive_path) else None
        if fmt is None:
            raise ExtractError("Path is not a valid archive: {}".format(archive_path))
        try:
            # Try to create the outdir path
            if not os.path.exists(out_dir_path):
                os.makedirs(out_dir_path)

            # Pre-validate member paths for zip/tar before extraction
            pre_validated = Extract._pre_validate_members(archive_path, out_dir_path)

            if fmt == 'ZIP':
                with zipfile.ZipFile(archive_path, 'r') as zf:
                    zf.extractall(out_dir_path)
            elif fmt in ('TAR', 'GZIP', 'BZIP2'):
                with tarfile.open(archive_path) as tf:
                    tf.extractall(out_dir_path)
            elif fmt in ('RAR4', 'RAR5'):
                result = subprocess.run(
                    ["unrar", "x", "-o+", "-y", archive_path, out_dir_path + os.sep],
                    capture_output=True, text=True
                )
                if result.returncode != 0:
                    raise ExtractError(
                        "unrar failed (exit {}): {}".format(result.returncode, result.stderr.strip())
                    )
            elif fmt == '7Z':
                result = subprocess.run(
                    ["7z", "x", archive_path, "-o" + out_dir_path, "-y"],
                    capture_output=True, text=True
                )
                if result.returncode != 0:
                    raise ExtractError(
                        "7z failed (exit {}): {}".format(result.returncode, result.stderr.strip())
                    )
            else:
                raise ExtractError("Unsupported archive format: {}".format(fmt))
        except ExtractError:
            raise
        except FileNotFoundError as e:
            raise ExtractError(str(e))
        except (zipfile.BadZipFile, tarfile.TarError) as e:
            raise ExtractError(str(e))

        # Post-extraction check as fallback for formats that can't be pre-validated (rar, 7z)
        if not pre_validated:
            real_out_dir = os.path.realpath(out_dir_path)
            for dirpath, dirnames, filenames in os.walk(real_out_dir):
                for name in filenames + dirnames:
                    full_path = os.path.realpath(os.path.join(dirpath, name))
                    if not full_path.startswith(real_out_dir + os.sep) and full_path != real_out_dir:
                        raise ExtractError(
                            "Zip-slip detected: extracted path '{}' escapes target directory '{}'".format(
                                full_path, real_out_dir
                            )
                        )
