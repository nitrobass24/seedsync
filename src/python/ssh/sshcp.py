# Copyright 2017, Inderpreet Singh, All rights reserved.

import logging
import time
from typing import Optional, List

import pexpect

# my libs
from common import AppError


class SshcpError(AppError):
    """
    Custom exception that describes the failure of the ssh command
    """
    pass


class Sshcp:
    """
    Scp command utility
    """
    __TIMEOUT_SECS = 180

    # Common shell paths to check, in order of preference
    SHELL_CANDIDATES = ["/bin/bash", "/usr/bin/bash", "/bin/sh", "/usr/bin/sh"]

    def __init__(self,
                 host: str,
                 port: int,
                 user: str = None,
                 password: str = None):
        if host is None:
            raise ValueError("Hostname not specified.")
        self.__host = host
        self.__port = port
        self.__user = user
        self.__password = password
        self.__detected_shell: Optional[str] = None
        self.__shell_detected: bool = False
        self.logger = logging.getLogger(self.__class__.__name__)

    def set_base_logger(self, base_logger: logging.Logger):
        self.logger = base_logger.getChild(self.__class__.__name__)

    def detect_shell(self) -> str:
        """
        Detect an available shell on the remote server.
        Tries running a test command via SSH. If the login shell is broken
        (e.g., /bin/bash not found), uses SFTP to check which shells exist
        and provides a clear error with remediation steps.
        Returns the detected shell path. Caches the result for the session.
        :return: path to the detected shell
        :raises SshcpError: if no working shell can be found
        """
        if self.__shell_detected:
            return self.__detected_shell

        self.logger.debug("Detecting remote shell...")

        # Try running a simple command to test the login shell
        try:
            self._run_shell_command("echo __shell_ok__")
            # Login shell works fine - detect which shell it is
            try:
                out = self._run_shell_command(
                    "echo __shell_path__$(which bash 2>/dev/null || "
                    "which sh 2>/dev/null || "
                    "echo unknown)__end__"
                )
                out_str = out.decode()
                # Parse the shell path from the marker-wrapped output
                if "__shell_path__" in out_str and "__end__" in out_str:
                    shell_path = out_str.split("__shell_path__")[1].split("__end__")[0].strip()
                    if shell_path and shell_path != "unknown":
                        self.__detected_shell = shell_path
                    else:
                        self.__detected_shell = "/bin/sh"
                else:
                    self.__detected_shell = "/bin/sh"
            except SshcpError:
                # Shell works but couldn't determine path - default to /bin/sh
                self.__detected_shell = "/bin/sh"

            self.__shell_detected = True
            self.logger.info("Detected remote shell: {}".format(self.__detected_shell))
            return self.__detected_shell

        except SshcpError as e:
            error_str = str(e)
            if "No such file or directory" not in error_str:
                # Not a shell-not-found error - re-raise as-is
                raise

            # Login shell is broken. Use SFTP to check which shells exist.
            self.logger.warning("Login shell not found on remote server. "
                                "Checking for available shells via SFTP...")

            available_shells = self._check_remote_shells_via_sftp()

            if available_shells:
                shells_str = ", ".join(available_shells)
                raise SshcpError(
                    "Remote user's login shell not found. "
                    "Available shells on the remote server: {}. "
                    "Fix by running on the remote server: "
                    "sudo chsh -s {} {}".format(
                        shells_str, available_shells[0], self.__user
                    )
                )
            else:
                raise SshcpError(
                    "Remote user's login shell not found and no common shells "
                    "could be detected. Fix by running on the remote server: "
                    "sudo chsh -s /bin/sh {} OR "
                    "sudo ln -s /usr/bin/bash /bin/bash".format(self.__user)
                )

    def _run_shell_command(self, command: str) -> bytes:
        """
        Run a shell command via SSH without going through the public shell()
        method's quoting logic. Used internally for shell detection.
        """
        # Quote the command
        if '"' in command:
            quoted = "'{}'".format(command)
        else:
            quoted = '"{}"'.format(command)

        flags = [
            "-p", str(self.__port),
        ]
        args = [
            "{}@{}".format(self.__user, self.__host),
            quoted
        ]
        return self.__run_command(
            command="ssh",
            flags=" ".join(flags),
            args=" ".join(args)
        )

    def _check_remote_shells_via_sftp(self) -> List[str]:
        """
        Check which shell binaries exist on the remote server using SFTP.
        SFTP does not require a working login shell.
        Returns a list of available shell paths.
        """
        available = []
        for shell_path in self.SHELL_CANDIDATES:
            try:
                self._sftp_stat(shell_path)
                available.append(shell_path)
            except SshcpError:
                pass
        return available

    def _sftp_stat(self, remote_path: str):
        """
        Use sftp to check if a remote file exists.
        SFTP uses a subsystem, not the login shell, so it works even
        when the login shell is broken.
        :raises SshcpError: if the file does not exist or the command fails
        """
        flags = [
            "-P", str(self.__port),
            "-o", "BatchMode=yes",
        ]

        # Use sftp batch mode to run 'ls' on the path
        args = [
            "-b", "-",  # read commands from stdin
            "{}@{}".format(self.__user, self.__host),
        ]

        command_args = ["sftp"]
        command_args += [
            "-o", "StrictHostKeyChecking=no",
            "-o", "UserKnownHostsFile=/dev/null",
            "-o", "LogLevel=error",
        ]

        if self.__password is None:
            command_args += ["-o", "PasswordAuthentication=no"]
        else:
            command_args += ["-o", "PubkeyAuthentication=no"]

        command_args += flags
        command_args += args

        command = " ".join(command_args)
        self.logger.debug("SFTP stat command: {}".format(command))

        sp = pexpect.spawn(command)
        try:
            if self.__password is not None:
                i = sp.expect([
                    'password: ',
                    pexpect.EOF,
                ], timeout=30)
                if i == 1:
                    sp.close()
                    raise SshcpError("SFTP connection failed")
                sp.sendline(self.__password)

            # Wait for sftp prompt
            i = sp.expect([
                'sftp>',
                pexpect.EOF,
                'password: ',
            ], timeout=30)
            if i != 0:
                sp.close()
                raise SshcpError("SFTP connection failed")

            # Send ls command to check if file exists
            sp.sendline("ls {}".format(remote_path))
            i = sp.expect([
                'sftp>',
                pexpect.EOF,
            ], timeout=30)

            output = sp.before.decode() if sp.before else ""
            sp.sendline("bye")
            sp.expect(pexpect.EOF, timeout=10)
            sp.close()

            if "No such file" in output or "not found" in output or "Can't ls" in output:
                raise SshcpError("File not found: {}".format(remote_path))

        except pexpect.exceptions.TIMEOUT:
            sp.close()
            raise SshcpError("SFTP timed out")

    def __run_command(self,
                      command: str,
                      flags: str,
                      args: str) -> bytes:

        command_args = [
            command,
            flags
        ]

        # Common flags
        command_args += [
            "-o", "StrictHostKeyChecking=no",  # ignore host key changes
            "-o", "UserKnownHostsFile=/dev/null",  # ignore known hosts file
            "-o", "LogLevel=error",  # suppress warnings
            "-o", "ConnectTimeout=30",  # cap connection establishment to 30s
            "-o", "ServerAliveInterval=15",  # send keepalive every 15s
            "-o", "ServerAliveCountMax=3",  # drop after 3 missed keepalives
        ]

        if self.__password is None:
            command_args += [
                "-o", "PasswordAuthentication=no",  # don't ask for password
            ]
        else:
            command_args += [
                "-o", "PubkeyAuthentication=no"  # don't use key authentication
            ]

        command_args.append(args)

        command = " ".join(command_args)
        self.logger.debug("Command: {}".format(command))

        start_time = time.time()
        sp = pexpect.spawn(command)
        try:
            if self.__password is not None:
                i = sp.expect([
                    'password: ',  # i=0, all's good
                    pexpect.EOF,  # i=1, unknown error
                    'lost connection',  # i=2, connection refused
                    'Could not resolve hostname',  # i=3, bad hostname
                    'Connection refused',  # i=4, connection refused
                ])
                if i > 0:
                    before = sp.before.decode().strip() if sp.before != pexpect.EOF else ""
                    after = sp.after.decode().strip() if sp.after != pexpect.EOF else ""
                    self.logger.warning("Command failed: '{} - {}'".format(before, after))
                if i == 1:
                    error_msg = "Unknown error"
                    if sp.before.decode().strip():
                        error_msg += " - " + sp.before.decode().strip()
                    raise SshcpError(error_msg)
                elif i == 3:
                    raise SshcpError("Bad hostname: {}".format(self.__host))
                elif i in {2, 4}:
                    error_msg = "Connection refused by server"
                    if sp.before.decode().strip():
                        error_msg += " - " + sp.before.decode().strip()
                    raise SshcpError(error_msg)
                sp.sendline(self.__password)

            i = sp.expect(
                [
                    pexpect.EOF,  # i=0, all's good
                    'password: ',  # i=1, wrong password
                    'lost connection',  # i=2, connection refused
                    'Could not resolve hostname',  # i=3, bad hostname
                    'Connection refused',  # i=4, connection refused
                ],
                timeout=self.__TIMEOUT_SECS
            )
            if i > 0:
                before = sp.before.decode().strip() if sp.before != pexpect.EOF else ""
                after = sp.after.decode().strip() if sp.after != pexpect.EOF else ""
                self.logger.warning("Command failed: '{} - {}'".format(before, after))
            if i == 1:
                raise SshcpError("Incorrect password")
            elif i == 3:
                raise SshcpError("Bad hostname: {}".format(self.__host))
            elif i in {2, 4}:
                error_msg = "Connection refused by server"
                if sp.before.decode().strip():
                    error_msg += " - " + sp.before.decode().strip()
                raise SshcpError(error_msg)

            # Capture attributes while sp is still open (before finally closes it)
            exit_status = sp.exitstatus
            out_before = sp.before.decode().strip() if sp.before != pexpect.EOF else ""
            out_after = sp.after.decode().strip() if sp.after != pexpect.EOF else ""
            out_raw = sp.before.replace(b'\r\n', b'\n').strip()

        except pexpect.exceptions.TIMEOUT:
            elapsed = time.time() - start_time
            self.logger.error(
                "Timed out after {:.0f}s (limit: {}s). Command: {}".format(
                    elapsed, self.__TIMEOUT_SECS, command
                )
            )
            self.logger.error("Command output before timeout: {}".format(
                sp.before if sp.before else b'(none)'
            ))
            raise SshcpError("Timed out after {:.0f}s".format(elapsed))
        finally:
            sp.close()

        end_time = time.time()

        self.logger.debug("Return code: {}".format(exit_status))
        self.logger.debug("Command took {:.3f}s".format(end_time-start_time))
        if exit_status != 0:
            self.logger.warning("Command failed: '{} - {}'".format(out_before, out_after))

            # Check for shell not found error (common on servers where bash is at /usr/bin/bash)
            if "No such file or directory" in out_before:
                for shell in self.SHELL_CANDIDATES:
                    if shell in out_before:
                        raise SshcpError(
                            "Remote user's login shell not found: {}. "
                            "Run detect_shell() or fix by running on the remote server: "
                            "sudo chsh -s /bin/sh {}".format(shell, self.__user)
                        )

            raise SshcpError(out_before)

        return out_raw

    def shell(self, command: str) -> bytes:
        """
        Run a shell command on remote service and return output
        :param command:
        :return:
        """
        if not command:
            raise ValueError("Command cannot be empty")

        # escape the command for SSH transport
        if "'" in command:
            # Single quotes in command: wrap in single quotes and escape each
            # inner single quote using the shell '"'"' trick (end single-quote,
            # add a double-quoted literal single-quote, start new single-quote).
            # This handles commands with both single and double quotes, e.g.
            # filenames like "Don't" inside double-quoted $HOME paths.
            command = "'" + command.replace("'", "'\"'\"'") + "'"
        elif '"' in command:
            # double quote in command, cover with single quotes
            command = "'{}'".format(command)
        else:
            # no quotes in command, cover with double quotes
            command = '"{}"'.format(command)

        flags = [
            "-p", str(self.__port),  # port
        ]
        args = [
            "{}@{}".format(self.__user, self.__host),
            command
        ]
        return self.__run_command(
            command="ssh",
            flags=" ".join(flags),
            args=" ".join(args)
        )

    def copy(self, local_path: str, remote_path: str):
        """
        Copies local file at local_path to remote remote_path
        :param local_path:
        :param remote_path:
        :return:
        """
        if not local_path:
            raise ValueError("Local path cannot be empty")
        if not remote_path:
            raise ValueError("Remote path cannot be empty")

        flags = [
            "-q",  # quiet
            "-P", str(self.__port),  # port
        ]
        args = [
            local_path,
            "{}@{}:{}".format(self.__user, self.__host, remote_path)
        ]
        self.__run_command(
            command="scp",
            flags=" ".join(flags),
            args=" ".join(args)
        )
