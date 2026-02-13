# Copyright 2017, Inderpreet Singh, All rights reserved.

import logging
import pickle
import re
from typing import List
import os
from typing import Optional
import hashlib

from .scanner_process import IScanner, ScannerError
from common import overrides, Localization
from common import escape_remote_path_single as _escape_remote_path_single
from common import escape_remote_path_double as _escape_remote_path_double
from ssh import Sshcp, SshcpError
from system import SystemFile


class RemoteScanner(IScanner):
    """
    Scanner implementation to scan the remote filesystem
    """
    _REQUIRED_ARCH = "x86_64"
    _MIN_GLIBC_VERSION = (2, 31)

    def __init__(self,
                 remote_address: str,
                 remote_username: str,
                 remote_password: Optional[str],
                 remote_port: int,
                 remote_path_to_scan: str,
                 local_path_to_scan_script: str,
                 remote_path_to_scan_script: str):
        self.logger = logging.getLogger("RemoteScanner")
        self.__remote_path_to_scan = remote_path_to_scan
        self.__local_path_to_scan_script = local_path_to_scan_script
        self.__remote_path_to_scan_script = remote_path_to_scan_script
        self.__ssh = Sshcp(host=remote_address,
                           port=remote_port,
                           user=remote_username,
                           password=remote_password)
        self.__first_run = True

        # Append scan script name to remote path if not there already
        script_name = os.path.basename(self.__local_path_to_scan_script)
        if os.path.basename(self.__remote_path_to_scan_script) != script_name:
            self.__remote_path_to_scan_script = os.path.join(self.__remote_path_to_scan_script, script_name)

    @overrides(IScanner)
    def set_base_logger(self, base_logger: logging.Logger):
        self.logger = base_logger.getChild("RemoteScanner")
        self.__ssh.set_base_logger(self.logger)

    @overrides(IScanner)
    def scan(self) -> List[SystemFile]:
        if self.__first_run:
            self._install_scanfs()

        try:
            # Use consistent quoting: double quotes if scan path has tilde (for $HOME expansion),
            # single quotes otherwise (protects literal characters)
            if self.__remote_path_to_scan.startswith("~"):
                out = self.__ssh.shell("{} {}".format(
                    _escape_remote_path_double(self.__remote_path_to_scan_script),
                    _escape_remote_path_double(self.__remote_path_to_scan))
                )
            else:
                out = self.__ssh.shell("{} {}".format(
                    _escape_remote_path_single(self.__remote_path_to_scan_script),
                    _escape_remote_path_single(self.__remote_path_to_scan))
                )
        except SshcpError as e:
            self.logger.warning("Caught an SshcpError: {}".format(str(e)))
            recoverable = True
            # Any scanner errors are fatal
            if "SystemScannerError" in str(e):
                recoverable = False
            # First time errors are fatal
            # User should be prompted to correct these
            if self.__first_run:
                recoverable = False
            raise ScannerError(
                Localization.Error.REMOTE_SERVER_SCAN.format(str(e).strip()),
                recoverable=recoverable
            )

        try:
            remote_files = pickle.loads(out)
        except pickle.UnpicklingError as err:
            self.logger.error("Unpickling error: {}\n{}".format(str(err), out))
            raise ScannerError(
                Localization.Error.REMOTE_SERVER_SCAN.format("Invalid pickled data"),
                recoverable=False
            )

        self.__first_run = False
        return remote_files

    def _install_scanfs(self):
        # Detect available shell on first run to provide clear errors
        # if the login shell is broken (e.g., /bin/bash not found)
        try:
            self.__ssh.detect_shell()
        except SshcpError as e:
            self.logger.exception("Shell detection failed")
            raise ScannerError(
                Localization.Error.REMOTE_SERVER_INSTALL.format(str(e).strip()),
                recoverable=False
            )

        self._log_remote_diagnostics()

        # Check md5sum on remote to see if we can skip installation
        with open(self.__local_path_to_scan_script, "rb") as f:
            local_md5sum = hashlib.md5(f.read()).hexdigest()
        self.logger.debug("Local scanfs md5sum = {}".format(local_md5sum))
        try:
            out = self.__ssh.shell("md5sum '{}' | awk '{{print $1}}' || echo".format(
                self.__remote_path_to_scan_script))
            out = out.decode()
            if out == local_md5sum:
                self.logger.info("Skipping remote scanfs installation: already installed")
                return
        except SshcpError as e:
            self.logger.exception("Caught scp exception")
            raise ScannerError(
                Localization.Error.REMOTE_SERVER_INSTALL.format(str(e).strip()),
                recoverable=False
            )

        # Go ahead and install
        self.logger.info("Installing local:{} to remote:{}".format(
            self.__local_path_to_scan_script,
            self.__remote_path_to_scan_script
        ))
        if not os.path.isfile(self.__local_path_to_scan_script):
            raise ScannerError(
                Localization.Error.REMOTE_SERVER_SCAN.format(
                    "Failed to find scanfs executable at {}".format(self.__local_path_to_scan_script)
                ),
                recoverable=False
            )
        try:
            self.__ssh.copy(local_path=self.__local_path_to_scan_script,
                            remote_path=self.__remote_path_to_scan_script)
        except SshcpError as e:
            self.logger.exception("Caught scp exception")
            raise ScannerError(
                Localization.Error.REMOTE_SERVER_INSTALL.format(str(e).strip()),
                recoverable=False
            )

    def _log_remote_diagnostics(self):
        """Log remote OS, architecture, and glibc version. Warn on incompatibilities."""
        try:
            cmd = (
                "uname -m && "
                "(grep ^PRETTY_NAME /etc/os-release 2>/dev/null || echo unknown) && "
                "(ldd --version 2>&1 | head -1 || echo unknown)"
            )
            out = self.__ssh.shell(cmd).decode().strip()
            lines = out.splitlines()
            arch = lines[0].strip() if len(lines) > 0 else "unknown"
            os_name = lines[1].strip().replace("PRETTY_NAME=", "").strip('"') if len(lines) > 1 else "unknown"
            glibc_line = lines[2].strip() if len(lines) > 2 else "unknown"

            self.logger.info("Remote server: os={}, arch={}, glibc={}".format(os_name, arch, glibc_line))

            if arch != self._REQUIRED_ARCH:
                self.logger.warning(
                    "Remote architecture is {}. scanfs requires x86_64 (amd64).".format(arch)
                )

            self._check_glibc_version(glibc_line)

        except SshcpError:
            self.logger.warning("Failed to collect remote server diagnostics")

    def _check_glibc_version(self, glibc_line: str):
        """Parse glibc version string and warn if too old."""
        match = re.search(r'(\d+)\.(\d+)', glibc_line)
        if not match:
            self.logger.warning("Could not determine remote glibc version")
            return
        major, minor = int(match.group(1)), int(match.group(2))
        if (major, minor) < self._MIN_GLIBC_VERSION:
            self.logger.warning(
                "Remote glibc {}.{} is older than required {}.{}. scanfs may fail to run.".format(
                    major, minor, self._MIN_GLIBC_VERSION[0], self._MIN_GLIBC_VERSION[1]
                )
            )
