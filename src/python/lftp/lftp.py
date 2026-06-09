# Copyright 2017, Inderpreet Singh, All rights reserved.

import logging
import os
import re
import warnings
from collections.abc import Callable
from functools import wraps
from typing import Any

# 3rd party libs
import pexpect

# my libs
from common import AppError

from .job_status_parser import (
    LftpJobStatus,
    LftpJobStatusParser,
    LftpJobStatusParserError,
    redact_credentials,
)

# How many consecutive status parse errors before error propagates out.
# Set high enough to ride out persistent lftp output quirks (e.g. Unraid
# PTY line-wrapping) without crashing the app.  At 0.5 s poll interval,
# 10 errors ≈ 5 seconds of degraded status before fatal.
MAX_CONSECUTIVE_STATUS_ERRORS = 10

# How many consecutive pexpect timeouts before we restart the lftp process
MAX_CONSECUTIVE_TIMEOUTS = 3


class LftpError(AppError):
    """
    Custom exception that describes the failure of the lftp command
    """

    pass


class Lftp:
    """
    Lftp command utility
    """

    __SET_NUM_PARALLEL_FILES = "mirror:parallel-transfer-count"
    __SET_NUM_CONNECTIONS_PGET = "pget:default-n"
    __SET_NUM_CONNECTIONS_MIRROR = "mirror:use-pget-n"
    __SET_NUM_MAX_TOTAL_CONNECTIONS = "net:connection-limit"
    __SET_RATE_LIMIT = "net:limit-rate"
    __SET_MIN_CHUNK_SIZE = "pget:min-chunk-size"
    __SET_NUM_PARALLEL_JOBS = "cmd:queue-parallel"
    __SET_MOVE_BACKGROUND_ON_EXIT = "cmd:move-background"
    __SET_COMMAND_AT_EXIT = "cmd:at-exit"
    __SET_USE_TEMP_FILE = "xfer:use-temp-file"
    __SET_TEMP_FILE_NAME = "xfer:temp-file-name"
    __SET_SFTP_AUTO_CONFIRM = "sftp:auto-confirm"
    __SET_SFTP_CONNECT_PROGRAM = "sftp:connect-program"
    __SET_SFTP_SET_PERMISSIONS = "sftp:set-permissions"
    __SET_NET_SOCKET_BUFFER = "net:socket-buffer"
    __SET_MIRROR_PARALLEL_DIRECTORIES = "mirror:parallel-directories"
    __SET_NET_TIMEOUT = "net:timeout"
    __SET_NET_MAX_RETRIES = "net:max-retries"
    __SET_NET_RECONNECT_INTERVAL_BASE = "net:reconnect-interval-base"
    __SET_NET_RECONNECT_INTERVAL_MULTIPLIER = "net:reconnect-interval-multiplier"
    __SET_XFER_VERIFY = "xfer:verify"
    __SET_XFER_VERIFY_COMMAND = "xfer:verify-command"
    # FTPS (explicit AUTH TLS over the ``ftp`` scheme) settings. lftp expresses
    # FTPS as the ``ftp`` scheme plus these toggles, not an ``ftps://`` URL.
    __SET_FTP_SSL_FORCE = "ftp:ssl-force"
    __SET_FTP_SSL_PROTECT_DATA = "ftp:ssl-protect-data"
    __SET_SSL_VERIFY_CERTIFICATE = "ssl:verify-certificate"
    __SET_FTP_SSL_AUTH = "ftp:ssl-auth"
    __SET_FTP_PASSIVE_MODE = "ftp:passive-mode"

    def __init__(
        self,
        address: str,
        port: int,
        user: str,
        password: str | None,
        protocol: str = "sftp",
        remote_ftp_port: int | None = None,
        ssl_verify_certificate: bool = False,
    ):
        self.__user = user
        self.__password = password
        self.__address = address
        # Transfer protocol. ``sftp`` (default) keeps the existing SSH-based
        # behavior; ``ftps`` switches the bulk transfer to FTP-over-TLS
        # (explicit AUTH TLS). The lftp URL scheme is ``ftp`` for FTPS.
        # Validate before deriving scheme/port so a typo fails fast instead of
        # silently downgrading (e.g. "ftp" -> sftp). The config layer's
        # protocol_allowed checker is the primary gate; this guards direct use.
        protocol = protocol.lower()
        if protocol not in ("sftp", "ftps"):
            raise ValueError(f"Invalid lftp protocol '{protocol}': must be 'sftp' or 'ftps'")
        self.__protocol = protocol
        self.__scheme = "ftp" if protocol == "ftps" else "sftp"
        self.__ssl_verify_certificate = ssl_verify_certificate
        # FTPS uses a dedicated transfer port (the SSH port is still used by the
        # scanner); fall back to the existing port when FTPS but no port given.
        if protocol == "ftps":
            self.__transfer_port = remote_ftp_port if remote_ftp_port is not None else port
        else:
            self.__transfer_port = port
        self.__base_remote_dir_path = ""
        self.__base_local_dir_path = ""
        self.logger = logging.getLogger("Lftp")
        self.__expect_pattern = f"lftp {self.__user}@{self.__address}:.*>"
        self.__job_status_parser = LftpJobStatusParser()
        self.__timeout = 10  # in seconds
        self.__consecutive_status_errors = 0
        self.__consecutive_timeouts = 0
        self.__settings_cache: dict[str, str] = {}

        self.__log_command_output = False
        self.__pending_error: str | None = None

        self.__process: pexpect.spawn | None = None  # type: ignore[type-arg]
        self.__spawn_process()

    def set_verbose_logging(self, verbose: bool):
        self.__log_command_output = verbose

    def __spawn_process(self):
        """
        Spawn a new lftp pexpect process and run initial setup
        """
        args = [
            "-p",
            str(self.__transfer_port),
            "-u",
            "{},{}".format(self.__user, self.__password if self.__password else ""),
            f"{self.__scheme}://{self.__address}",
        ]
        # Force a wide terminal so LFTP never wraps 'jobs -v' output.
        # Belt-and-suspenders: set COLUMNS in the environment (which LFTP
        # and libc may read) AND call setwinsize on the PTY fd.  Unraid's
        # Docker layer can override PTY dimensions, so the env var covers
        # that case.
        spawn_env = os.environ.copy()
        spawn_env["COLUMNS"] = "10000"
        # Suppress DeprecationWarning from pexpect.spawn's internal forkpty call.
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message=".*fork.*", category=DeprecationWarning)
            self.__process = pexpect.spawn("/usr/bin/lftp", args, env=spawn_env)  # type: ignore[arg-type]
        self.__process.setwinsize(24, 10000)
        self.__process.expect(self.__expect_pattern)
        self.__setup()

    def __restart_process(self):
        """
        Force-close the existing lftp process and start a fresh one,
        replaying all cached settings
        """
        self.logger.warning("Restarting lftp process")
        if self.__process is not None and self.__process.isalive():
            self.__process.close(force=True)
        self.__spawn_process()
        # Replay cached settings
        for setting, value in self.__settings_cache.items():
            self.__run_command(f"set {setting} {value}")  # type: ignore[arg-type]
        self.__consecutive_timeouts = 0

    def __setup(self):
        """
        Setup the lftp instance with default settings
        :return:
        """
        # Set to kill on exit to prevent a zombie process
        self.__set(Lftp.__SET_COMMAND_AT_EXIT, '"kill all"')
        if self.__protocol == "ftps":
            self.__setup_ftps()
        else:
            self.__setup_sftp()

    def __setup_sftp(self):
        """SFTP-specific runtime settings (the historical default behavior)."""
        # Auto-add server to known host file
        self.sftp_auto_confirm = True
        # Do not copy remote file permissions — let the local umask determine
        # the permissions of downloaded files instead of preserving the seedbox's
        # permission bits (e.g. 664 → remote) which would override our umask setting
        self.__set(Lftp.__SET_SFTP_SET_PERMISSIONS, "false")

    def __setup_ftps(self):
        """FTPS-specific runtime settings (FTP-over-TLS, explicit AUTH TLS).

        The control channel and the data channel are both TLS-encrypted
        (``ssl-force`` + ``ssl-protect-data`` are hardcoded ON — this is FTPS,
        never cleartext FTP). Certificate verification is configurable and
        defaults OFF; when it is off we emit a WARNING so the downgrade (TLS
        encryption without authentication → MITM risk) is never silent.

        After issuing the settings we fail-closed: read ``ftp:ssl-force`` back
        and raise if it is not ``true`` so we never silently fall back to
        cleartext.
        """
        # Force TLS on the control connection (the FTPS handshake) and encrypt
        # the data channel. Both are hardcoded ON.
        self.__set(Lftp.__SET_FTP_SSL_FORCE, "true")
        self.__set(Lftp.__SET_FTP_SSL_PROTECT_DATA, "true")
        # Certificate verification (configurable; default OFF for seedboxes
        # with self-signed / mismatched certs).
        self.__set(Lftp.__SET_SSL_VERIFY_CERTIFICATE, "true" if self.__ssl_verify_certificate else "false")
        if not self.__ssl_verify_certificate:
            self.logger.warning(
                "FTPS TLS certificate verification is DISABLED "
                "(ssl:verify-certificate off) — the connection is encrypted but "
                "NOT authenticated, exposing it to man-in-the-middle attacks. "
                "Enable ftp_ssl_verify_certificate once your seedbox has a "
                "properly-issued certificate."
            )
        # Explicit FTPS: AUTH TLS before login.
        self.__set(Lftp.__SET_FTP_SSL_AUTH, "TLS")
        # Passive mode (firewall/NAT friendly; the data connection is opened
        # from the client out to the server).
        self.__set(Lftp.__SET_FTP_PASSIVE_MODE, "true")
        # Fail-closed: confirm TLS really is forced before any transfer runs.
        self.__verify_ftps_ssl_forced()

    def __verify_ftps_ssl_forced(self):
        """Read ``ftp:ssl-force`` back from the live lftp and raise LftpError if
        it is not enabled, so we never silently fall back to cleartext FTP."""
        try:
            ssl_force = Lftp.__to_bool(self.__get(Lftp.__SET_FTP_SSL_FORCE))
        except LftpError as e:
            raise LftpError(f"FTPS fail-closed check could not read ftp:ssl-force: {e}") from e
        if not ssl_force:
            raise LftpError(
                "FTPS fail-closed check failed: ftp:ssl-force is not enabled — refusing to transfer over cleartext FTP"
            )

    def with_check_process(method: Callable[..., Any]) -> Callable[..., Any]:  # type: ignore[override]
        """
        Decorator that checks for a valid process before executing
        the decorated method. Attempts restart if process is dead.
        :param method:
        :return:
        """

        @wraps(method)
        def wrapper(inst: "Lftp", *args: Any, **kwargs: Any) -> Any:
            if inst.__process is None or not inst.__process.isalive():
                try:
                    inst.__restart_process()
                except Exception as e:
                    # Preserve the underlying reason — e.g. the FTPS fail-closed
                    # "ftp:ssl-force is not enabled" raised during the restart's
                    # __setup — instead of swallowing it.
                    raise LftpError(f"lftp process is not running and restart failed: {e}") from e
            return method(inst, *args, **kwargs)

        return wrapper

    def set_base_logger(self, base_logger: logging.Logger):
        self.logger = base_logger.getChild("Lftp")
        self.__job_status_parser.set_base_logger(self.logger)

    def set_base_remote_dir_path(self, base_remote_dir_path: str):
        self.__base_remote_dir_path = base_remote_dir_path

    def set_base_local_dir_path(self, base_local_dir_path: str):
        self.__base_local_dir_path = base_local_dir_path

    def raise_pending_error(self):
        """
        Raise any pending errors
        Errors show up late after a command is executed
        This method raises any errors that were detected while executing the next command
        :return:
        """
        if self.__pending_error:
            error = self.__pending_error
            self.__pending_error = None
            raise LftpError(error)

    @with_check_process
    def __run_command(self, command: str):  # type: ignore[arg-type]
        assert self.__process is not None
        if self.__log_command_output:
            self.logger.debug("command: {}".format(command.encode("utf8", "surrogateescape")))
        self.__process.sendline(command)
        timed_out = False
        try:
            self.__process.expect(self.__expect_pattern, timeout=self.__timeout)
        except pexpect.exceptions.TIMEOUT:
            timed_out = True

        if timed_out:
            self.__consecutive_timeouts += 1
            self.logger.warning(f"Lftp timeout on command (consecutive timeouts: {self.__consecutive_timeouts})")
            if self.__consecutive_timeouts >= MAX_CONSECUTIVE_TIMEOUTS:
                self.__restart_process()
                raise LftpError(f"lftp process restarted after {MAX_CONSECUTIVE_TIMEOUTS} consecutive timeouts")
            # Return empty string to prevent parsing corrupted buffer output
            return ""

        # Success — reset consecutive timeout counter
        self.__consecutive_timeouts = 0
        before = self.__process.before
        assert isinstance(before, bytes)
        out = before.decode("utf8", "replace")
        out = out.strip()  # remove any CRs

        if self.__log_command_output:
            self.logger.debug(f"out ({len(out)} bytes):\n {redact_credentials(out)}")
            after_val = self.__process.after
            if isinstance(after_val, bytes):
                after = after_val.decode("utf8", "replace").strip()
            else:
                after = ""
            self.logger.debug(f"after: {after}")

        # let's try and detect some errors
        if self.__detect_errors_from_output(out):
            # we need to consume the actual output so that
            # it doesn't get passed onto next command
            error_out = out
            try:
                self.__process.expect(self.__expect_pattern, timeout=self.__timeout)
            except pexpect.exceptions.TIMEOUT:
                self.logger.warning("Lftp timeout while consuming error output")
                self.__pending_error = redact_credentials(error_out)
                return ""
            before = self.__process.before
            assert isinstance(before, bytes)
            out = before.decode("utf8", "replace")
            out = out.strip()  # remove any CRs
            if self.__log_command_output:
                self.logger.debug(f"retry out ({len(out)} bytes):\n {redact_credentials(out)}")
                after_val = self.__process.after
                if isinstance(after_val, bytes):
                    after = after_val.decode("utf8", "replace").strip()
                else:
                    after = ""
                self.logger.debug(f"retry after: {after}")
            self.logger.error(f"Lftp detected error: {redact_credentials(error_out)}")
            # save pending error (redacted — raise_pending_error re-raises this text)
            self.__pending_error = redact_credentials(error_out)
        return out

    @staticmethod
    def __detect_errors_from_output(out: str) -> bool:
        errors = [
            "pget: Access failed",
            "pget-chunk: Access failed",
            "mirror: Access failed",
            # Protocol-agnostic: matches the SFTP-synthesized "Login failed: Login
            # incorrect" and every FTP-530 variant ("Login failed: 530 ...").
            "Login failed:",
            # FTPS / TLS failures (control or data channel)
            "Fatal error: gnutls_handshake",
            "Fatal error: SSL_connect",
            "TLS/SSL connection error",
            "Certificate verification",
            "certificate verification",
            "AUTH TLS failed",
            "Make data connection: error",
            "data connection: timeout",
            "PASV: timeout",
        ]
        return any(error in out for error in errors)

    def __set(self, setting: str, value: str):
        """
        Set a setting in the lftp runtime
        :param setting:
        :param value:
        :return:
        """
        self.__settings_cache[setting] = value
        self.__run_command(f"set {setting} {value}")  # type: ignore[arg-type]

    def __get(self, setting: str) -> str:
        """
        Get a setting from the lftp runtime
        :param setting:
        :return:
        """
        out = self.__run_command(f"set -a | grep {setting}")  # type: ignore[arg-type]
        m = re.search(f"set {setting} (.*)", out)
        if not m or not m.group or not m.group(1):  # type: ignore[reportUnnecessaryComparison]
            raise LftpError(f"Failed to get setting '{setting}'. Output: '{out}'")
        return m.group(1).strip()

    @staticmethod
    def __to_bool(value: str) -> bool:
        # sets are taken from LFTP manual
        if value.lower() in {"true", "on", "yes", "1", "+"}:
            return True
        if value.lower() in {"false", "off", "no", "0", "-"}:
            return False
        raise LftpError(f"Cannot convert value '{value}' to boolean")

    @property
    def num_connections_per_dir_file(self) -> int:
        return int(self.__get(Lftp.__SET_NUM_CONNECTIONS_MIRROR))

    @num_connections_per_dir_file.setter
    def num_connections_per_dir_file(self, num_connections: int):
        if num_connections < 1:
            raise ValueError("Number of connections must be positive")
        self.__set(Lftp.__SET_NUM_CONNECTIONS_MIRROR, str(num_connections))

    @property
    def num_connections_per_root_file(self) -> int:
        return int(self.__get(Lftp.__SET_NUM_CONNECTIONS_PGET))

    @num_connections_per_root_file.setter
    def num_connections_per_root_file(self, num_connections: int):
        if num_connections < 1:
            raise ValueError("Number of connections must be positive")
        self.__set(Lftp.__SET_NUM_CONNECTIONS_PGET, str(num_connections))

    @property
    def num_max_total_connections(self) -> int:
        return int(self.__get(Lftp.__SET_NUM_MAX_TOTAL_CONNECTIONS))

    @num_max_total_connections.setter
    def num_max_total_connections(self, num_connections: int):
        if num_connections < 0:
            raise ValueError("Number of connections must be zero or greater")
        self.__set(Lftp.__SET_NUM_MAX_TOTAL_CONNECTIONS, str(num_connections))

    @property
    def num_parallel_files(self) -> int:
        return int(self.__get(Lftp.__SET_NUM_PARALLEL_FILES))

    @num_parallel_files.setter
    def num_parallel_files(self, num_parallel_files: int):
        if num_parallel_files < 1:
            raise ValueError("Number of parallel files must be positive")
        self.__set(Lftp.__SET_NUM_PARALLEL_FILES, str(num_parallel_files))

    @property
    def rate_limit(self) -> str:
        return self.__get(Lftp.__SET_RATE_LIMIT)

    @rate_limit.setter
    def rate_limit(self, rate_limit: int | str):
        self.__set(Lftp.__SET_RATE_LIMIT, str(rate_limit))

    @property
    def min_chunk_size(self) -> str:
        return self.__get(Lftp.__SET_MIN_CHUNK_SIZE)

    @min_chunk_size.setter
    def min_chunk_size(self, min_chunk_size: int | str):
        self.__set(Lftp.__SET_MIN_CHUNK_SIZE, str(min_chunk_size))

    @property
    def num_parallel_jobs(self) -> int:
        return int(self.__get(Lftp.__SET_NUM_PARALLEL_JOBS))

    @num_parallel_jobs.setter
    def num_parallel_jobs(self, num_parallel_jobs: int):
        if num_parallel_jobs < 1:
            raise ValueError("Number of parallel jobs must be positive")
        self.__set(Lftp.__SET_NUM_PARALLEL_JOBS, str(num_parallel_jobs))

    @property
    def move_background_on_exit(self) -> bool:
        return Lftp.__to_bool(self.__get(Lftp.__SET_MOVE_BACKGROUND_ON_EXIT))

    @move_background_on_exit.setter
    def move_background_on_exit(self, move_background_on_exit: bool):
        self.__set(Lftp.__SET_MOVE_BACKGROUND_ON_EXIT, str(int(move_background_on_exit)))

    @property
    def use_temp_file(self) -> bool:
        return Lftp.__to_bool(self.__get(Lftp.__SET_USE_TEMP_FILE))

    @use_temp_file.setter
    def use_temp_file(self, use_temp_file: bool):
        self.__set(Lftp.__SET_USE_TEMP_FILE, str(int(use_temp_file)))

    @property
    def temp_file_name(self) -> str:
        return self.__get(Lftp.__SET_TEMP_FILE_NAME)

    @temp_file_name.setter
    def temp_file_name(self, temp_file_name: str):
        self.__set(Lftp.__SET_TEMP_FILE_NAME, temp_file_name)

    @property
    def sftp_auto_confirm(self) -> bool:
        return Lftp.__to_bool(self.__get(Lftp.__SET_SFTP_AUTO_CONFIRM))

    @sftp_auto_confirm.setter
    def sftp_auto_confirm(self, auto_confirm: bool):
        self.__set(Lftp.__SET_SFTP_AUTO_CONFIRM, str(int(auto_confirm)))

    @property
    def sftp_connect_program(self) -> str:
        return self.__get(Lftp.__SET_SFTP_CONNECT_PROGRAM)

    @sftp_connect_program.setter
    def sftp_connect_program(self, program: str):
        self.__set(Lftp.__SET_SFTP_CONNECT_PROGRAM, program)

    @property
    def net_socket_buffer(self) -> str:
        return self.__get(Lftp.__SET_NET_SOCKET_BUFFER)

    @net_socket_buffer.setter
    def net_socket_buffer(self, value: str):
        self.__set(Lftp.__SET_NET_SOCKET_BUFFER, value)

    @property
    def mirror_parallel_directories(self) -> bool:
        return Lftp.__to_bool(self.__get(Lftp.__SET_MIRROR_PARALLEL_DIRECTORIES))

    @mirror_parallel_directories.setter
    def mirror_parallel_directories(self, value: bool):
        self.__set(Lftp.__SET_MIRROR_PARALLEL_DIRECTORIES, str(int(value)))

    @property
    def net_timeout(self) -> int:
        return int(self.__get(Lftp.__SET_NET_TIMEOUT))

    @net_timeout.setter
    def net_timeout(self, value: int):
        if value < 0:
            raise ValueError("Network timeout must be zero or greater")
        self.__set(Lftp.__SET_NET_TIMEOUT, str(value))

    @property
    def net_max_retries(self) -> int:
        return int(self.__get(Lftp.__SET_NET_MAX_RETRIES))

    @net_max_retries.setter
    def net_max_retries(self, value: int):
        if value < 0:
            raise ValueError("Max retries must be zero or greater")
        self.__set(Lftp.__SET_NET_MAX_RETRIES, str(value))

    @property
    def net_reconnect_interval_base(self) -> int:
        return int(self.__get(Lftp.__SET_NET_RECONNECT_INTERVAL_BASE))

    @net_reconnect_interval_base.setter
    def net_reconnect_interval_base(self, value: int):
        if value < 0:
            raise ValueError("Reconnect interval base must be zero or greater")
        self.__set(Lftp.__SET_NET_RECONNECT_INTERVAL_BASE, str(value))

    @property
    def net_reconnect_interval_multiplier(self) -> int:
        return int(self.__get(Lftp.__SET_NET_RECONNECT_INTERVAL_MULTIPLIER))

    @net_reconnect_interval_multiplier.setter
    def net_reconnect_interval_multiplier(self, value: int):
        if value < 0:
            raise ValueError("Reconnect interval multiplier must be zero or greater")
        self.__set(Lftp.__SET_NET_RECONNECT_INTERVAL_MULTIPLIER, str(value))

    @property
    def xfer_verify(self) -> bool:
        return Lftp.__to_bool(self.__get(Lftp.__SET_XFER_VERIFY))

    @xfer_verify.setter
    def xfer_verify(self, value: bool):
        self.__set(Lftp.__SET_XFER_VERIFY, str(int(value)))

    @property
    def xfer_verify_command(self) -> str:
        return self.__get(Lftp.__SET_XFER_VERIFY_COMMAND)

    @xfer_verify_command.setter
    def xfer_verify_command(self, command: str):
        self.__set(Lftp.__SET_XFER_VERIFY_COMMAND, command)

    def status(self) -> list[LftpJobStatus] | None:
        """
        Return a status list of queued and running jobs.
        Returns None when the status output could not be parsed, so callers
        can distinguish "no jobs" from "parse failed" and avoid false
        completion signals.
        :return:
        """
        out = self.__run_command("jobs -v")  # type: ignore[arg-type]
        try:
            statuses = self.__job_status_parser.parse(out)
            self.__consecutive_status_errors = 0
        except LftpJobStatusParserError:
            self.__consecutive_status_errors += 1
            if self.__consecutive_status_errors < MAX_CONSECUTIVE_STATUS_ERRORS:
                self.logger.warning(f"Ignoring status error (count={self.__consecutive_status_errors})")
                return None
            raise
        return statuses

    def queue(self, name: str, is_dir: bool, exclude_patterns: list[str] | None = None):
        """
        Queues a job for download
        This method may cause an exception to be generated in a later method call:
          * Wrong type (is_dir) is specified
          * File/folder does not exist
        :param name: name of file or folder to download
        :param is_dir: true if folder, false if file
        :param exclude_patterns: list of glob patterns to exclude (only applies to mirror/directory downloads)
        :return:
        """

        # Escape single and double quotes in any string used in queue command
        def escape(s: str) -> str:
            return s.replace("'", "\\'").replace('"', '\\"')

        # Build --exclude-glob flags for mirror commands
        # Note: LFTP's --exclude uses regex; --exclude-glob uses glob patterns
        exclude_flags = ""
        if is_dir and exclude_patterns:
            exclude_flags = " ".join(f'--exclude-glob "{escape(p)}"' for p in exclude_patterns)

        parts = [
            "queue",
            "'",
            "pget" if not is_dir else "mirror",
            "-c",
        ]
        if exclude_flags:
            parts.append(exclude_flags)
        parts.extend(
            [
                f'"{escape(self.__base_remote_dir_path)}/{escape(name)}"',
                "-o" if not is_dir else "",
                f'"{escape(self.__base_local_dir_path)}/"',
                "'",
            ]
        )
        command = " ".join(parts)
        self.logger.info("queue command: %s", command)
        self.__run_command(command)  # type: ignore[arg-type]

    def kill(self, name: str) -> bool:
        """
        Kill a queued or running job
        :param name:
        :return: True if job of given name was found, False otherwise
        """
        # look for this name in the status list
        job_to_kill = None
        statuses = self.status()
        if statuses is None:
            self.logger.debug(f"Kill failed - status unavailable for job '{name}'")
            return False
        for status in statuses:
            if status.name == name:
                job_to_kill = status
                break
        if job_to_kill is None:
            self.logger.debug(f"Kill failed to find job '{name}'")
            return False
        # Note: there's a chance that job ids change between when we called status
        #       and when we execute the kill command
        #       in this case the wrong job may be killed, there's nothing we can do about it
        if job_to_kill.state == LftpJobStatus.State.RUNNING:
            self.logger.debug(f"Killing running job '{name}'...")
            self.__run_command(f"kill {job_to_kill.id}")  # type: ignore[arg-type]
        elif job_to_kill.state == LftpJobStatus.State.QUEUED:
            self.logger.debug(f"Killing queued job '{name}'...")
            self.__run_command(f"queue --delete {job_to_kill.id}")  # type: ignore[arg-type]
        else:
            raise NotImplementedError(f"Unsupported state {job_to_kill.state!s}")
        return True

    def kill_all(self):
        """
        Kills are jobs, queued or downloading
        :return:
        """
        # empty the queue and kill running jobs
        self.__run_command("queue -d *")  # type: ignore[arg-type]
        self.__run_command("kill all")  # type: ignore[arg-type]

    def exit(self):
        """
        Exit the lftp instance. It cannot be used after being killed
        :return:
        """
        self.kill_all()
        assert self.__process is not None
        self.__process.sendline("exit")
        self.__process.close(force=True)

    # Mark decorators as static (must be at end of class)
    # Source: https://stackoverflow.com/a/3422823
    with_check_process = staticmethod(with_check_process)  # type: ignore[arg-type]
