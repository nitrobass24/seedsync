# Copyright 2017, Inderpreet Singh, All rights reserved.

import logging
import time
import warnings

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

    def __init__(self, host: str, port: int, user: str | None = None, password: str | None = None):
        self.__host = host
        self.__port = port
        self.__user = user
        self.__password = password
        self.__detected_shell: str | None = None
        self.__shell_detected: bool = False
        self.logger = logging.getLogger(self.__class__.__name__)

    def _remote_address(self) -> str:
        """Return 'user@host' when user is set, or just 'host' when None."""
        if self.__user is not None:
            return f"{self.__user}@{self.__host}"
        return self.__host

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
            assert self.__detected_shell is not None
            return self.__detected_shell

        self.logger.debug("Detecting remote shell...")

        # Try running a simple command to test the login shell
        try:
            self._run_shell_command("echo __shell_ok__")
            # Login shell works fine - detect which shell it is
            try:
                out = self._run_shell_command(
                    "echo __shell_path__$(which bash 2>/dev/null || which sh 2>/dev/null || echo unknown)__end__"
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
            self.logger.info(f"Detected remote shell: {self.__detected_shell}")
            return self.__detected_shell

        except SshcpError as e:
            error_str = str(e)
            if "No such file or directory" not in error_str:
                # Not a shell-not-found error - re-raise as-is
                raise

            # Login shell is broken. Use SFTP to check which shells exist.
            self.logger.warning("Login shell not found on remote server. Checking for available shells via SFTP...")

            available_shells = self._check_remote_shells_via_sftp()

            if available_shells:
                shells_str = ", ".join(available_shells)
                raise SshcpError(
                    "Remote user's login shell not found. "
                    f"Available shells on the remote server: {shells_str}. "
                    "Fix by running on the remote server: "
                    f"sudo chsh -s {available_shells[0]} {self.__user}"
                ) from e
            raise SshcpError(
                "Remote user's login shell not found and no common shells "
                "could be detected. Fix by running on the remote server: "
                f"sudo chsh -s /bin/sh {self.__user} OR "
                "sudo ln -s /usr/bin/bash /bin/bash"
            ) from e

    def _run_shell_command(self, command: str) -> bytes:
        """
        Run a shell command via SSH without going through the public shell()
        method's quoting logic. Used internally for shell detection.
        """
        # Quote the command
        if '"' in command:
            quoted = f"'{command}'"
        else:
            quoted = f'"{command}"'

        flags = [
            "-p",
            str(self.__port),
        ]
        args = [self._remote_address(), quoted]
        return self.__run_command(command="ssh", flags=" ".join(flags), args=" ".join(args))

    def _check_remote_shells_via_sftp(self) -> list[str]:
        """
        Check which shell binaries exist on the remote server using SFTP.
        SFTP does not require a working login shell.
        Returns a list of available shell paths.
        """
        available: list[str] = []
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
            "-P",
            str(self.__port),
            "-o",
            "BatchMode=yes",
        ]

        # Use sftp batch mode to run 'ls' on the path
        args = [
            "-b",
            "-",  # read commands from stdin
            self._remote_address(),
        ]

        command_args = ["sftp"]
        command_args += [
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            "UserKnownHostsFile=/dev/null",
            "-o",
            "LogLevel=error",
        ]

        if self.__password is None:
            command_args += ["-o", "PasswordAuthentication=no"]
        else:
            command_args += ["-o", "PubkeyAuthentication=no"]

        command_args += flags
        command_args += args

        command = " ".join(command_args)
        self.logger.debug(f"SFTP stat command: {command}")

        # Suppress DeprecationWarning from pexpect.spawn's internal forkpty call.
        # Scoped here so it doesn't affect the parent process.
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message=".*fork.*", category=DeprecationWarning)
            sp = pexpect.spawn(command)
        try:
            if self.__password is not None:
                i = sp.expect(
                    [
                        "password: ",
                        pexpect.EOF,
                    ],
                    timeout=30,
                )
                if i == 1:
                    sp.close()
                    raise SshcpError("SFTP connection failed")
                sp.sendline(self.__password)

            # Wait for sftp prompt
            i = sp.expect(
                [
                    "sftp>",
                    pexpect.EOF,
                    "password: ",
                ],
                timeout=30,
            )
            if i != 0:
                sp.close()
                raise SshcpError("SFTP connection failed")

            # Send ls command to check if file exists
            sp.sendline(f"ls {remote_path}")
            i = sp.expect(
                [
                    "sftp>",
                    pexpect.EOF,
                ],
                timeout=30,
            )

            output = sp.before.decode() if sp.before else ""
            sp.sendline("bye")
            sp.expect(pexpect.EOF, timeout=10)
            sp.close()

            if "No such file" in output or "not found" in output or "Can't ls" in output:
                raise SshcpError(f"File not found: {remote_path}")

        except pexpect.exceptions.TIMEOUT:
            sp.close()
            raise SshcpError("SFTP timed out") from None

    def __run_command(self, command: str, flags: str, args: str) -> bytes:
        command_args = [command, flags]

        # Common flags
        command_args += [
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            "UserKnownHostsFile=/dev/null",
            "-o",
            "LogLevel=error",
            "-o",
            "ConnectTimeout=30",
            "-o",
            "ServerAliveInterval=15",
            "-o",
            "ServerAliveCountMax=3",
        ]

        if self.__password is None:
            command_args += ["-o", "PasswordAuthentication=no"]
        else:
            command_args += ["-o", "PubkeyAuthentication=no"]

        command_args.append(args)
        command = " ".join(command_args)
        self.logger.debug(f"Command: {command}")

        start_time = time.time()
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message=".*fork.*", category=DeprecationWarning)
            sp = pexpect.spawn(command)
        try:
            if self.__password is not None:
                i = sp.expect(
                    [
                        "password: ",
                        pexpect.EOF,
                        "lost connection",
                        "Could not resolve hostname",
                        "Connection refused",
                    ]
                )
                self._classify_expect_result(sp, i, eof_error="Unknown error", password_error=None)
                sp.sendline(self.__password)

            i = sp.expect(
                [pexpect.EOF, "password: ", "lost connection", "Could not resolve hostname", "Connection refused"],
                timeout=self.__TIMEOUT_SECS,
            )
            self._classify_expect_result(sp, i, eof_error=None, password_error="Incorrect password")

            before_val = sp.before
            after_val = sp.after
            out_before = before_val.decode(errors="replace").strip() if isinstance(before_val, bytes) else ""
            out_after = after_val.decode(errors="replace").strip() if isinstance(after_val, bytes) else ""
            assert isinstance(before_val, bytes)
            out_raw = before_val.replace(b"\r\n", b"\n").strip()

        except pexpect.exceptions.TIMEOUT:
            elapsed = time.time() - start_time
            self.logger.error(f"Timed out after {elapsed:.0f}s (limit: {self.__TIMEOUT_SECS}s). Command: {command}")
            self.logger.error(f"Command output before timeout: {sp.before if sp.before else b'(none)'}")
            raise SshcpError(f"Timed out after {elapsed:.0f}s") from None
        finally:
            sp.close()

        exit_status = sp.exitstatus
        end_time = time.time()

        self.logger.debug(f"Return code: {exit_status}")
        self.logger.debug(f"Command took {end_time - start_time:.3f}s")
        if exit_status != 0:
            self.logger.warning(f"Command failed: '{out_before} - {out_after}'")
            self._check_shell_not_found(out_before)
            raise SshcpError(out_before)

        return out_raw

    def _classify_expect_result(
        self, sp: pexpect.spawn, i: int, eof_error: str | None, password_error: str | None
    ) -> None:
        """Classify the result of a pexpect expect() call and raise on error.

        Args:
            sp: The pexpect spawn instance.
            i: The index returned by expect().
               0 = success (password prompt or EOF depending on phase).
               1 = EOF/password prompt (error).
               2 = lost connection.
               3 = bad hostname.
               4 = connection refused.
            eof_error: Error message for i=1 (EOF in phase 1, password in phase 2).
                       None means i=0 is the success case.
            password_error: Error message for i=1 when it's a password prompt.
        """
        if i == 0:
            return
        # Log the failure
        before_val = sp.before
        after_val = sp.after
        before = before_val.decode(errors="replace").strip() if isinstance(before_val, bytes) else ""
        after = after_val.decode(errors="replace").strip() if isinstance(after_val, bytes) else ""
        self.logger.warning(f"Command failed: '{before} - {after}'")

        if i == 1:
            if eof_error is not None:
                msg = eof_error
                if before:
                    msg += " - " + before
                raise SshcpError(msg)
            if password_error is not None:
                raise SshcpError(password_error)
        if i == 3:
            raise SshcpError(f"Bad hostname: {self.__host}")
        if i in {2, 4}:
            msg = "Connection refused by server"
            if before:
                msg += " - " + before
            raise SshcpError(msg)

    def _check_shell_not_found(self, output: str) -> None:
        """Check if a command failure is due to a missing login shell."""
        if "No such file or directory" not in output:
            return
        for shell in self.SHELL_CANDIDATES:
            if shell in output:
                raise SshcpError(
                    f"Remote user's login shell not found: {shell}. "
                    "Run detect_shell() or fix by running on the remote server: "
                    f"sudo chsh -s /bin/sh {self.__user}"
                )

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
            command = f"'{command}'"
        else:
            # no quotes in command, cover with double quotes
            command = f'"{command}"'

        flags = [
            "-p",
            str(self.__port),  # port
        ]
        args = [self._remote_address(), command]
        return self.__run_command(command="ssh", flags=" ".join(flags), args=" ".join(args))

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
            "-P",
            str(self.__port),  # port
        ]
        args = [local_path, f"{self._remote_address()}:{remote_path}"]
        self.__run_command(command="scp", flags=" ".join(flags), args=" ".join(args))
