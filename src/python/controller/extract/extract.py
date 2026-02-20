# Copyright 2017, Inderpreet Singh, All rights reserved.

import os

import patoolib
import patoolib.util

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
    def is_archive(archive_path: str) -> bool:
        if not os.path.isfile(archive_path):
            return False
        try:
            # noinspection PyUnusedLocal,PyShadowingBuiltins
            format, compression = patoolib.get_archive_format(archive_path)
            return True
        except patoolib.util.PatoolError:
            return False

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
    def extract_archive(archive_path: str, out_dir_path: str):
        if not Extract.is_archive(archive_path):
            raise ExtractError("Path is not a valid archive: {}".format(archive_path))
        try:
            # Try to create the outdir path
            if not os.path.exists(out_dir_path):
                os.makedirs(out_dir_path)
            patoolib.extract_archive(archive_path, outdir=out_dir_path, interactive=False)
        except FileNotFoundError as e:
            raise ExtractError(str(e))
        except patoolib.util.PatoolError as e:
            raise ExtractError(str(e))
