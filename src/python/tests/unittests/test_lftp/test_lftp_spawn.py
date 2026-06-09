# Copyright 2017, Inderpreet Singh, All rights reserved.

"""Offline unit tests for Lftp process spawning and protocol setup.

Unlike the @requires_live_ssh suite in ``test_lftp.py`` (which talks to a real
SSH/SFTP server), these tests patch ``pexpect.spawn`` with a fake recording
process so they run in CI with no network. They assert the exact connection
command (``-p`` port + scheme URL) and the ``set`` commands each protocol issues
during ``__setup``.
"""

import re
import unittest
from unittest.mock import patch

import lftp.lftp as lftp_mod
from lftp import Lftp, LftpError


class FakeSpawn:
    """A stand-in for ``pexpect.spawn`` that records ``sendline`` calls and
    returns canned ``before`` output for ``__get`` read-backs.

    ``get_responses`` maps an lftp setting name to the value the fake should
    report when the code runs ``set -a | grep <setting>`` (used by the FTPS
    fail-closed read-back). Anything not listed defaults to ``true``.
    """

    def __init__(self, command, args, env=None, get_responses=None):
        self.command = command
        self.args = list(args)
        self.env = env
        self.sendlines: list[str] = []
        self._get_responses = get_responses or {}
        self._last_command: str | None = None
        self.before = b""
        self.after = b""
        self.closed = False

    # --- API used by Lftp ---------------------------------------------------
    def setwinsize(self, rows, cols):
        pass

    def isalive(self) -> bool:
        return not self.closed

    def sendline(self, command: str):
        self.sendlines.append(command)
        self._last_command = command

    def expect(self, pattern, timeout=None) -> int:
        # Produce a canned 'before' buffer for the previous sendline. For a
        # 'set -a | grep <setting>' query, echo the matching setting value so
        # Lftp.__get can parse it; otherwise an empty (error-free) buffer.
        cmd = self._last_command
        if cmd and cmd.startswith("set -a | grep "):
            setting = cmd[len("set -a | grep ") :].strip()
            value = self._get_responses.get(setting, "true")
            self.before = f"set {setting} {value}".encode()
        else:
            self.before = b""
        return 0

    def close(self, force=False):
        self.closed = True


def make_lftp(get_responses=None, **kwargs):
    """Construct a real Lftp, but with pexpect.spawn replaced by FakeSpawn.

    Returns ``(lftp, fake)`` where ``fake`` is the FakeSpawn instance the
    constructor used (so tests can inspect ``fake.sendlines`` / ``fake.args``).
    """
    created: list[FakeSpawn] = []

    def fake_spawn(command, args, env=None):
        fake = FakeSpawn(command, args, env=env, get_responses=get_responses)
        created.append(fake)
        return fake

    with patch.object(lftp_mod.pexpect, "spawn", side_effect=fake_spawn):
        lftp = Lftp(**kwargs)
    return lftp, created[-1]


def sent_settings(fake: FakeSpawn) -> dict[str, str]:
    """Parse the recorded ``set <name> <value>`` sendlines into a dict.

    The last value wins (matching lftp semantics). The fail-closed read-back's
    ``set -a | grep ...`` lines are ignored.
    """
    settings: dict[str, str] = {}
    for line in fake.sendlines:
        m = re.match(r"^set (?P<name>\S+) (?P<value>.+)$", line)
        if m and not line.startswith("set -a | grep "):
            settings[m.group("name")] = m.group("value")
    return settings


class TestLftpSpawn(unittest.TestCase):
    def test_lftp_spawn_sftp(self):
        """Regression: the default (sftp) protocol uses sftp:// + -p port and
        issues the two sftp:* settings."""
        lftp, fake = make_lftp(address="host.example.com", port=22, user="bob", password=None)

        # Connection command: -p 22 and sftp://host
        self.assertIn("-p", fake.args)
        self.assertEqual("22", fake.args[fake.args.index("-p") + 1])
        self.assertIn("sftp://host.example.com", fake.args)
        self.assertNotIn("ftp://host.example.com", fake.args)
        # -u user,pass form preserved
        self.assertIn("-u", fake.args)
        self.assertEqual("bob,", fake.args[fake.args.index("-u") + 1])

        # sftp:* settings issued
        settings = sent_settings(fake)
        self.assertEqual("1", settings.get("sftp:auto-confirm"))
        self.assertEqual("false", settings.get("sftp:set-permissions"))
        # No FTPS settings
        self.assertNotIn("ftp:ssl-force", settings)
        self.assertNotIn("ssl:verify-certificate", settings)

    def test_lftp_spawn_ftps(self):
        """FTPS protocol uses ftp:// + the FTP transfer port and issues the
        TLS settings, skipping the sftp:* settings."""
        lftp, fake = make_lftp(
            address="host.example.com",
            port=22,
            user="bob",
            password="secret",
            protocol="ftps",
            remote_ftp_port=21,
            ssl_verify_certificate=False,
        )

        # Connection command: -p 21 (the ftp port, NOT 22) and ftp://host
        self.assertEqual("21", fake.args[fake.args.index("-p") + 1])
        self.assertIn("ftp://host.example.com", fake.args)
        self.assertNotIn("sftp://host.example.com", fake.args)
        # -u user,pass form preserved
        self.assertEqual("bob,secret", fake.args[fake.args.index("-u") + 1])

        settings = sent_settings(fake)
        # TLS hardcoded ON
        self.assertEqual("true", settings.get("ftp:ssl-force"))
        self.assertEqual("true", settings.get("ftp:ssl-protect-data"))
        # Verify cert off (from ssl_verify_certificate=False)
        self.assertEqual("false", settings.get("ssl:verify-certificate"))
        # Explicit AUTH TLS + passive mode
        self.assertEqual("TLS", settings.get("ftp:ssl-auth"))
        self.assertEqual("true", settings.get("ftp:passive-mode"))
        # sftp:* settings NOT issued
        self.assertNotIn("sftp:auto-confirm", settings)
        self.assertNotIn("sftp:set-permissions", settings)

    def test_lftp_spawn_ftps_verify_cert_true(self):
        """When ssl_verify_certificate=True, ssl:verify-certificate is 'true'
        and no MITM warning is logged."""
        with patch.object(lftp_mod.logging.getLogger("Lftp"), "warning") as warn:
            lftp, fake = make_lftp(
                address="host",
                port=22,
                user="u",
                password=None,
                protocol="ftps",
                remote_ftp_port=990,
                ssl_verify_certificate=True,
            )
        settings = sent_settings(fake)
        self.assertEqual("true", settings.get("ssl:verify-certificate"))
        # No MITM warning when verification is on
        warned_mitm = any(
            "man-in-the-middle" in str(c.args[0]).lower() if c.args else False for c in warn.call_args_list
        )
        self.assertFalse(warned_mitm)

    def test_lftp_spawn_ftps_warns_when_verify_disabled(self):
        """A per-spawn WARNING is emitted when FTPS runs without cert
        verification."""
        with patch.object(lftp_mod.logging.getLogger("Lftp"), "warning") as warn:
            make_lftp(
                address="host",
                port=22,
                user="u",
                password=None,
                protocol="ftps",
                remote_ftp_port=21,
                ssl_verify_certificate=False,
            )
        warned_mitm = any(
            ("man-in-the-middle" in str(c.args[0]).lower()) if c.args else False for c in warn.call_args_list
        )
        self.assertTrue(warned_mitm)

    def test_lftp_spawn_ftps_default_port_falls_back(self):
        """FTPS with no remote_ftp_port falls back to the given port."""
        lftp, fake = make_lftp(address="host", port=2121, user="u", password=None, protocol="ftps")
        self.assertEqual("2121", fake.args[fake.args.index("-p") + 1])
        self.assertIn("ftp://host", fake.args)

    def test_lftp_ftps_fail_closed(self):
        """If the ftp:ssl-force read-back reports 'false', construction raises
        LftpError (never falls back to cleartext)."""
        with self.assertRaises(LftpError) as ctx:
            make_lftp(
                get_responses={"ftp:ssl-force": "false"},
                address="host",
                port=22,
                user="u",
                password=None,
                protocol="ftps",
                remote_ftp_port=21,
            )
        self.assertIn("ssl-force", str(ctx.exception))

    def test_sftp_no_fail_closed_check(self):
        """The fail-closed read-back is FTPS-only: SFTP never queries
        ftp:ssl-force."""
        _lftp, fake = make_lftp(address="host", port=22, user="u", password=None)
        self.assertFalse(
            any("ftp:ssl-force" in line for line in fake.sendlines),
            "SFTP setup must not read back ftp:ssl-force",
        )

    def test_lftp_ftps_restart_reverifies_ssl_force(self):
        """A restart re-runs the FTPS fail-closed check: if the restarted
        process can no longer force TLS, the operation raises (carrying the
        underlying reason) rather than silently transferring over cleartext."""
        # First spawn forces TLS OK; the restart's spawn reports ssl-force=false.
        responses = [{"ftp:ssl-force": "true"}, {"ftp:ssl-force": "false"}]
        created: list[FakeSpawn] = []

        def fake_spawn(command, args, env=None):
            resp = responses[min(len(created), len(responses) - 1)]
            fake = FakeSpawn(command, args, env=env, get_responses=resp)
            created.append(fake)
            return fake

        with patch.object(lftp_mod.pexpect, "spawn", side_effect=fake_spawn):
            lftp = Lftp(
                address="host",
                port=22,
                user="u",
                password=None,
                protocol="ftps",
                remote_ftp_port=21,
            )
            self.assertEqual(1, len(created))  # construction succeeded (ssl-force=true)
            created[-1].close()  # kill the process so the next command restarts it
            with self.assertRaises(LftpError) as ctx:
                lftp.status()  # @with_check_process -> restart -> spawn 2 fails closed
        self.assertEqual(2, len(created), "a restart should have occurred")
        self.assertIn("restart failed", str(ctx.exception))
        self.assertIn("ssl-force", str(ctx.exception))


class TestLftpFtpsErrorDetection(unittest.TestCase):
    """The FTPS error signatures added to __detect_errors_from_output."""

    def _detect(self, out: str) -> bool:
        return Lftp._Lftp__detect_errors_from_output(out)

    def test_lftp_ftps_ssl_error_detected(self):
        cert_error = "mirror: Certificate verification: certificate common name doesn't match requested host name"
        self.assertTrue(self._detect(cert_error))

    def test_tls_handshake_error_detected(self):
        self.assertTrue(self._detect("Fatal error: gnutls_handshake: A TLS fatal alert has been received."))

    def test_data_connection_timeout_detected(self):
        self.assertTrue(self._detect("Make data connection: error: timeout"))

    def test_existing_sftp_errors_still_detected(self):
        # Regression: the original signatures must still trip.
        self.assertTrue(self._detect("mirror: Access failed: No such file"))
        self.assertTrue(self._detect("Login failed: Login incorrect"))

    def test_clean_output_not_flagged(self):
        self.assertFalse(self._detect("`file' at 100 (50%) 1.2M/s eta:30s [Receiving data/TLS]"))
