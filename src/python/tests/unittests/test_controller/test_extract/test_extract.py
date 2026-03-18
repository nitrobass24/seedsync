# Tests for Extract class: plain gzip and plain bzip2 support
# These test the detection and extraction pipeline for compressed files
# that do NOT contain a tar archive inside (plain .gz and .bz2 files).

import bz2
import gzip
import os
import shutil
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from controller.extract import Extract, ExtractError


class TestExtractPlainGzip(unittest.TestCase):
    """Tests for plain .gz files (not .tar.gz)."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="test_extract_plain_gz_")
        self.out_dir = os.path.join(self.temp_dir, "output")
        os.makedirs(self.out_dir)

        # Create a plain gzip file (text content, not a tar)
        self.file_content = b"Hello, this is plain gzip content!\n" * 100
        self.gz_path = os.path.join(self.temp_dir, "data.gz")
        with gzip.open(self.gz_path, "wb") as f:
            f.write(self.file_content)

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_is_archive_fast_gz(self):
        self.assertTrue(Extract.is_archive_fast("file.gz"))
        self.assertTrue(Extract.is_archive_fast("/path/to/file.gz"))

    def test_is_archive_detects_plain_gzip(self):
        self.assertTrue(Extract.is_archive(self.gz_path))

    def test_detect_format_returns_gzip(self):
        fmt = Extract._detect_format(self.gz_path)
        self.assertEqual("GZIP", fmt)

    def test_extract_routes_gzip_to_two_pass(self):
        """Verify that GZIP format triggers _extract_compressed_archive."""
        with (
            patch.object(Extract, "_extract_compressed_archive") as mock_two_pass,
            patch.object(Extract, "_run_7z") as mock_run_7z,
        ):
            Extract.extract_archive(self.gz_path, self.out_dir)
            mock_two_pass.assert_called_once_with(self.gz_path, self.out_dir)
            mock_run_7z.assert_not_called()

    def test_extract_plain_gzip_moves_decompressed_file(self):
        """Simulate 7z decompressing a plain .gz to a non-tar file, verify it lands in out_dir."""
        decompressed_name = "data"

        def fake_run_7z(archive_path, out_dir_path):
            # Simulate 7z extracting a .gz: produces the inner file in out_dir_path
            inner = os.path.join(out_dir_path, decompressed_name)
            with open(inner, "wb") as f:
                f.write(self.file_content)

        with patch.object(Extract, "_run_7z", side_effect=fake_run_7z):
            Extract.extract_archive(self.gz_path, self.out_dir)

        # The decompressed file should be in the output directory
        result_path = os.path.join(self.out_dir, decompressed_name)
        self.assertTrue(os.path.isfile(result_path))
        with open(result_path, "rb") as f:
            self.assertEqual(self.file_content, f.read())


class TestExtractPlainBzip2(unittest.TestCase):
    """Tests for plain .bz2 files (not .tar.bz2)."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="test_extract_plain_bz2_")
        self.out_dir = os.path.join(self.temp_dir, "output")
        os.makedirs(self.out_dir)

        # Create a plain bzip2 file (text content, not a tar)
        self.file_content = b"Hello, this is plain bzip2 content!\n" * 100
        self.bz2_path = os.path.join(self.temp_dir, "data.bz2")
        with bz2.open(self.bz2_path, "wb") as f:
            f.write(self.file_content)

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_is_archive_fast_bz2(self):
        self.assertTrue(Extract.is_archive_fast("file.bz2"))
        self.assertTrue(Extract.is_archive_fast("/path/to/file.bz2"))

    def test_is_archive_detects_plain_bzip2(self):
        self.assertTrue(Extract.is_archive(self.bz2_path))

    def test_detect_format_returns_bzip2(self):
        fmt = Extract._detect_format(self.bz2_path)
        self.assertEqual("BZIP2", fmt)

    def test_extract_routes_bzip2_to_two_pass(self):
        """Verify that BZIP2 format triggers _extract_compressed_archive."""
        with (
            patch.object(Extract, "_extract_compressed_archive") as mock_two_pass,
            patch.object(Extract, "_run_7z") as mock_run_7z,
        ):
            Extract.extract_archive(self.bz2_path, self.out_dir)
            mock_two_pass.assert_called_once_with(self.bz2_path, self.out_dir)
            mock_run_7z.assert_not_called()

    def test_extract_plain_bzip2_moves_decompressed_file(self):
        """Simulate 7z decompressing a plain .bz2 to a non-tar file, verify it lands in out_dir."""
        decompressed_name = "data"

        def fake_run_7z(archive_path, out_dir_path):
            inner = os.path.join(out_dir_path, decompressed_name)
            with open(inner, "wb") as f:
                f.write(self.file_content)

        with patch.object(Extract, "_run_7z", side_effect=fake_run_7z):
            Extract.extract_archive(self.bz2_path, self.out_dir)

        result_path = os.path.join(self.out_dir, decompressed_name)
        self.assertTrue(os.path.isfile(result_path))
        with open(result_path, "rb") as f:
            self.assertEqual(self.file_content, f.read())


class TestExtractTwoPassTarVsPlain(unittest.TestCase):
    """Tests verifying the two-pass logic distinguishes tar-containing from plain compressed."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="test_extract_twopass_")
        self.out_dir = os.path.join(self.temp_dir, "output")
        os.makedirs(self.out_dir)

        # Create a .tar.gz (compressed tar) for comparison
        self.file_content = b"tar content file data\n" * 100
        self.inner_file = os.path.join(self.temp_dir, "inner_file.txt")
        with open(self.inner_file, "wb") as f:
            f.write(self.file_content)

        self.tar_gz_path = os.path.join(self.temp_dir, "archive.tar.gz")
        with tarfile.open(self.tar_gz_path, "w:gz") as tar:
            tar.add(self.inner_file, arcname="inner_file.txt")

        # Also create a plain .gz
        self.plain_content = b"plain content\n" * 100
        self.plain_gz_path = os.path.join(self.temp_dir, "plain.gz")
        with gzip.open(self.plain_gz_path, "wb") as f:
            f.write(self.plain_content)

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_tar_gz_detected_as_gzip(self):
        """A .tar.gz file has GZIP magic bytes and routes through two-pass."""
        fmt = Extract._detect_format(self.tar_gz_path)
        self.assertEqual("GZIP", fmt)

    def test_two_pass_extracts_tar_contents_when_inner_is_tar(self):
        """When 7z decompresses to a tar, the second pass extracts the tar."""
        call_count = [0]

        def fake_run_7z(archive_path, out_dir_path):
            call_count[0] += 1
            if call_count[0] == 1:
                # First pass: decompress .tar.gz -> produce a .tar in temp dir
                tar_inner = os.path.join(out_dir_path, "archive.tar")
                with tarfile.open(tar_inner, "w") as tar:
                    tar.add(self.inner_file, arcname="inner_file.txt")
            else:
                # Second pass: simulate 7z extracting the tar contents
                with open(os.path.join(out_dir_path, "inner_file.txt"), "wb") as f:
                    f.write(self.file_content)

        with patch.object(Extract, "_run_7z", side_effect=fake_run_7z):
            Extract.extract_archive(self.tar_gz_path, self.out_dir)

        self.assertEqual(2, call_count[0])
        result_path = os.path.join(self.out_dir, "inner_file.txt")
        self.assertTrue(os.path.isfile(result_path))

    def test_two_pass_moves_file_when_inner_is_not_tar(self):
        """When 7z decompresses to a non-tar file, it moves it to the output dir."""
        call_count = [0]

        def fake_run_7z(archive_path, out_dir_path):
            call_count[0] += 1
            # Produce a plain text file (not a tar)
            inner = os.path.join(out_dir_path, "plain")
            with open(inner, "wb") as f:
                f.write(self.plain_content)

        with patch.object(Extract, "_run_7z", side_effect=fake_run_7z):
            Extract.extract_archive(self.plain_gz_path, self.out_dir)

        # Should only call 7z once (no second pass needed)
        self.assertEqual(1, call_count[0])
        result_path = os.path.join(self.out_dir, "plain")
        self.assertTrue(os.path.isfile(result_path))
        with open(result_path, "rb") as f:
            self.assertEqual(self.plain_content, f.read())

    def test_tar_bz2_detected_as_bzip2(self):
        """A .tar.bz2 file has BZIP2 magic bytes and routes through two-pass."""
        tar_bz2_path = os.path.join(self.temp_dir, "archive.tar.bz2")
        with tarfile.open(tar_bz2_path, "w:bz2") as tar:
            tar.add(self.inner_file, arcname="inner_file.txt")
        fmt = Extract._detect_format(tar_bz2_path)
        self.assertEqual("BZIP2", fmt)


class TestExtractErrorCases(unittest.TestCase):
    """Tests for error handling in extraction."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="test_extract_errors_")
        self.out_dir = os.path.join(self.temp_dir, "output")
        os.makedirs(self.out_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_extract_nonexistent_file_raises_error(self):
        fake_path = os.path.join(self.temp_dir, "nonexistent.gz")
        with self.assertRaises(ExtractError):
            Extract.extract_archive(fake_path, self.out_dir)

    def test_detect_format_returns_none_for_unknown(self):
        unknown_path = os.path.join(self.temp_dir, "unknown.dat")
        with open(unknown_path, "wb") as f:
            f.write(b"this is not an archive at all")
        fmt = Extract._detect_format(unknown_path)
        self.assertIsNone(fmt)

    def test_is_archive_returns_false_for_nonexistent(self):
        self.assertFalse(Extract.is_archive(os.path.join(self.temp_dir, "no.gz")))

    def test_is_archive_fast_returns_false_for_non_archive_ext(self):
        self.assertFalse(Extract.is_archive_fast("file.txt"))
        self.assertFalse(Extract.is_archive_fast("file.jpg"))
        self.assertFalse(Extract.is_archive_fast("noext"))

    def test_extract_corrupt_gzip_raises_error(self):
        """A file with gzip magic bytes but corrupt content should raise ExtractError."""
        corrupt_path = os.path.join(self.temp_dir, "corrupt.gz")
        with open(corrupt_path, "wb") as f:
            # Write gzip magic bytes followed by garbage
            f.write(b"\x1f\x8b" + b"\x00" * 50)

        # _detect_format should still detect it as GZIP (magic bytes match)
        fmt = Extract._detect_format(corrupt_path)
        self.assertEqual("GZIP", fmt)

        # extract_archive should raise because 7z will fail on corrupt data
        with patch.object(Extract, "_run_7z", side_effect=ExtractError("7z failed")):
            with self.assertRaises(ExtractError):
                Extract.extract_archive(corrupt_path, self.out_dir)

    def test_extract_corrupt_bzip2_raises_error(self):
        """A file with bzip2 magic bytes but corrupt content should raise ExtractError."""
        corrupt_path = os.path.join(self.temp_dir, "corrupt.bz2")
        with open(corrupt_path, "wb") as f:
            # Write bzip2 magic bytes followed by garbage
            f.write(b"\x42\x5a\x68" + b"\x00" * 50)

        fmt = Extract._detect_format(corrupt_path)
        self.assertEqual("BZIP2", fmt)

        with patch.object(Extract, "_run_7z", side_effect=ExtractError("7z failed")):
            with self.assertRaises(ExtractError):
                Extract.extract_archive(corrupt_path, self.out_dir)

    def test_two_pass_with_multiple_decompressed_files(self):
        """When 7z produces multiple files, all should be moved to output dir."""
        gz_path = os.path.join(self.temp_dir, "multi.gz")
        with gzip.open(gz_path, "wb") as f:
            f.write(b"content")

        def fake_run_7z(archive_path, out_dir_path):
            # Simulate 7z producing multiple files
            for name in ["file_a.txt", "file_b.txt"]:
                with open(os.path.join(out_dir_path, name), "wb") as f:
                    f.write(b"data for " + name.encode())

        with patch.object(Extract, "_run_7z", side_effect=fake_run_7z):
            Extract.extract_archive(gz_path, self.out_dir)

        self.assertTrue(os.path.isfile(os.path.join(self.out_dir, "file_a.txt")))
        self.assertTrue(os.path.isfile(os.path.join(self.out_dir, "file_b.txt")))
