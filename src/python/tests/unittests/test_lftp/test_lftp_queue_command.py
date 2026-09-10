import unittest
from unittest.mock import MagicMock, patch


class TestLftpQueueCommand(unittest.TestCase):
    """Unit tests for Lftp.queue() command construction.

    These tests mock __run_command to capture the generated LFTP command
    string without requiring a real LFTP process or SSH connection.
    """

    def _make_lftp(self):
        """Create an Lftp instance with mocked internals."""
        from lftp import Lftp

        with patch.object(Lftp, "__init__", lambda self, **kwargs: None):
            lftp = Lftp.__new__(Lftp)
        # Set the private attributes that queue() uses
        lftp._Lftp__base_remote_dir_path = "/remote/path"
        lftp._Lftp__base_local_dir_path = "/local/path"
        lftp._Lftp__run_command = MagicMock()
        # queue() logs the constructed command; __init__ is stubbed out, so
        # supply a mock logger in its place.
        lftp.logger = MagicMock()
        return lftp

    def test_queue_dir_no_excludes(self):
        lftp = self._make_lftp()
        lftp.queue("mydir", True)
        cmd = lftp._Lftp__run_command.call_args[0][0]
        self.assertIn("mirror", cmd)
        self.assertNotIn("--exclude", cmd)
        self.assertIn("/remote/path/mydir", cmd)

    def test_queue_file_no_excludes(self):
        lftp = self._make_lftp()
        lftp.queue("myfile.mkv", False)
        cmd = lftp._Lftp__run_command.call_args[0][0]
        self.assertIn("pget", cmd)
        self.assertNotIn("--exclude", cmd)

    def test_queue_dir_with_excludes(self):
        lftp = self._make_lftp()
        lftp.queue("mydir", True, exclude_patterns=["*.nfo", "*.txt", "Sample/"])
        cmd = lftp._Lftp__run_command.call_args[0][0]
        self.assertIn("mirror", cmd)
        self.assertIn('--exclude-glob "*.nfo"', cmd)
        self.assertIn('--exclude-glob "*.txt"', cmd)
        self.assertIn('--exclude-glob "Sample/"', cmd)

    def test_queue_file_ignores_excludes(self):
        """Exclude patterns only apply to mirror (directory) downloads, not pget (file)."""
        lftp = self._make_lftp()
        lftp.queue("myfile.mkv", False, exclude_patterns=["*.nfo"])
        cmd = lftp._Lftp__run_command.call_args[0][0]
        self.assertIn("pget", cmd)
        self.assertNotIn("--exclude", cmd)

    def test_queue_dir_empty_excludes(self):
        lftp = self._make_lftp()
        lftp.queue("mydir", True, exclude_patterns=[])
        cmd = lftp._Lftp__run_command.call_args[0][0]
        self.assertNotIn("--exclude", cmd)

    def test_queue_dir_excludes_with_special_chars(self):
        lftp = self._make_lftp()
        lftp.queue("mydir", True, exclude_patterns=["file's name", 'file "quoted"'])
        cmd = lftp._Lftp__run_command.call_args[0][0]
        self.assertIn("--exclude", cmd)
        # Quotes should be escaped
        self.assertIn("\\'", cmd)
        self.assertIn('\\"', cmd)

    def test_queue_dir_excludes_before_source_path(self):
        """Exclude flags should appear between -c and the source path in the mirror command."""
        lftp = self._make_lftp()
        lftp.queue("mydir", True, exclude_patterns=["*.nfo"])
        cmd = lftp._Lftp__run_command.call_args[0][0]
        # --exclude should come after -c and before the remote path
        c_pos = cmd.index("-c")
        exclude_pos = cmd.index("--exclude")
        remote_pos = cmd.index("/remote/path/mydir")
        self.assertLess(c_pos, exclude_pos)
        self.assertLess(exclude_pos, remote_pos)

    def test_queue_nested_file_destination_reproduces_parent_dir(self):
        """A nested pget target must include the source's parent dir, or the
        file lands flat under the pair root instead of mirroring the remote
        nesting (#671)."""
        lftp = self._make_lftp()
        with patch("lftp.lftp.os.makedirs") as mock_makedirs:
            lftp.queue("TopDir/leaf.rar", False)
        cmd = lftp._Lftp__run_command.call_args[0][0]
        self.assertIn('-o "/local/path/TopDir/"', cmd)
        mock_makedirs.assert_called_once_with("/local/path/TopDir", exist_ok=True)

    def test_queue_nested_dir_destination_reproduces_parent_dir(self):
        lftp = self._make_lftp()
        with patch("lftp.lftp.os.makedirs") as mock_makedirs:
            lftp.queue("TopDir/SubDir", True)
        cmd = lftp._Lftp__run_command.call_args[0][0]
        self.assertIn('"/local/path/TopDir/"', cmd)
        mock_makedirs.assert_called_once_with("/local/path/TopDir", exist_ok=True)

    def test_queue_deeply_nested_file_reproduces_full_parent_path(self):
        lftp = self._make_lftp()
        with patch("lftp.lftp.os.makedirs") as mock_makedirs:
            lftp.queue("A/B/C/leaf.rar", False)
        cmd = lftp._Lftp__run_command.call_args[0][0]
        self.assertIn('-o "/local/path/A/B/C/"', cmd)
        mock_makedirs.assert_called_once_with("/local/path/A/B/C", exist_ok=True)

    def test_queue_top_level_file_does_not_create_any_directory(self):
        """Top-level (non-nested) jobs must keep today's behavior exactly -
        no makedirs call, destination stays the bare pair local root."""
        lftp = self._make_lftp()
        with patch("lftp.lftp.os.makedirs") as mock_makedirs:
            lftp.queue("myfile.mkv", False)
        cmd = lftp._Lftp__run_command.call_args[0][0]
        self.assertIn('-o "/local/path/"', cmd)
        mock_makedirs.assert_not_called()

    def test_queue_top_level_dir_does_not_create_any_directory(self):
        lftp = self._make_lftp()
        with patch("lftp.lftp.os.makedirs") as mock_makedirs:
            lftp.queue("mydir", True)
        mock_makedirs.assert_not_called()


class TestLftpSetBaseRemoteDirPath(unittest.TestCase):
    """Lftp.set_base_remote_dir_path() must also forward to the job status
    parser, so it can recover a nested job's name (relative to the remote
    base dir) instead of just its basename - see job_status_parser.py."""

    def test_forwards_to_job_status_parser(self):
        from lftp import Lftp
        from lftp.job_status_parser import LftpJobStatusParser

        with patch.object(Lftp, "__init__", lambda self, **kwargs: None):
            lftp = Lftp.__new__(Lftp)
        lftp._Lftp__job_status_parser = LftpJobStatusParser()

        lftp.set_base_remote_dir_path("/remote/path")

        parser = lftp._Lftp__job_status_parser
        self.assertEqual("TopDir/leaf.rar", parser._extract_name("/remote/path/TopDir/leaf.rar"))
