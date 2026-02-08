# Copyright 2017, Inderpreet Singh, All rights reserved.

import unittest
from unittest.mock import patch, MagicMock, PropertyMock

from ssh import Sshcp, SshcpError


class TestDetectShell(unittest.TestCase):
    """Unit tests for Sshcp.detect_shell() using mocked SSH connections."""

    def setUp(self):
        self.sshcp = Sshcp(host="testhost", port=22, user="testuser", password="testpass")

    @patch.object(Sshcp, '_run_shell_command')
    def test_detect_shell_returns_bash_when_available(self, mock_run):
        """When login shell works and bash is found, returns bash path."""
        mock_run.side_effect = [
            b"__shell_ok__",  # echo test
            b"__shell_path__/usr/bin/bash__end__",  # which bash
        ]
        result = self.sshcp.detect_shell()
        self.assertEqual("/usr/bin/bash", result)
        self.assertEqual(2, mock_run.call_count)

    @patch.object(Sshcp, '_run_shell_command')
    def test_detect_shell_returns_sh_when_bash_not_found(self, mock_run):
        """When login shell works but bash not found, returns sh path."""
        mock_run.side_effect = [
            b"__shell_ok__",  # echo test
            b"__shell_path__/bin/sh__end__",  # which sh (bash not found)
        ]
        result = self.sshcp.detect_shell()
        self.assertEqual("/bin/sh", result)

    @patch.object(Sshcp, '_run_shell_command')
    def test_detect_shell_returns_bin_bash(self, mock_run):
        """When login shell works and /bin/bash is found."""
        mock_run.side_effect = [
            b"__shell_ok__",
            b"__shell_path__/bin/bash__end__",
        ]
        result = self.sshcp.detect_shell()
        self.assertEqual("/bin/bash", result)

    @patch.object(Sshcp, '_run_shell_command')
    def test_detect_shell_defaults_to_sh_on_unknown(self, mock_run):
        """When login shell works but shell path is unknown, defaults to /bin/sh."""
        mock_run.side_effect = [
            b"__shell_ok__",
            b"__shell_path__unknown__end__",
        ]
        result = self.sshcp.detect_shell()
        self.assertEqual("/bin/sh", result)

    @patch.object(Sshcp, '_run_shell_command')
    def test_detect_shell_defaults_to_sh_on_detection_error(self, mock_run):
        """When login shell works but detection command fails, defaults to /bin/sh."""
        mock_run.side_effect = [
            b"__shell_ok__",
            SshcpError("command failed"),
        ]
        result = self.sshcp.detect_shell()
        self.assertEqual("/bin/sh", result)

    @patch.object(Sshcp, '_run_shell_command')
    def test_detect_shell_caches_result(self, mock_run):
        """Shell detection result is cached across calls."""
        mock_run.side_effect = [
            b"__shell_ok__",
            b"__shell_path__/bin/bash__end__",
        ]
        result1 = self.sshcp.detect_shell()
        result2 = self.sshcp.detect_shell()
        self.assertEqual(result1, result2)
        # Should only have called _run_shell_command twice (both on first call)
        self.assertEqual(2, mock_run.call_count)

    @patch.object(Sshcp, '_check_remote_shells_via_sftp')
    @patch.object(Sshcp, '_run_shell_command')
    def test_detect_shell_shell_not_found_with_alternatives(self, mock_run, mock_sftp):
        """When login shell is broken, uses SFTP to find alternatives."""
        mock_run.side_effect = SshcpError(
            "No such file or directory: /bin/bash"
        )
        mock_sftp.return_value = ["/usr/bin/bash", "/bin/sh"]

        with self.assertRaises(SshcpError) as ctx:
            self.sshcp.detect_shell()
        error_msg = str(ctx.exception)
        self.assertIn("login shell not found", error_msg)
        self.assertIn("/usr/bin/bash", error_msg)
        self.assertIn("/bin/sh", error_msg)
        self.assertIn("sudo chsh", error_msg)
        self.assertIn("/usr/bin/bash", error_msg)  # first available shell suggested

    @patch.object(Sshcp, '_check_remote_shells_via_sftp')
    @patch.object(Sshcp, '_run_shell_command')
    def test_detect_shell_shell_not_found_no_alternatives(self, mock_run, mock_sftp):
        """When login shell is broken and no alternatives found via SFTP."""
        mock_run.side_effect = SshcpError(
            "No such file or directory: /bin/bash"
        )
        mock_sftp.return_value = []

        with self.assertRaises(SshcpError) as ctx:
            self.sshcp.detect_shell()
        error_msg = str(ctx.exception)
        self.assertIn("login shell not found", error_msg)
        self.assertIn("no common shells", error_msg)

    @patch.object(Sshcp, '_run_shell_command')
    def test_detect_shell_reraises_non_shell_errors(self, mock_run):
        """Non-shell-related SSH errors are re-raised as-is."""
        mock_run.side_effect = SshcpError("Connection refused by server")

        with self.assertRaises(SshcpError) as ctx:
            self.sshcp.detect_shell()
        self.assertEqual("Connection refused by server", str(ctx.exception))

    @patch.object(Sshcp, '_run_shell_command')
    def test_detect_shell_handles_garbled_output(self, mock_run):
        """When detection output doesn't match expected format, defaults to /bin/sh."""
        mock_run.side_effect = [
            b"__shell_ok__",
            b"some garbled output",
        ]
        result = self.sshcp.detect_shell()
        self.assertEqual("/bin/sh", result)

    @patch.object(Sshcp, '_run_shell_command')
    def test_detect_shell_handles_empty_shell_path(self, mock_run):
        """When detection returns empty shell path, defaults to /bin/sh."""
        mock_run.side_effect = [
            b"__shell_ok__",
            b"__shell_path____end__",
        ]
        result = self.sshcp.detect_shell()
        self.assertEqual("/bin/sh", result)


class TestCheckRemoteShellsViaSftp(unittest.TestCase):
    """Unit tests for _check_remote_shells_via_sftp."""

    def setUp(self):
        self.sshcp = Sshcp(host="testhost", port=22, user="testuser", password="testpass")

    @patch.object(Sshcp, '_sftp_stat')
    def test_returns_available_shells(self, mock_stat):
        """Returns list of shells that exist on remote."""
        def stat_side_effect(path):
            if path in ["/usr/bin/bash", "/bin/sh"]:
                return  # exists
            raise SshcpError("File not found")

        mock_stat.side_effect = stat_side_effect
        result = self.sshcp._check_remote_shells_via_sftp()
        self.assertEqual(["/usr/bin/bash", "/bin/sh"], result)

    @patch.object(Sshcp, '_sftp_stat')
    def test_returns_empty_when_no_shells(self, mock_stat):
        """Returns empty list when no shells found."""
        mock_stat.side_effect = SshcpError("File not found")
        result = self.sshcp._check_remote_shells_via_sftp()
        self.assertEqual([], result)

    @patch.object(Sshcp, '_sftp_stat')
    def test_returns_all_shells_when_all_exist(self, mock_stat):
        """Returns all candidates when all exist."""
        mock_stat.return_value = None  # all succeed
        result = self.sshcp._check_remote_shells_via_sftp()
        self.assertEqual(Sshcp.SHELL_CANDIDATES, result)


class TestShellCandidates(unittest.TestCase):
    """Tests for SHELL_CANDIDATES constant."""

    def test_shell_candidates_not_empty(self):
        self.assertTrue(len(Sshcp.SHELL_CANDIDATES) > 0)

    def test_shell_candidates_contains_common_shells(self):
        self.assertIn("/bin/bash", Sshcp.SHELL_CANDIDATES)
        self.assertIn("/usr/bin/bash", Sshcp.SHELL_CANDIDATES)
        self.assertIn("/bin/sh", Sshcp.SHELL_CANDIDATES)
