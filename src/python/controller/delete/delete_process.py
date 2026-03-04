# Copyright 2017, Inderpreet Singh, All rights reserved.

import os
import shutil
from typing import Optional

from common import AppOneShotProcess
from common import escape_remote_path_single, escape_remote_path_double
from ssh import Sshcp


class DeleteLocalProcess(AppOneShotProcess):
    def __init__(self, local_path: str, file_name: str):
        super().__init__(name=self.__class__.__name__)
        self.__local_path = local_path
        self.__file_name = file_name

    def run_once(self):
        file_path = os.path.join(self.__local_path, self.__file_name)
        # Path containment check: ensure resolved path is strictly inside local_path
        real_base = os.path.realpath(self.__local_path)
        real_target = os.path.realpath(file_path)
        try:
            common = os.path.commonpath([real_base, real_target])
        except ValueError:
            common = None
        if common != real_base or real_target == real_base:
            self.logger.error("Path traversal blocked: {} escapes {}".format(
                real_target, real_base))
            return
        self.logger.debug("Deleting local file {}".format(self.__file_name))
        if not os.path.exists(file_path):
            self.logger.error("Failed to delete non-existing file: {}".format(file_path))
        else:
            if os.path.isfile(file_path):
                os.remove(file_path)
            else:
                shutil.rmtree(file_path, ignore_errors=True)


class DeleteRemoteProcess(AppOneShotProcess):
    def __init__(self,
                 remote_address: str,
                 remote_username: str,
                 remote_password: Optional[str],
                 remote_port: int,
                 remote_path: str,
                 file_name: str):
        super().__init__(name=self.__class__.__name__)
        self.__remote_path = remote_path
        self.__file_name = file_name
        self.__ssh = Sshcp(host=remote_address,
                           port=remote_port,
                           user=remote_username,
                           password=remote_password)

    def run_once(self):
        self.__ssh.set_base_logger(self.logger)
        # Reject path traversal in filename (defense-in-depth)
        normalized = os.path.normpath(self.__file_name)
        if (not normalized or normalized == os.curdir or normalized == os.pardir
                or normalized.startswith(".." + os.sep) or os.path.isabs(normalized)):
            self.logger.error("Path traversal blocked in remote delete: {}".format(self.__file_name))
            return
        file_path = os.path.join(self.__remote_path, self.__file_name)
        self.logger.info("Deleting remote file: {}".format(self.__file_name))
        if file_path.startswith("~"):
            escaped_path = escape_remote_path_double(file_path)
        else:
            escaped_path = escape_remote_path_single(file_path)
        out = self.__ssh.shell("rm -rf {}".format(escaped_path))
        self.logger.debug("Remote delete output: {}".format(out.decode()))
        self.logger.info("Successfully deleted remote file: {}".format(self.__file_name))
