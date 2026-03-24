import unittest

from ssh import Sshcp


class TestSshcpRemoteAddress(unittest.TestCase):
    """Unit tests for Sshcp._remote_address helper."""

    def test_remote_address_with_user(self):
        sshcp = Sshcp(host="example.com", port=22, user="alice")
        self.assertEqual("alice@example.com", sshcp._remote_address())

    def test_remote_address_without_user(self):
        sshcp = Sshcp(host="example.com", port=22, user=None)
        self.assertEqual("example.com", sshcp._remote_address())

    def test_remote_address_default_user(self):
        sshcp = Sshcp(host="example.com", port=22)
        self.assertEqual("example.com", sshcp._remote_address())
