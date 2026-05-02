# Copyright 2017, Inderpreet Singh, All rights reserved.

import logging
import sys
import unittest
from unittest.mock import patch

from controller.delete.delete_process import DeleteLocalProcess, DeleteRemoteProcess


class TestDeleteLocalProcess(unittest.TestCase):
    """Tests for DeleteLocalProcess.run_once()."""

    def setUp(self):
        logger = logging.getLogger()
        handler = logging.StreamHandler(sys.stdout)
        logger.addHandler(handler)
        self.addCleanup(logger.removeHandler, handler)
        logger.setLevel(logging.DEBUG)

    @patch("controller.delete.delete_process.shutil.rmtree")
    @patch("controller.delete.delete_process.os.path.isfile", return_value=False)
    @patch("controller.delete.delete_process.os.path.exists", return_value=True)
    @patch("controller.delete.delete_process.os.path.realpath")
    def test_directory_uses_rmtree(self, mock_realpath, mock_exists, mock_isfile, mock_rmtree):
        """Directory deletion uses shutil.rmtree."""
        mock_realpath.side_effect = lambda p: p
        proc = DeleteLocalProcess("/base", "mydir")
        proc.run_once()
        mock_rmtree.assert_called_once_with("/base/mydir", ignore_errors=True)

    @patch("controller.delete.delete_process.os.remove")
    @patch("controller.delete.delete_process.os.path.isfile", return_value=True)
    @patch("controller.delete.delete_process.os.path.exists", return_value=True)
    @patch("controller.delete.delete_process.os.path.realpath")
    def test_regular_file_uses_os_remove(self, mock_realpath, mock_exists, mock_isfile, mock_remove):
        """Regular file deletion uses os.remove."""
        mock_realpath.side_effect = lambda p: p
        proc = DeleteLocalProcess("/base", "myfile.txt")
        proc.run_once()
        mock_remove.assert_called_once_with("/base/myfile.txt")

    @patch("controller.delete.delete_process.os.path.realpath")
    def test_symlink_escaping_base_blocked(self, mock_realpath):
        """Symlink escaping base directory is blocked and logged."""
        mock_realpath.side_effect = lambda p: "/etc/passwd" if "evil" in p else p
        proc = DeleteLocalProcess("/base", "evil_symlink")

        with self.assertLogs(level="ERROR") as log_ctx:
            proc.run_once()

        self.assertTrue(any("Path traversal blocked" in msg for msg in log_ctx.output))

    @patch("controller.delete.delete_process.os.path.realpath")
    def test_path_traversal_blocked(self, mock_realpath):
        """../../etc/passwd style paths are blocked."""
        mock_realpath.side_effect = lambda p: "/etc/passwd" if "etc" in p else "/base"
        proc = DeleteLocalProcess("/base", "../../etc/passwd")

        with self.assertLogs(level="ERROR") as log_ctx:
            proc.run_once()

        self.assertTrue(any("Path traversal blocked" in msg for msg in log_ctx.output))

    @patch("controller.delete.delete_process.os.path.exists", return_value=False)
    @patch("controller.delete.delete_process.os.path.realpath")
    def test_nonexistent_file_logs_error(self, mock_realpath, mock_exists):
        """Non-existing file logs error, no crash."""
        mock_realpath.side_effect = lambda p: p
        proc = DeleteLocalProcess("/base", "gone.txt")

        with self.assertLogs(level="ERROR") as log_ctx:
            proc.run_once()

        self.assertTrue(any("non-existing" in msg for msg in log_ctx.output))


class TestDeleteRemoteProcess(unittest.TestCase):
    """Tests for DeleteRemoteProcess.run_once()."""

    def setUp(self):
        logger = logging.getLogger()
        handler = logging.StreamHandler(sys.stdout)
        logger.addHandler(handler)
        self.addCleanup(logger.removeHandler, handler)
        logger.setLevel(logging.DEBUG)

    @patch("controller.delete.delete_process.Sshcp")
    def test_constructs_correct_ssh_command(self, mock_sshcp_cls):
        """Remote delete constructs correct SSH rm -rf command."""
        mock_ssh = mock_sshcp_cls.return_value
        mock_ssh.shell.return_value = b""

        proc = DeleteRemoteProcess(
            remote_address="host",
            remote_username="user",
            remote_password="pass",
            remote_port=22,
            remote_path="/remote",
            file_name="myfile.txt",
        )
        proc.run_once()

        mock_ssh.shell.assert_called_once()
        cmd = mock_ssh.shell.call_args[0][0]
        self.assertIn("rm -rf", cmd)
        self.assertIn("myfile.txt", cmd)

    @patch("controller.delete.delete_process.Sshcp")
    def test_remote_path_starting_with_dotdot_blocked(self, mock_sshcp_cls):
        """Remote paths starting with .. are blocked."""
        mock_ssh = mock_sshcp_cls.return_value

        proc = DeleteRemoteProcess(
            remote_address="host",
            remote_username="user",
            remote_password="pass",
            remote_port=22,
            remote_path="/remote",
            file_name="../etc/passwd",
        )

        with self.assertLogs(level="ERROR") as log_ctx:
            proc.run_once()

        self.assertTrue(any("Path traversal blocked" in msg for msg in log_ctx.output))
        mock_ssh.shell.assert_not_called()

    @patch("controller.delete.delete_process.Sshcp")
    def test_remote_absolute_path_blocked(self, mock_sshcp_cls):
        """Remote file names with absolute paths are blocked."""
        mock_ssh = mock_sshcp_cls.return_value

        proc = DeleteRemoteProcess(
            remote_address="host",
            remote_username="user",
            remote_password="pass",
            remote_port=22,
            remote_path="/remote",
            file_name="/etc/passwd",
        )

        with self.assertLogs(level="ERROR") as log_ctx:
            proc.run_once()

        self.assertTrue(any("Path traversal blocked" in msg for msg in log_ctx.output))
        mock_ssh.shell.assert_not_called()

    @patch("controller.delete.delete_process.Sshcp")
    def test_tilde_path_uses_double_escape(self, mock_sshcp_cls):
        """Paths starting with ~ use double-quote escaping."""
        mock_ssh = mock_sshcp_cls.return_value
        mock_ssh.shell.return_value = b""

        proc = DeleteRemoteProcess(
            remote_address="host",
            remote_username="user",
            remote_password="pass",
            remote_port=22,
            remote_path="~/downloads",
            file_name="myfile.txt",
        )
        proc.run_once()

        cmd = mock_ssh.shell.call_args[0][0]
        # Tilde paths use double-quote escaping (escape_remote_path_double)
        self.assertIn('"', cmd)
