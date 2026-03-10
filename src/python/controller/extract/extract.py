# Copyright 2017, Inderpreet Singh, All rights reserved.

import os
import subprocess
import tarfile

from common import AppError


class ExtractError(AppError):
    """
    Indicates an extraction error
    """
    pass


# Magic byte signatures for archive formats.
# All formats are extracted via 7z; signatures are used for fast detection only.
_ARCHIVE_SIGNATURES = [
    (b'\x52\x61\x72\x21\x1A\x07\x01\x00', 'RAR5'),   # RAR5 (8 bytes, check before RAR4)
    (b'\x52\x61\x72\x21\x1A\x07\x00', 'RAR4'),        # RAR4 (7 bytes)
    (b'\x50\x4B\x03\x04', 'ZIP'),                      # ZIP (4 bytes; also covers .zipx variant)
    (b'\x37\x7A\xBC\xAF\x27\x1C', '7Z'),              # 7Z (6 bytes)
    (b'\xFD\x37\x7A\x58\x5A\x00', 'XZ'),              # XZ (6 bytes)
    (b'\x42\x5A\x68', 'BZIP2'),                        # BZIP2 (3 bytes)
    (b'\x1F\x8B', 'GZIP'),                             # GZIP (2 bytes)
    (b'\x4C\x5A\x49\x50', 'LZIP'),                     # LZIP (4 bytes, "LZIP")
]


class Extract:
    """
    Utility to extract archive files.
    All extraction is performed via 7z (built from source with RAR codec).
    """

    _7Z_TIMEOUT_SECS = 3600

    @staticmethod
    def _format_7z_error(result: subprocess.CompletedProcess, prefix: str) -> str:
        """Format a 7z failure message with both stderr and stdout details."""
        details = result.stderr.strip()
        if result.stdout.strip():
            stdout_lines = result.stdout.strip().splitlines()
            stdout_tail = "\n".join(stdout_lines[-20:])
            details = "{}\n--- stdout (last 20 lines) ---\n{}".format(details, stdout_tail)
        return "{} (exit {}): {}".format(prefix, result.returncode, details)

    @staticmethod
    def verify_archive(archive_path: str):
        """
        Verify archive integrity using 7z test command.
        Raises ExtractError on failure.
        """
        if not os.path.isfile(archive_path):
            raise ExtractError("Archive verification failed: file not found: {}".format(archive_path))

        file_size = os.path.getsize(archive_path)
        if file_size == 0:
            raise ExtractError("Archive verification failed: empty file: {}".format(archive_path))

        try:
            result = subprocess.run(
                ["7z", "t", "--", archive_path],
                capture_output=True, text=True, timeout=Extract._7Z_TIMEOUT_SECS
            )
        except subprocess.TimeoutExpired:
            raise ExtractError(
                "Archive verification timed out after {}s: {}".format(Extract._7Z_TIMEOUT_SECS, archive_path)
            )
        except FileNotFoundError:
            raise ExtractError("7z binary not found; cannot verify archive")

        if result.returncode != 0:
            raise ExtractError(Extract._format_7z_error(result, "Archive verification failed"))

    @staticmethod
    def _detect_format(archive_path: str) -> str:
        """
        Detect archive format using magic bytes.
        Returns format name or None if unrecognized.
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
            with tarfile.open(archive_path):
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
        Fast version of is_archive that only looks at file extension.
        May return false negatives.
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
                "xz",
                "rar",
                "tar", "tgz", "tbz2",
                "zip", "zipx"
            ]
        else:
            return False

    @staticmethod
    def extract_archive(archive_path: str, out_dir_path: str):
        """
        Extract an archive using 7z.
        Supports all formats handled by 7z: zip, rar, 7z, tar, gz, bz2, xz, and more.
        """
        if not os.path.isfile(archive_path):
            raise ExtractError("Path is not a valid archive: {}".format(archive_path))

        fmt = Extract._detect_format(archive_path)
        if fmt is None:
            raise ExtractError("Path is not a valid archive: {}".format(archive_path))

        try:
            if not os.path.exists(out_dir_path):
                os.makedirs(out_dir_path)

            # For .tar.gz, .tar.bz2, .tar.xz — 7z extracts the outer compression
            # to get the .tar, then we need a second pass to extract the tar contents.
            # Detect this by checking if the inner content is a tar.
            if fmt in ('GZIP', 'BZIP2', 'XZ', 'LZIP'):
                # Two-pass extraction: decompress → extract tar (if applicable)
                Extract._extract_compressed_archive(archive_path, out_dir_path)
            else:
                Extract._run_7z(archive_path, out_dir_path)

        except ExtractError:
            raise
        except FileNotFoundError as e:
            raise ExtractError(str(e)) from e

        # Post-extraction path validation: ensure nothing escaped the output directory
        real_out_dir = os.path.realpath(out_dir_path)
        for dirpath, dirnames, filenames in os.walk(real_out_dir):
            for name in filenames + dirnames:
                full_path = os.path.realpath(os.path.join(dirpath, name))
                if os.path.islink(os.path.join(dirpath, name)):
                    os.remove(os.path.join(dirpath, name))
                    continue
                try:
                    common = os.path.commonpath([real_out_dir, full_path])
                except ValueError:
                    common = None
                if common != real_out_dir:
                    raise ExtractError(
                        "Zip-slip detected: extracted path '{}' escapes target directory '{}'".format(
                            full_path, real_out_dir
                        )
                    )

    @staticmethod
    def _run_7z(archive_path: str, out_dir_path: str):
        """Run 7z extraction with standard options."""
        try:
            result = subprocess.run(
                ["7z", "x", "-o" + out_dir_path, "-y", "-aoa", "--", archive_path],
                capture_output=True, text=True, timeout=Extract._7Z_TIMEOUT_SECS
            )
        except subprocess.TimeoutExpired:
            raise ExtractError(
                "7z timed out after {}s: {}".format(Extract._7Z_TIMEOUT_SECS, archive_path)
            )
        except FileNotFoundError:
            raise ExtractError("7z binary not found; cannot extract archive")

        if result.returncode != 0:
            raise ExtractError(Extract._format_7z_error(result, "7z failed"))

    @staticmethod
    def _extract_compressed_archive(archive_path: str, out_dir_path: str):
        """
        Handle .tar.gz, .tar.bz2, .tar.xz, .tar.lz and plain .gz, .bz2, .xz, .lz files.
        First pass decompresses to a temp location; if the result is a tar,
        second pass extracts the tar. Otherwise moves the decompressed file.
        """
        import tempfile
        import shutil

        # Decompress to a temp directory first
        with tempfile.TemporaryDirectory(prefix="seedsync_extract_", dir=out_dir_path) as tmp_dir:
            Extract._run_7z(archive_path, tmp_dir)

            # Check what we got
            extracted = os.listdir(tmp_dir)
            if len(extracted) == 1:
                inner_path = os.path.join(tmp_dir, extracted[0])
                # If the inner file is a tar, extract it
                if os.path.isfile(inner_path) and Extract._detect_format(inner_path) == 'TAR':
                    Extract._run_7z(inner_path, out_dir_path)
                    return

            # Not a tar inside — move everything to the output directory
            for item in extracted:
                src = os.path.join(tmp_dir, item)
                dst = os.path.join(out_dir_path, item)
                if os.path.exists(dst):
                    if os.path.isdir(dst):
                        shutil.rmtree(dst)
                    else:
                        os.remove(dst)
                shutil.move(src, dst)
