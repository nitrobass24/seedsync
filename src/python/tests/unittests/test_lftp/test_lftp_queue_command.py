import unittest
from unittest.mock import patch, MagicMock


class TestLftpQueueCommand(unittest.TestCase):
    """Unit tests for Lftp.queue() command construction.

    These tests mock __run_command to capture the generated LFTP command
    string without requiring a real LFTP process or SSH connection.
    """

    def _make_lftp(self):
        """Create an Lftp instance with mocked internals."""
        from lftp import Lftp

        with patch.object(Lftp, '__init__', lambda self, **kwargs: None):
            lftp = Lftp.__new__(Lftp)
        # Set the private attributes that queue() uses
        lftp._Lftp__base_remote_dir_path = "/remote/path"
        lftp._Lftp__base_local_dir_path = "/local/path"
        lftp._Lftp__run_command = MagicMock()
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
        self.assertIn('--exclude "*.nfo"', cmd)
        self.assertIn('--exclude "*.txt"', cmd)
        self.assertIn('--exclude "Sample/"', cmd)

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
