# Copyright 2017, Inderpreet Singh, All rights reserved.

import logging
import unittest
from unittest.mock import MagicMock, patch

from ssh import Sshcp


# noinspection SpellCheckingInspection
class TestSshcpRunCommand(unittest.TestCase):
    """Offline unit tests for Sshcp.__run_command().

    Pin the ssh option flags and the expect() timeouts without needing a live
    SSH server by patching pexpect.spawn. These guard two fixes:
      * the password-prompt wait must use the full __TIMEOUT_SECS, not
        pexpect's silent 30s default;
      * GSSAPI auth is disabled to avoid slow auth-prompt delays.
    """

    __TIMEOUT = Sshcp._Sshcp__TIMEOUT_SECS

    def _make_sshcp(self, password: str | None) -> Sshcp:
        sshcp = Sshcp.__new__(Sshcp)
        sshcp._Sshcp__host = "host"
        sshcp._Sshcp__port = 22
        sshcp._Sshcp__user = "user"
        sshcp._Sshcp__password = password
        sshcp.logger = logging.getLogger("test_sshcp_run_command")
        return sshcp

    def _run(self, password: str | None):
        """Run __run_command with a mocked pexpect spawn that succeeds.

        Returns (command_string, expect_calls) where command_string is the
        full ssh command handed to pexpect.spawn and expect_calls is the list
        of expect() call objects in invocation order.
        """
        sshcp = self._make_sshcp(password)
        sp = MagicMock()
        sp.expect.return_value = 0  # always match index 0 (prompt / EOF success)
        sp.before = b"output"
        sp.after = b""
        sp.exitstatus = 0
        with patch("ssh.sshcp.pexpect.spawn", return_value=sp) as mock_spawn:
            out = sshcp._Sshcp__run_command(command="ssh", flags="-p 22", args='user@host "ls"')
        self.assertEqual(b"output", out)
        return mock_spawn.call_args.args[0], sp.expect.call_args_list

    def test_password_prompt_uses_full_timeout(self):
        # Regression: the password-prompt expect() previously had no timeout=
        # and fell back to pexpect's 30s default. Both expects must use 180s.
        _, expect_calls = self._run(password="secret")
        self.assertEqual(2, len(expect_calls))
        self.assertEqual(self.__TIMEOUT, expect_calls[0].kwargs.get("timeout"))
        self.assertEqual(self.__TIMEOUT, expect_calls[1].kwargs.get("timeout"))

    def test_keyauth_output_expect_uses_full_timeout(self):
        # Key auth skips the password branch: a single expect with the full timeout.
        _, expect_calls = self._run(password=None)
        self.assertEqual(1, len(expect_calls))
        self.assertEqual(self.__TIMEOUT, expect_calls[0].kwargs.get("timeout"))

    def test_gssapi_auth_disabled(self):
        for password in ("secret", None):
            with self.subTest(password=password):
                command, _ = self._run(password=password)
                self.assertIn("GSSAPIAuthentication=no", command)

    def test_password_auth_disables_pubkey(self):
        command, _ = self._run(password="secret")
        self.assertIn("PubkeyAuthentication=no", command)
        self.assertNotIn("PasswordAuthentication=no", command)

    def test_keyauth_disables_password(self):
        command, _ = self._run(password=None)
        self.assertIn("PasswordAuthentication=no", command)
        self.assertNotIn("PubkeyAuthentication=no", command)
