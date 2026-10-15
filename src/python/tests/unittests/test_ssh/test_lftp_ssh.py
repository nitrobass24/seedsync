import unittest

from ssh.lftp_ssh import is_credential_error


class TestIsCredentialError(unittest.TestCase):
    def test_ssh_auth_failures_are_credential_errors(self):
        for message in (
            "Incorrect password",
            "Connection refused by server - user@host: Permission denied (publickey,password).",
            "Permission denied, please try again.",
            "Permission denied (keyboard-interactive).",
        ):
            with self.subTest(message=message):
                self.assertTrue(is_credential_error(message))

    def test_other_permission_denied_errors_are_not(self):
        for message in (
            "mirror: Access failed: Permission denied (/remote/file)",
            "[Errno 13] Permission denied: '/downloads/file'",
            "Connection refused by server",
            "Bad hostname: seedbox",
        ):
            with self.subTest(message=message):
                self.assertFalse(is_credential_error(message))
