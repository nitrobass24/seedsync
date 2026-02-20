# Copyright 2017, Inderpreet Singh, All rights reserved.

import logging
import re
from functools import wraps
from typing import Callable, Union, List, Optional

# 3rd party libs
import pexpect

# my libs
from common import AppError
from .job_status_parser import LftpJobStatus, LftpJobStatusParser, LftpJobStatusParserError


# How many status errors are allowed before error propagates out
MAX_CONSECUTIVE_STATUS_ERRORS = 2

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
    __SET_NET_SOCKET_BUFFER = "net:socket-buffer"
    __SET_MIRROR_PARALLEL_DIRECTORIES = "mirror:parallel-directories"
    __SET_NET_TIMEOUT = "net:timeout"
    __SET_NET_MAX_RETRIES = "net:max-retries"
    __SET_NET_RECONNECT_INTERVAL_BASE = "net:reconnect-interval-base"
    __SET_NET_RECONNECT_INTERVAL_MULTIPLIER = "net:reconnect-interval-multiplier"

    def __init__(self,
                 address: str,
                 port: int,
                 user: str,
                 password: Optional[str]):
        self.__user = user
        self.__password = password
        self.__address = address
        self.__port = port
        self.__base_remote_dir_path = ""
        self.__base_local_dir_path = ""
        self.logger = logging.getLogger("Lftp")
        self.__expect_pattern = "lftp {}@{}:.*>".format(self.__user, self.__address)
        self.__job_status_parser = LftpJobStatusParser()
        self.__timeout = 10  # in seconds
        self.__consecutive_status_errors = 0
        self.__consecutive_timeouts = 0
        self.__settings_cache = {}

        self.__log_command_output = False
        self.__pending_error = None

        self.__process = None
        self.__spawn_process()

    def set_verbose_logging(self, verbose: bool):
        self.__log_command_output = verbose

    def __spawn_process(self):
        """
        Spawn a new lftp pexpect process and run initial setup
        """
        args = [
            "-p", str(self.__port),
            "-u", "{},{}".format(self.__user, self.__password if self.__password else ""),
            "sftp://{}".format(self.__address)
        ]
        self.__process = pexpect.spawn("/usr/bin/lftp", args)
        # Set a very wide terminal to prevent LFTP from wrapping long lines
        # in 'jobs -v' output. The default 80-column pty causes paths to wrap
        # mid-word, producing fragments the parser can't handle.
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
            self.__run_command("set {} {}".format(setting, value))
        self.__consecutive_timeouts = 0

    def __setup(self):
        """
        Setup the lftp instance with default settings
        :return:
        """
        # Set to kill on exit to prevent a zombie process
        self.__set(Lftp.__SET_COMMAND_AT_EXIT, "\"kill all\"")
        # Auto-add server to known host file
        self.sftp_auto_confirm = True

    def with_check_process(method: Callable):
        """
        Decorator that checks for a valid process before executing
        the decorated method. Attempts restart if process is dead.
        :param method:
        :return:
        """
        @wraps(method)
        def wrapper(inst: "Lftp", *args, **kwargs):
            if inst.__process is None or not inst.__process.isalive():
                try:
                    inst.__restart_process()
                except Exception:
                    raise LftpError("lftp process is not running and restart failed")
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
    def __run_command(self, command: str):
        if self.__log_command_output:
            self.logger.debug("command: {}".format(command.encode('utf8', 'surrogateescape')))
        self.__process.sendline(command)
        timed_out = False
        try:
            self.__process.expect(self.__expect_pattern, timeout=self.__timeout)
        except pexpect.exceptions.TIMEOUT:
            timed_out = True

        if timed_out:
            self.__consecutive_timeouts += 1
            self.logger.warning("Lftp timeout on command (consecutive timeouts: {})".format(
                self.__consecutive_timeouts))
            if self.__consecutive_timeouts >= MAX_CONSECUTIVE_TIMEOUTS:
                self.__restart_process()
                raise LftpError("lftp process restarted after {} consecutive timeouts".format(
                    MAX_CONSECUTIVE_TIMEOUTS))
            # Return empty string to prevent parsing corrupted buffer output
            return ""

        # Success — reset consecutive timeout counter
        self.__consecutive_timeouts = 0
        out = self.__process.before.decode('utf8', 'replace')
        out = out.strip()  # remove any CRs

        if self.__log_command_output:
            self.logger.debug("out ({} bytes):\n {}".format(len(out), out))
            after = self.__process.after.decode('utf8', 'replace').strip() \
                if self.__process.after != pexpect.TIMEOUT else ""
            self.logger.debug("after: {}".format(after))

        # let's try and detect some errors
        if self.__detect_errors_from_output(out):
            # we need to consume the actual output so that
            # it doesn't get passed onto next command
            error_out = out
            try:
                self.__process.expect(self.__expect_pattern, timeout=self.__timeout)
            except pexpect.exceptions.TIMEOUT:
                self.logger.warning("Lftp timeout while consuming error output")
                self.__pending_error = error_out
                return ""
            out = self.__process.before.decode('utf8', 'replace')
            out = out.strip()  # remove any CRs
            if self.__log_command_output:
                self.logger.debug("retry out ({} bytes):\n {}".format(len(out), out))
                after = self.__process.after.decode('utf8', 'replace').strip() \
                    if self.__process.after != pexpect.TIMEOUT else ""
                self.logger.debug("retry after: {}".format(after))
            self.logger.error("Lftp detected error: {}".format(error_out))
            # save pending error
            self.__pending_error = error_out
        return out

    @staticmethod
    def __detect_errors_from_output(out: str) -> bool:
        errors = [
            "pget: Access failed",
            "pget-chunk: Access failed",
            "mirror: Access failed",
            "Login failed: Login incorrect"
        ]
        for error in errors:
            if error in out:
                return True
        return False

    def __set(self, setting: str, value: str):
        """
        Set a setting in the lftp runtime
        :param setting:
        :param value:
        :return:
        """
        self.__settings_cache[setting] = value
        self.__run_command("set {} {}".format(setting, value))

    def __get(self, setting: str) -> str:
        """
        Get a setting from the lftp runtime
        :param setting:
        :return:
        """
        out = self.__run_command("set -a | grep {}".format(setting))
        m = re.search("set {} (.*)".format(setting), out)
        if not m or not m.group or not m.group(1):
            raise LftpError("Failed to get setting '{}'. Output: '{}'".format(setting, out))
        return m.group(1).strip()

    @staticmethod
    def __to_bool(value: str) -> bool:
        # sets are taken from LFTP manual
        if value.lower() in {"true", "on", "yes", "1", "+"}:
            return True
        elif value.lower() in {"false",  "off", "no", "0", "-"}:
            return False
        else:
            raise LftpError("Cannot convert value '{}' to boolean".format(value))

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
    def rate_limit(self, rate_limit: Union[int, str]):
        self.__set(Lftp.__SET_RATE_LIMIT, str(rate_limit))

    @property
    def min_chunk_size(self) -> str:
        return self.__get(Lftp.__SET_MIN_CHUNK_SIZE)

    @min_chunk_size.setter
    def min_chunk_size(self, min_chunk_size: Union[int, str]):
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

    def status(self) -> List[LftpJobStatus]:
        """
        Return a status list of queued and running jobs
        :return:
        """
        out = self.__run_command("jobs -v")
        try:
            statuses = self.__job_status_parser.parse(out)
            self.__consecutive_status_errors = 0
        except LftpJobStatusParserError:
            self.__consecutive_status_errors += 1
            if self.__consecutive_status_errors <= MAX_CONSECUTIVE_STATUS_ERRORS:
                self.logger.warning(f"Ignoring status error (count={self.__consecutive_status_errors})")
                statuses = []
            else:
                raise
        return statuses

    def queue(self, name: str, is_dir: bool):
        """
        Queues a job for download
        This method may cause an exception to be generated in a later method call:
          * Wrong type (is_dir) is specified
          * File/folder does not exist
        :param name: name of file or folder to download
        :param is_dir: true if folder, false if file
        :return:
        """
        # Escape single and double quotes in any string used in queue command
        def escape(s: str) -> str:
            return s.replace("'", "\\'").replace("\"", "\\\"")

        command = " ".join([
            "queue",
            "'",
            "pget" if not is_dir else "mirror",
            "-c",
            "\"{remote_dir}/{filename}\"".format(remote_dir=escape(self.__base_remote_dir_path),
                                                 filename=escape(name)),
            "-o" if not is_dir else "",
            "\"{local_dir}/\"".format(local_dir=escape(self.__base_local_dir_path)),
            "'"
        ])
        self.__run_command(command)

    def kill(self, name: str) -> bool:
        """
        Kill a queued or running job
        :param name:
        :return: True if job of given name was found, False otherwise
        """
        # look for this name in the status list
        job_to_kill = None
        for status in self.status():
            if status.name == name:
                job_to_kill = status
                break
        if job_to_kill is None:
            self.logger.debug("Kill failed to find job '{}'".format(name))
            return False
        # Note: there's a chance that job ids change between when we called status
        #       and when we execute the kill command
        #       in this case the wrong job may be killed, there's nothing we can do about it
        if job_to_kill.state == LftpJobStatus.State.RUNNING:
            self.logger.debug("Killing running job '{}'...".format(name))
            self.__run_command("kill {}".format(job_to_kill.id))
        elif job_to_kill.state == LftpJobStatus.State.QUEUED:
            self.logger.debug("Killing queued job '{}'...".format(name))
            self.__run_command("queue --delete {}".format(job_to_kill.id))
        else:
            raise NotImplementedError("Unsupported state {}".format(str(job_to_kill.state)))
        return True

    def kill_all(self):
        """
        Kills are jobs, queued or downloading
        :return:
        """
        # empty the queue and kill running jobs
        self.__run_command("queue -d *")
        self.__run_command("kill all")

    def exit(self):
        """
        Exit the lftp instance. It cannot be used after being killed
        :return:
        """
        self.kill_all()
        self.__process.sendline("exit")
        self.__process.close(force=True)

    # Mark decorators as static (must be at end of class)
    # Source: https://stackoverflow.com/a/3422823
    with_check_process = staticmethod(with_check_process)
