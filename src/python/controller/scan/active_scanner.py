# Copyright 2017, Inderpreet Singh, All rights reserved.

import logging
import multiprocessing
import queue

from common import overrides
from system import SystemFile, SystemScanner, SystemScannerError

from .scanner_process import IScanner


class ActiveScanner(IScanner):
    """
    Scanner implementation to scan the active files only
    A caller sets the names of the active files that need to be scanned.
    A multiprocessing.Queue is used to store the names because the set and scan
    methods are called by different processes.
    """

    def __init__(self, local_path: str, lftp_temp_suffix: str | None = None):
        self.__scanner = SystemScanner(local_path)
        if lftp_temp_suffix:
            self.__scanner.set_lftp_temp_suffix(lftp_temp_suffix)
        self.__active_files_queue = multiprocessing.Queue()
        self.__active_files = []  # latest state
        self.logger = logging.getLogger(self.__class__.__name__)

    @overrides(IScanner)
    def set_base_logger(self, base_logger: logging.Logger):
        self.logger = base_logger.getChild(self.__class__.__name__)

    def set_active_files(self, file_names: list[str]):
        """
        Set the list of active file names. Only these files will be scanned.
        :param file_names:
        :return:
        """
        self.__active_files_queue.put(file_names)

    def close(self):
        """Close multiprocessing resources."""
        self.__active_files_queue.close()
        self.__active_files_queue.join_thread()

    @overrides(IScanner)
    def scan(self) -> list[SystemFile]:
        # Grab the latest list of active files, if any
        try:
            while True:
                self.__active_files = self.__active_files_queue.get(block=False)
        except queue.Empty:
            pass

        # Do the scan
        # self.logger.debug("Scanning files: {}".format(str(self.__active_files)))
        result = []
        for file_name in self.__active_files:
            try:
                result.append(self.__scanner.scan_single(file_name))
            except SystemScannerError as ex:
                error_str = str(ex)
                if "does not exist" in error_str:
                    self.logger.debug(error_str)
                else:
                    self.logger.warning("Unexpected scan error for '{}': {}".format(file_name, error_str))
        return result
