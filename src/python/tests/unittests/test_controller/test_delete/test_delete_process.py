# Copyright 2017, Inderpreet Singh, All rights reserved.

import logging
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

from controller.delete.delete_process import CleanupLocalProcess, DeleteLocalProcess, DeleteRemoteProcess


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


class TestCleanupLocalProcess(unittest.TestCase):
    """Tests for CleanupLocalProcess.run_once().

    These run against a real temp directory rather than mocking os.path, so that
    symlink and containment behaviour is exercised as the filesystem actually
    resolves it (#663 review).
    """

    def setUp(self):
        logger = logging.getLogger()
        handler = logging.StreamHandler(sys.stdout)
        logger.addHandler(handler)
        self.addCleanup(logger.removeHandler, handler)
        logger.setLevel(logging.DEBUG)

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        # base/ holds the folder being cleaned; outside/ is a sibling that must
        # never be touched, standing in for anything beyond the local path.
        self.base = os.path.join(tmp.name, "base")
        self.outside = os.path.join(tmp.name, "outside")
        self.folder = os.path.join(self.base, "myfolder")
        os.makedirs(self.folder)
        os.makedirs(self.outside)

    def _write(self, path: str, content: str = "x") -> str:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(content)
        return path

    def _run(self, relative_paths: list[str]) -> None:
        CleanupLocalProcess(self.base, "myfolder", relative_paths).run_once()

    def test_deletes_local_only_file_and_directory(self):
        stray_file = self._write(os.path.join(self.folder, "stray.txt"))
        stray_dir = os.path.join(self.folder, "stray_dir")
        self._write(os.path.join(stray_dir, "nested.txt"))
        mirrored = self._write(os.path.join(self.folder, "keep.mkv"))

        self._run(["stray.txt", "stray_dir"])

        self.assertFalse(os.path.exists(stray_file))
        self.assertFalse(os.path.exists(stray_dir))
        self.assertTrue(os.path.exists(mirrored))

    def test_nested_relative_path_deleted_without_removing_parent(self):
        nested = self._write(os.path.join(self.folder, "mirrored", "stray.txt"))

        self._run([os.path.join("mirrored", "stray.txt")])

        self.assertFalse(os.path.exists(nested))
        self.assertTrue(os.path.isdir(os.path.join(self.folder, "mirrored")))

    def test_symlink_to_directory_is_unlinked_not_followed(self):
        target_dir = os.path.join(self.folder, "realdir")
        target_file = self._write(os.path.join(target_dir, "keep.txt"))
        link = os.path.join(self.folder, "link_to_dir")
        os.symlink(target_dir, link)

        self._run(["link_to_dir"])

        self.assertFalse(os.path.lexists(link))
        self.assertTrue(os.path.isdir(target_dir), "symlink target must survive")
        self.assertTrue(os.path.exists(target_file))

    def test_symlink_pointing_outside_base_is_unlinked(self):
        """A local-only symlink out of the folder must be removed, not flagged as traversal.

        Resolving the final component made realpath land outside the base, so the
        link was reported as a path-traversal failure and never deleted (#663 review).
        """
        external_file = self._write(os.path.join(self.outside, "extdir", "payload.txt"))
        link = os.path.join(self.folder, "link_out")
        os.symlink(os.path.join(self.outside, "extdir"), link)

        self._run(["link_out"])

        self.assertFalse(os.path.lexists(link))
        self.assertTrue(os.path.exists(external_file), "symlink target must survive")

    def test_dangling_symlink_is_removed(self):
        link = os.path.join(self.folder, "dangling")
        os.symlink(os.path.join(self.folder, "missing_target"), link)

        self._run(["dangling"])

        self.assertFalse(os.path.lexists(link))

    def test_traversal_relative_path_blocked_and_target_untouched(self):
        victim = self._write(os.path.join(self.outside, "outside.txt"))

        with self.assertLogs(level="ERROR") as log_ctx, self.assertRaises(RuntimeError):
            self._run([os.path.join("..", "..", "outside", "outside.txt")])

        self.assertTrue(any("Path traversal blocked" in msg for msg in log_ctx.output))
        self.assertTrue(os.path.exists(victim))

    def test_symlinked_ancestor_cannot_be_used_to_escape(self):
        victim = self._write(os.path.join(self.outside, "extdir", "victim.txt"))
        os.symlink(os.path.join(self.outside, "extdir"), os.path.join(self.folder, "link_dir"))

        with self.assertRaises(RuntimeError):
            self._run([os.path.join("link_dir", "victim.txt")])

        self.assertTrue(os.path.exists(victim))

    def test_dotdot_basename_blocked(self):
        with self.assertRaises(RuntimeError):
            self._run([".."])

        self.assertTrue(os.path.isdir(self.base))
        self.assertTrue(os.path.isdir(self.folder))

    def test_nonexistent_relative_path_logs_error_and_raises(self):
        with self.assertLogs(level="ERROR") as log_ctx, self.assertRaises(RuntimeError):
            self._run(["gone.txt"])

        self.assertTrue(any("non-existing" in msg for msg in log_ctx.output))

    def test_one_failure_does_not_abort_remaining_paths(self):
        """A permission error on one path must not skip the rest of the batch (#663 review).

        os.unlink is faulted for a single path rather than relying on chmod, which
        does not deny root in the CI container.
        """
        locked = self._write(os.path.join(self.folder, "locked.txt"))
        stray_dir = os.path.join(self.folder, "stray_dir")
        self._write(os.path.join(stray_dir, "nested.txt"))
        real_unlink = os.unlink

        def fake_unlink(path, **kwargs):
            # rmtree unlinks its own entries through this same patch, so only the
            # one target path is faulted and everything else passes through.
            if isinstance(path, str) and os.path.basename(path) == "locked.txt":
                raise PermissionError("denied")
            return real_unlink(path, **kwargs)

        with (
            patch("controller.delete.delete_process.os.unlink", side_effect=fake_unlink),
            self.assertRaises(RuntimeError) as ctx,
        ):
            self._run(["locked.txt", "stray_dir"])

        self.assertTrue(os.path.exists(locked))
        self.assertFalse(os.path.exists(stray_dir), "later paths must still be processed")
        self.assertIn("locked.txt", str(ctx.exception))


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
