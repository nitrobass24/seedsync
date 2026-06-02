# Copyright 2017, Inderpreet Singh, All rights reserved.

import unittest
from unittest.mock import MagicMock

from ssh import Sshcp


# noinspection SpellCheckingInspection
class TestSshcpShellQuoting(unittest.TestCase):
    """Offline unit tests for Sshcp.shell() command quoting.

    shell() builds the string handed to the remote ssh command line. Its
    hand-rolled quoting (not shlex.quote) is the local-side barrier for remote
    command transport, so the exact quoted output must be pinned. These tests
    patch _run_command so no live SSH server is needed.
    """

    def _make_sshcp(self) -> Sshcp:
        sshcp = Sshcp.__new__(Sshcp)
        sshcp._Sshcp__port = 22
        # shell() calls self._remote_address(); shadow it with a fixed value.
        sshcp._remote_address = MagicMock(return_value="user@host")
        sshcp._Sshcp__run_command = MagicMock(return_value=b"")
        return sshcp

    def _args(self, sshcp: Sshcp) -> str:
        """The 'args' string passed to _run_command: '<remote_address> <quoted_command>'."""
        return sshcp._Sshcp__run_command.call_args.kwargs["args"]

    def test_no_quotes_wrapped_in_double_quotes(self):
        sshcp = self._make_sshcp()
        sshcp.shell("ls -la")
        self.assertEqual('user@host "ls -la"', self._args(sshcp))

    def test_double_quotes_wrapped_in_single_quotes(self):
        sshcp = self._make_sshcp()
        sshcp.shell('echo "hi"')
        self.assertEqual("user@host 'echo \"hi\"'", self._args(sshcp))

    def test_single_quote_uses_shell_escape_trick(self):
        sshcp = self._make_sshcp()
        sshcp.shell("don't")
        # ' -> '"'"'  (end quote, double-quoted literal quote, reopen quote)
        self.assertEqual("user@host 'don'\"'\"'t'", self._args(sshcp))

    def test_mixed_single_and_double_quotes(self):
        sshcp = self._make_sshcp()
        sshcp.shell("a'b\"c")
        self.assertEqual("user@host 'a'\"'\"'b\"c'", self._args(sshcp))

    def test_command_and_flags_are_passed(self):
        sshcp = self._make_sshcp()
        sshcp.shell("ls")
        kwargs = sshcp._Sshcp__run_command.call_args.kwargs
        self.assertEqual("ssh", kwargs["command"])
        self.assertEqual("-p 22", kwargs["flags"])

    def test_empty_command_raises(self):
        sshcp = self._make_sshcp()
        with self.assertRaises(ValueError):
            sshcp.shell("")
