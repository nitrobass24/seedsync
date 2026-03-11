# Copyright 2017, Inderpreet Singh, All rights reserved.

import multiprocessing
import datetime
import time
import hashlib
import os
import queue
from enum import Enum
from typing import Optional, List
import logging

from common import overrides, AppProcess


class ValidateRequest:
    """Request to validate a file by comparing local and remote checksums."""
    def __init__(self, name: str, is_dir: bool, pair_id: str,
                 local_path: str, remote_path: str, algorithm: str,
                 remote_address: str, remote_username: str,
                 remote_password: Optional[str], remote_port: int):
        self.name = name
        self.is_dir = is_dir
        self.pair_id = pair_id
        self.local_path = local_path
        self.remote_path = remote_path
        self.algorithm = algorithm
        self.remote_address = remote_address
        self.remote_username = remote_username
        self.remote_password = remote_password
        self.remote_port = remote_port


class ValidateStatus:
    """Status of an in-progress validation."""
    class State(Enum):
        VALIDATING = 0

    def __init__(self, name: str, is_dir: bool, state: "ValidateStatus.State"):
        self.name = name
        self.is_dir = is_dir
        self.state = state


class ValidateStatusResult:
    def __init__(self, timestamp: datetime.datetime, statuses: List[ValidateStatus]):
        self.timestamp = timestamp
        self.statuses = statuses


class ValidateCompletedResult:
    def __init__(self, timestamp: datetime.datetime, name: str, is_dir: bool, pair_id: str = None):
        self.timestamp = timestamp
        self.name = name
        self.is_dir = is_dir
        self.pair_id = pair_id


class ValidateFailedResult:
    def __init__(self, timestamp: datetime.datetime, name: str, is_dir: bool,
                 pair_id: str = None, error_message: str = None):
        self.timestamp = timestamp
        self.name = name
        self.is_dir = is_dir
        self.pair_id = pair_id
        self.error_message = error_message


class ValidateProcess(AppProcess):
    """Process to validate file integrity by comparing local and remote checksums."""
    __DEFAULT_SLEEP_INTERVAL_IN_SECS = 0.5

    def __init__(self):
        super().__init__(name=self.__class__.__name__)
        self.__command_queue = multiprocessing.Queue()
        self.__status_result_queue = multiprocessing.Queue()
        self.__completed_result_queue = multiprocessing.Queue()
        self.__failed_result_queue = multiprocessing.Queue()
        self.__active_validations = {}  # name -> ValidateRequest

    @overrides(AppProcess)
    def run_init(self):
        pass

    @overrides(AppProcess)
    def run_cleanup(self):
        pass

    @overrides(AppProcess)
    def run_loop(self):
        # Pick up new validation requests
        try:
            while True:
                req = self.__command_queue.get(block=False)
                if req.name in self.__active_validations:
                    self.logger.warning("Validation already in progress for {}".format(req.name))
                    continue
                self.__active_validations[req.name] = req
        except queue.Empty:
            pass

        # Process one validation at a time (blocking but in child process)
        if self.__active_validations:
            name, req = next(iter(self.__active_validations.items()))
            try:
                self._validate_file(req)
                completed = ValidateCompletedResult(
                    timestamp=datetime.datetime.now(),
                    name=req.name,
                    is_dir=req.is_dir,
                    pair_id=req.pair_id,
                )
                self.__completed_result_queue.put(completed)
            except Exception as e:
                self.logger.error("Validation failed for {}: {}".format(req.name, str(e)))
                failed = ValidateFailedResult(
                    timestamp=datetime.datetime.now(),
                    name=req.name,
                    is_dir=req.is_dir,
                    pair_id=req.pair_id,
                    error_message=str(e),
                )
                self.__failed_result_queue.put(failed)
            finally:
                del self.__active_validations[name]

        # Publish current status
        statuses = [
            ValidateStatus(name=name, is_dir=req.is_dir, state=ValidateStatus.State.VALIDATING)
            for name, req in self.__active_validations.items()
        ]
        status_result = ValidateStatusResult(
            timestamp=datetime.datetime.now(),
            statuses=statuses,
        )
        self.__status_result_queue.put(status_result)

        if not self.__active_validations:
            time.sleep(ValidateProcess.__DEFAULT_SLEEP_INTERVAL_IN_SECS)

    def _validate_file(self, req: ValidateRequest):
        """Compare local and remote checksums for a single file or directory."""
        file_path = os.path.join(req.local_path, req.name)

        if req.is_dir:
            self._validate_directory(req, file_path)
        else:
            local_hash = self._hash_local_file(file_path, req.algorithm)
            remote_hash = self._hash_remote_file(req, req.name, req.algorithm)
            if local_hash != remote_hash:
                raise ValueError(
                    "Checksum mismatch for {}: local={} remote={}".format(
                        req.name, local_hash, remote_hash
                    )
                )
            self.logger.info("Validated {}: {}".format(req.name, local_hash))

    def _validate_directory(self, req: ValidateRequest, local_dir: str):
        """Recursively validate all files in a directory."""
        for root, _dirs, files in os.walk(local_dir):
            for filename in files:
                local_file = os.path.join(root, filename)
                # Relative path from the pair's local_path for the remote command
                rel_path = os.path.relpath(local_file, req.local_path)
                local_hash = self._hash_local_file(local_file, req.algorithm)
                remote_hash = self._hash_remote_file(req, rel_path, req.algorithm)
                if local_hash != remote_hash:
                    raise ValueError(
                        "Checksum mismatch for {}: local={} remote={}".format(
                            rel_path, local_hash, remote_hash
                        )
                    )
                self.logger.debug("Validated file {}: {}".format(rel_path, local_hash))
        self.logger.info("Validated directory {}".format(req.name))

    @staticmethod
    def _hash_local_file(file_path: str, algorithm: str) -> str:
        """Compute hash of a local file using streaming reads."""
        h = hashlib.new(algorithm)
        with open(file_path, "rb") as f:
            while True:
                chunk = f.read(8192)
                if not chunk:
                    break
                h.update(chunk)
        return h.hexdigest()

    def _hash_remote_file(self, req: ValidateRequest, rel_path: str, algorithm: str) -> str:
        """Compute hash of a remote file via SSH."""
        from ssh import Sshcp

        remote_file = os.path.join(req.remote_path, rel_path)

        # Map algorithm to remote command
        if algorithm == "md5":
            cmd = 'md5sum "{}"'.format(remote_file)
        elif algorithm in ("sha256", "sha-256"):
            cmd = 'sha256sum "{}"'.format(remote_file)
        elif algorithm == "sha1":
            cmd = 'sha1sum "{}"'.format(remote_file)
        else:
            cmd = '{}sum "{}"'.format(algorithm, remote_file)

        sshcp = Sshcp(
            host=req.remote_address,
            port=req.remote_port,
            user=req.remote_username,
            password=req.remote_password,
        )
        sshcp.set_base_logger(self.logger)

        output = sshcp.shell(cmd)
        # Output format: "<hash>  <filename>\n"
        hash_value = output.decode().strip().split()[0]
        return hash_value

    @overrides(AppProcess)
    def close_queues(self):
        self.__command_queue.close()
        self.__command_queue.join_thread()
        self.__status_result_queue.close()
        self.__status_result_queue.join_thread()
        self.__completed_result_queue.close()
        self.__completed_result_queue.join_thread()
        self.__failed_result_queue.close()
        self.__failed_result_queue.join_thread()
        super().close_queues()

    def validate(self, req: ValidateRequest):
        """Process-safe method to queue a validation request."""
        self.__command_queue.put(req)

    def pop_latest_statuses(self) -> Optional[ValidateStatusResult]:
        """Process-safe method to retrieve latest validation status."""
        latest_result = None
        try:
            while True:
                latest_result = self.__status_result_queue.get(block=False)
        except queue.Empty:
            pass
        return latest_result

    def pop_completed(self) -> List[ValidateCompletedResult]:
        """Process-safe method to retrieve newly completed validations."""
        completed = []
        try:
            while True:
                result = self.__completed_result_queue.get(block=False)
                completed.append(result)
        except queue.Empty:
            pass
        return completed

    def pop_failed(self) -> List[ValidateFailedResult]:
        """Process-safe method to retrieve newly failed validations."""
        failed = []
        try:
            while True:
                result = self.__failed_result_queue.get(block=False)
                failed.append(result)
        except queue.Empty:
            pass
        return failed
