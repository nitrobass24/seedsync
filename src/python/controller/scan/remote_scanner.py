# Copyright 2017, Inderpreet Singh, All rights reserved.

import logging
import json
import time
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
    Scanner implementation to scan the remote filesystem.
    Uploads scan_fs.py to the remote and runs it via python3.
    """
    _SCAN_MAX_RETRIES = 3
    _SCAN_RETRY_DELAY_SECS = 5

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

        out = self._run_scanfs_with_retry()

        try:
            data = json.loads(out)
            remote_files = [SystemFile.from_dict(d) for d in data]
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as err:
            self.logger.error("JSON parse error: {}\n{}".format(str(err), out[:500]))
            raise ScannerError(
                Localization.Error.REMOTE_SERVER_SCAN.format("Invalid JSON data from scanner"),
                recoverable=False
            )

        self.__first_run = False
        return remote_files

    def _run_scanfs_with_retry(self) -> bytes:
        """
        Run the scanfs command on the remote with retries for transient errors.
        """
        last_error = None
        for attempt in range(1, self._SCAN_MAX_RETRIES + 1):
            try:
                # Use consistent quoting: double quotes if scan path has tilde
                # (for $HOME expansion), single quotes otherwise
                if self.__remote_path_to_scan.startswith("~"):
                    return self.__ssh.shell("python3 {} {}".format(
                        _escape_remote_path_double(self.__remote_path_to_scan_script),
                        _escape_remote_path_double(self.__remote_path_to_scan))
                    )
                else:
                    return self.__ssh.shell("python3 {} {}".format(
                        _escape_remote_path_single(self.__remote_path_to_scan_script),
                        _escape_remote_path_single(self.__remote_path_to_scan))
                    )
            except SshcpError as e:
                last_error = e
                error_str = str(e)
                self.logger.warning(
                    "Scan attempt {}/{} failed: {}".format(
                        attempt, self._SCAN_MAX_RETRIES, error_str
                    )
                )

                # Non-recoverable errors: don't retry
                if "Is a directory" in error_str:
                    raise ScannerError(
                        "Server Script Path '{}' is a directory on the remote server. "
                        "Change the 'Server Script Path' setting to a writable location "
                        "outside your sync tree (e.g. '~' or '~/.local') and remove the "
                        "conflicting directory from the remote server.".format(
                            self.__remote_path_to_scan_script
                        ),
                        recoverable=False
                    )

                if "SystemScannerError" in error_str:
                    raise ScannerError(
                        Localization.Error.REMOTE_SERVER_SCAN.format(error_str.strip()),
                        recoverable=False
                    )

                # Config errors on first run are non-recoverable
                if self.__first_run and not self._is_transient_error(error_str):
                    raise ScannerError(
                        Localization.Error.REMOTE_SERVER_SCAN.format(error_str.strip()),
                        recoverable=False
                    )

                # Retry transient errors
                if attempt < self._SCAN_MAX_RETRIES:
                    self.logger.info(
                        "Retrying in {}s...".format(self._SCAN_RETRY_DELAY_SECS)
                    )
                    time.sleep(self._SCAN_RETRY_DELAY_SECS)

        # All retries exhausted
        self.logger.error(
            "All {} scan attempts failed".format(self._SCAN_MAX_RETRIES)
        )
        raise ScannerError(
            Localization.Error.REMOTE_SERVER_SCAN.format(str(last_error).strip()),
            recoverable=True
        )

    @staticmethod
    def _is_transient_error(error_str: str) -> bool:
        """Timeouts and connection drops are transient and worth retrying."""
        transient_patterns = ["Timed out", "lost connection", "Connection refused", "Connection timed out"]
        return any(p in error_str for p in transient_patterns)

    def _install_scanfs(self):
        # Detect available shell on first run to provide clear errors
        # if the login shell is broken (e.g., /bin/bash not found)
        try:
            self.__ssh.detect_shell()
        except SshcpError as e:
            self.logger.exception("Shell detection failed")
            recoverable = self._is_transient_error(str(e))
            raise ScannerError(
                Localization.Error.REMOTE_SERVER_INSTALL.format(str(e).strip()),
                recoverable=recoverable
            )

        # Resolve tilde in the script path to an absolute path.
        # SCP expands ~ natively, but the path is shell-quoted for md5sum
        # and execution commands where ~ does not expand inside quotes.
        # Resolve by fetching the remote home dir via `echo ~` (no user
        # input in the command) and substituting in Python.
        if self.__remote_path_to_scan_script.startswith("~"):
            try:
                home = self.__ssh.shell("echo ~").decode().strip()
                if home and not home.startswith("~"):
                    expanded = home + self.__remote_path_to_scan_script[1:]
                    self.logger.debug("Resolved script path '{}' -> '{}'".format(
                        self.__remote_path_to_scan_script, expanded
                    ))
                    self.__remote_path_to_scan_script = expanded
            except SshcpError as e:
                self.logger.warning("Could not resolve tilde in script path: {}".format(str(e)))

        # Check md5sum on remote to see if we can skip installation
        with open(self.__local_path_to_scan_script, "rb") as f:
            local_md5sum = hashlib.md5(f.read()).hexdigest()
        self.logger.debug("Local scanfs md5sum = {}".format(local_md5sum))
        try:
            out = self.__ssh.shell("md5sum {} | awk '{{print $1}}' || echo".format(
                _escape_remote_path_single(self.__remote_path_to_scan_script)))
            out = out.decode().strip()
            if out == local_md5sum:
                self.logger.info("Skipping remote scanfs installation: already installed")
                return
        except SshcpError as e:
            self.logger.exception("Caught SSH exception during md5sum check")
            recoverable = self._is_transient_error(str(e))
            raise ScannerError(
                Localization.Error.REMOTE_SERVER_INSTALL.format(str(e).strip()),
                recoverable=recoverable
            )

        # Guard: if the target path is already a directory on the remote, the
        # copy would succeed (scp deposits the file inside the dir) but
        # execution would then fail with "Is a directory". Catch this early.
        try:
            result = self.__ssh.shell(
                "[ -d {} ] && echo IS_DIRECTORY || echo OK".format(
                    _escape_remote_path_single(self.__remote_path_to_scan_script)
                )
            ).decode().strip()
            if result == "IS_DIRECTORY":
                raise ScannerError(
                    "Server Script Path '{}' is a directory on the remote server. "
                    "This usually means it overlaps with your sync directory. "
                    "Change the 'Server Script Path' setting to a writable location "
                    "outside your sync tree (e.g. '~' or '~/.local') and remove the "
                    "conflicting directory from the remote server.".format(
                        self.__remote_path_to_scan_script
                    ),
                    recoverable=False
                )
        except SshcpError as e:
            self.logger.warning("Could not check remote path type: {}".format(str(e)))

        # Go ahead and install
        self.logger.info("Installing local:{} to remote:{}".format(
            self.__local_path_to_scan_script,
            self.__remote_path_to_scan_script
        ))
        if not os.path.isfile(self.__local_path_to_scan_script):
            raise ScannerError(
                Localization.Error.REMOTE_SERVER_SCAN.format(
                    "Failed to find scan script at {}".format(self.__local_path_to_scan_script)
                ),
                recoverable=False
            )
        try:
            self.__ssh.copy(local_path=self.__local_path_to_scan_script,
                            remote_path=self.__remote_path_to_scan_script)
        except SshcpError as e:
            if "Permission denied" in str(e):
                self._install_scanfs_with_home_fallback(str(e))
            else:
                self.logger.exception("Caught scp exception")
                recoverable = self._is_transient_error(str(e))
                raise ScannerError(
                    Localization.Error.REMOTE_SERVER_INSTALL.format(str(e).strip()),
                    recoverable=recoverable
                )

    def _install_scanfs_with_home_fallback(self, original_error: str):
        """
        Called when SCP to the configured script path is denied.
        Falls back to the user's home directory and retries.
        Warns the user to update their Server Script Path setting.
        """
        script_name = os.path.basename(self.__local_path_to_scan_script)

        # Resolve ~ to an absolute path so quoting works for all operations.
        # Use `echo ~` with no arguments — no user input reaches the shell.
        fallback_path = "~/" + script_name
        try:
            home = self.__ssh.shell("echo ~").decode().strip()
            if home and not home.startswith("~"):
                fallback_path = home + "/" + script_name
        except SshcpError:
            pass

        self.logger.warning(
            "Script path '{}' is not writable (Permission denied). "
            "Retrying with home directory: '{}'".format(
                self.__remote_path_to_scan_script, fallback_path
            )
        )
        self.logger.warning(
            "Update 'Server Script Path' in Settings to '~' to avoid this fallback on restart."
        )

        # Guard: if the fallback path is already a directory, SCP would deposit
        # the script inside it and execution would fail with "Is a directory".
        try:
            result = self.__ssh.shell(
                "[ -d {} ] && echo IS_DIRECTORY || echo OK".format(
                    _escape_remote_path_single(fallback_path)
                )
            ).decode().strip()
            if result == "IS_DIRECTORY":
                raise ScannerError(
                    "Fallback script path '{}' is already a directory on the remote server. "
                    "Remove it and update 'Server Script Path' in Settings to a writable "
                    "location (e.g. '~' or '~/.local'). "
                    "Original error: {}".format(fallback_path, original_error.strip()),
                    recoverable=False
                )
        except SshcpError as e:
            self.logger.warning("Could not check fallback path type: {}".format(str(e)))

        try:
            self.__ssh.copy(local_path=self.__local_path_to_scan_script,
                            remote_path=fallback_path)
            self.__remote_path_to_scan_script = fallback_path
            self.logger.info("Scanner installed to fallback path: {}".format(fallback_path))
        except SshcpError as fallback_e:
            raise ScannerError(
                Localization.Error.REMOTE_SERVER_INSTALL.format(
                    "Could not install scanner to '{}' ({}), "
                    "fallback to '{}' also failed: {}".format(
                        self.__remote_path_to_scan_script, original_error.strip(),
                        fallback_path, str(fallback_e).strip()
                    )
                ),
                recoverable=False
            )

