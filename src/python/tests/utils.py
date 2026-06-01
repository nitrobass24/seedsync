# Copyright 2017, Inderpreet Singh, All rights reserved.

import contextlib
import os
import unittest

# Live-server test suites talk to a real SSH/SFTP server using the
# `seedsynctest` account on localhost (see doc/DeveloperReadme.md). They are
# skipped unless SEEDSYNC_LIVE_SSH_TESTS is set to a truthy value, so CI and
# `make test` (neither of which provisions that account) stay green while the
# fully-mocked tests in the same packages still run.
LIVE_SSH_TESTS_ENV_VAR = "SEEDSYNC_LIVE_SSH_TESTS"


def live_ssh_tests_enabled() -> bool:
    """True if the live seedsynctest SSH account is available (opt-in via env var)."""
    return os.environ.get(LIVE_SSH_TESTS_ENV_VAR, "").strip().lower() in ("1", "true", "yes", "on")


def requires_live_ssh(test_item):
    """Class/method decorator: skip a live-server test unless the seedsynctest account is enabled."""
    reason = (
        f"requires the live seedsynctest SSH account; "
        f"set {LIVE_SSH_TESTS_ENV_VAR}=1 to run (see doc/DeveloperReadme.md)"
    )
    return unittest.skipUnless(live_ssh_tests_enabled(), reason)(test_item)


class TestUtils:
    @staticmethod
    def chmod_from_to(from_path: str, to_path: str, mode: int):
        """
        Chmod from_path and all its parents up to and including to_path
        :param from_path:
        :param to_path:
        :param mode:
        :return:
        """
        path = from_path
        with contextlib.suppress(PermissionError):
            os.chmod(path, mode)
        while path != "/" and path != to_path:
            path = os.path.dirname(path)
            with contextlib.suppress(PermissionError):
                os.chmod(path, mode)
