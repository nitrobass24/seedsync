# Tests for Extract class: plain gzip and plain bzip2 support
# These test the detection and extraction pipeline for compressed files
# that do NOT contain a tar archive inside (plain .gz and .bz2 files).

import unittest
import gzip
import bz2
import os
import shutil
import tarfile
import tempfile
from unittest.mock import patch, MagicMock

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
        with gzip.open(self.gz_path, 'wb') as f:
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
        self.assertEqual('GZIP', fmt)

    def test_extract_routes_gzip_to_two_pass(self):
        """Verify that GZIP format triggers _extract_compressed_archive."""
        with patch.object(Extract, '_extract_compressed_archive') as mock_two_pass, \
             patch.object(Extract, '_run_7z') as mock_run_7z:
            Extract.extract_archive(self.gz_path, self.out_dir)
            mock_two_pass.assert_called_once_with(self.gz_path, self.out_dir)
            mock_run_7z.assert_not_called()

    def test_extract_plain_gzip_moves_decompressed_file(self):
        """Simulate 7z decompressing a plain .gz to a non-tar file, verify it lands in out_dir."""
        decompressed_name = "data"

        def fake_run_7z(archive_path, out_dir_path):
            # Simulate 7z extracting a .gz: produces the inner file in out_dir_path
            inner = os.path.join(out_dir_path, decompressed_name)
            with open(inner, 'wb') as f:
                f.write(self.file_content)

        with patch.object(Extract, '_run_7z', side_effect=fake_run_7z):
            Extract.extract_archive(self.gz_path, self.out_dir)

        # The decompressed file should be in the output directory
        result_path = os.path.join(self.out_dir, decompressed_name)
        self.assertTrue(os.path.isfile(result_path))
        with open(result_path, 'rb') as f:
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
        with bz2.open(self.bz2_path, 'wb') as f:
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
        self.assertEqual('BZIP2', fmt)

    def test_extract_routes_bzip2_to_two_pass(self):
        """Verify that BZIP2 format triggers _extract_compressed_archive."""
        with patch.object(Extract, '_extract_compressed_archive') as mock_two_pass, \
             patch.object(Extract, '_run_7z') as mock_run_7z:
            Extract.extract_archive(self.bz2_path, self.out_dir)
            mock_two_pass.assert_called_once_with(self.bz2_path, self.out_dir)
            mock_run_7z.assert_not_called()

    def test_extract_plain_bzip2_moves_decompressed_file(self):
        """Simulate 7z decompressing a plain .bz2 to a non-tar file, verify it lands in out_dir."""
        decompressed_name = "data"

        def fake_run_7z(archive_path, out_dir_path):
            inner = os.path.join(out_dir_path, decompressed_name)
            with open(inner, 'wb') as f:
                f.write(self.file_content)

        with patch.object(Extract, '_run_7z', side_effect=fake_run_7z):
            Extract.extract_archive(self.bz2_path, self.out_dir)

        result_path = os.path.join(self.out_dir, decompressed_name)
        self.assertTrue(os.path.isfile(result_path))
        with open(result_path, 'rb') as f:
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
        with open(self.inner_file, 'wb') as f:
            f.write(self.file_content)

        self.tar_gz_path = os.path.join(self.temp_dir, "archive.tar.gz")
        with tarfile.open(self.tar_gz_path, 'w:gz') as tar:
            tar.add(self.inner_file, arcname="inner_file.txt")

        # Also create a plain .gz
        self.plain_content = b"plain content\n" * 100
        self.plain_gz_path = os.path.join(self.temp_dir, "plain.gz")
        with gzip.open(self.plain_gz_path, 'wb') as f:
            f.write(self.plain_content)

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_tar_gz_detected_as_gzip(self):
        """A .tar.gz file has GZIP magic bytes and routes through two-pass."""
        fmt = Extract._detect_format(self.tar_gz_path)
        self.assertEqual('GZIP', fmt)

    def test_two_pass_extracts_tar_contents_when_inner_is_tar(self):
        """When 7z decompresses to a tar, the second pass extracts the tar."""
        call_count = [0]

        def fake_run_7z(archive_path, out_dir_path):
            call_count[0] += 1
            if call_count[0] == 1:
                # First pass: decompress .tar.gz -> produce a .tar in temp dir
                tar_inner = os.path.join(out_dir_path, "archive.tar")
                with tarfile.open(tar_inner, 'w') as tar:
                    tar.add(self.inner_file, arcname="inner_file.txt")
            else:
                # Second pass: extract the tar contents
                with tarfile.open(archive_path) as tar:
                    tar.extractall(out_dir_path)

        with patch.object(Extract, '_run_7z', side_effect=fake_run_7z):
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
            with open(inner, 'wb') as f:
                f.write(self.plain_content)

        with patch.object(Extract, '_run_7z', side_effect=fake_run_7z):
            Extract.extract_archive(self.plain_gz_path, self.out_dir)

        # Should only call 7z once (no second pass needed)
        self.assertEqual(1, call_count[0])
        result_path = os.path.join(self.out_dir, "plain")
        self.assertTrue(os.path.isfile(result_path))
        with open(result_path, 'rb') as f:
            self.assertEqual(self.plain_content, f.read())
