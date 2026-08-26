# Copyright 2017, Inderpreet Singh, All rights reserved.
from __future__ import annotations

import datetime
import hashlib
import hmac
import multiprocessing
import os
import queue
import time
from enum import Enum
from typing import TYPE_CHECKING, override

from common import AppProcess, PipeStream, escape_remote_path_double, escape_remote_path_single

if TYPE_CHECKING:
    from ssh import Sshcp


class ValidateRequest:
    """Request to validate a file by comparing local and remote checksums."""

    def __init__(
        self,
        name: str,
        is_dir: bool,
        pair_id: str | None,
        local_path: str,
        remote_path: str,
        algorithm: str,
        remote_address: str,
        remote_username: str,
        remote_password: str | None,
        remote_port: int,
    ):
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

    def __init__(self, name: str, is_dir: bool, state: ValidateStatus.State, pair_id: str | None = None):
        self.name = name
        self.is_dir = is_dir
        self.state = state
        self.pair_id = pair_id

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ValidateStatus):
            return NotImplemented
        return self.__dict__ == other.__dict__


class ValidateStatusResult:
    def __init__(self, timestamp: datetime.datetime, statuses: list[ValidateStatus]):
        self.timestamp = timestamp
        self.statuses = statuses


class ValidateCompletedResult:
    def __init__(self, timestamp: datetime.datetime, name: str, is_dir: bool, pair_id: str | None = None):
        self.timestamp = timestamp
        self.name = name
        self.is_dir = is_dir
        self.pair_id = pair_id


class ValidateFailedResult:
    def __init__(
        self,
        timestamp: datetime.datetime,
        name: str,
        is_dir: bool,
        pair_id: str | None = None,
        error_message: str | None = None,
        is_checksum_mismatch: bool = False,
    ):
        self.timestamp = timestamp
        self.name = name
        self.is_dir = is_dir
        self.pair_id = pair_id
        self.error_message = error_message
        self.is_checksum_mismatch = is_checksum_mismatch


class ChecksumMismatchError(ValueError):
    """Raised when local and remote checksums don't match."""

    pass


_ALLOWED_ALGORITHMS = frozenset({"md5", "sha1", "sha256"})


class ValidateProcess(AppProcess):
    """Process to validate file integrity by comparing local and remote checksums."""

    __DEFAULT_SLEEP_INTERVAL_IN_SECS = 0.5

    def __init__(self):
        super().__init__(name=self.__class__.__name__)
        self.__command_queue: multiprocessing.Queue[ValidateRequest] = multiprocessing.Queue()
        self.__status_result_queue = PipeStream()
        self.__completed_result_queue = PipeStream()
        self.__failed_result_queue = PipeStream()
        self.__active_validations: dict[tuple[str | None, str], ValidateRequest] = {}

    @override
    def run_init(self):
        pass

    @override
    def run_cleanup(self):
        pass

    @override
    def run_loop(self):
        # Pick up new validation requests
        try:
            while True:
                req = self.__command_queue.get(block=False)
                key = (req.pair_id, req.name)
                if key in self.__active_validations:
                    self.logger.warning(f"Validation already in progress for {req.name}")
                    continue
                self.__active_validations[key] = req
        except queue.Empty:
            pass

        # Publish current status BEFORE the blocking call so the active request
        # appears as VALIDATING to the UI.
        if self.__active_validations:
            statuses = [
                ValidateStatus(
                    name=req.name, is_dir=req.is_dir, state=ValidateStatus.State.VALIDATING, pair_id=req.pair_id
                )
                for req in self.__active_validations.values()
            ]
            self.__status_result_queue.put(
                ValidateStatusResult(
                    timestamp=datetime.datetime.now(),
                    statuses=statuses,
                )
            )

        # Process one validation at a time (blocking but in child process)
        if self.__active_validations:
            key, req = next(iter(self.__active_validations.items()))
            try:
                self._validate_file(req)
                completed = ValidateCompletedResult(
                    timestamp=datetime.datetime.now(),
                    name=req.name,
                    is_dir=req.is_dir,
                    pair_id=req.pair_id,
                )
                self.__completed_result_queue.put(completed)
            except ChecksumMismatchError as e:
                self.logger.error(f"Checksum mismatch for {req.name}: {e!s}")
                failed = ValidateFailedResult(
                    timestamp=datetime.datetime.now(),
                    name=req.name,
                    is_dir=req.is_dir,
                    pair_id=req.pair_id,
                    error_message=str(e),
                    is_checksum_mismatch=True,
                )
                self.__failed_result_queue.put(failed)
            except Exception as e:
                self.logger.error(f"Validation failed for {req.name}: {e!s}")
                failed = ValidateFailedResult(
                    timestamp=datetime.datetime.now(),
                    name=req.name,
                    is_dir=req.is_dir,
                    pair_id=req.pair_id,
                    error_message=str(e),
                    is_checksum_mismatch=False,
                )
                self.__failed_result_queue.put(failed)
            finally:
                del self.__active_validations[key]

            # Publish post-completion status (the completed item is now removed)
            statuses = [
                ValidateStatus(name=r.name, is_dir=r.is_dir, state=ValidateStatus.State.VALIDATING, pair_id=r.pair_id)
                for r in self.__active_validations.values()
            ]
            self.__status_result_queue.put(
                ValidateStatusResult(
                    timestamp=datetime.datetime.now(),
                    statuses=statuses,
                )
            )
        else:
            time.sleep(ValidateProcess.__DEFAULT_SLEEP_INTERVAL_IN_SECS)

    def _validate_file(self, req: ValidateRequest):
        """Compare local and remote checksums for a single file or directory."""
        file_path = os.path.join(req.local_path, req.name)

        if req.algorithm not in _ALLOWED_ALGORITHMS:
            raise ValueError(f"Unsupported hash algorithm: {req.algorithm}")

        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Local path does not exist: {file_path}")

        sshcp = self._create_ssh(req)

        if req.is_dir:
            if not os.path.isdir(file_path):
                raise ValueError(f"Expected directory but found file: {file_path}")
            self._validate_directory(req, file_path, sshcp)
        else:
            local_hash = self._hash_local_file(file_path, req.algorithm)
            remote_hash = self._hash_remote_file(req, req.name, req.algorithm, sshcp)
            if not hmac.compare_digest(local_hash, remote_hash):
                raise ChecksumMismatchError(
                    f"Checksum mismatch for {req.name}: local={local_hash} remote={remote_hash}"
                )
            self.logger.info(f"Validated {req.name}: {local_hash}")

    def _validate_directory(self, req: ValidateRequest, local_dir: str, sshcp: Sshcp) -> None:
        """Validate all files in a directory by comparing local and remote checksums.

        Performs symmetric validation: collects local file set via os.walk and
        remote file set via SSH 'find', then compares the union of both sets.
        Files only on one side are flagged as mismatches.
        """
        # Build local file set (relative paths from local_dir)
        local_rel_paths: set[str] = set()
        for root, _dirs, files in os.walk(local_dir):
            for filename in files:
                local_file = os.path.join(root, filename)
                rel_path = os.path.relpath(local_file, req.local_path)
                local_rel_paths.add(rel_path)

        # Build remote file set via SSH find
        remote_dir = os.path.join(req.remote_path, req.name)
        find_cmd = f"find {self._escape_remote(remote_dir)} -type f"
        try:
            find_output = sshcp.shell(find_cmd)
            remote_abs_paths = find_output.decode().strip().split("\n")
            remote_rel_paths: set[str] = set()
            for abs_path in remote_abs_paths:
                abs_path = abs_path.strip()
                if abs_path:
                    remote_rel_paths.add(self._remote_key(abs_path, req.name))
        except Exception as e:
            raise ValueError(f"Failed to list remote directory {remote_dir}: {e!s}") from e

        # Validate the union of both sets
        all_paths = local_rel_paths | remote_rel_paths
        mismatches: list[str] = []

        for rel_path in sorted(all_paths):
            local_file = os.path.join(req.local_path, rel_path)
            is_local = rel_path in local_rel_paths
            is_remote = rel_path in remote_rel_paths

            if is_local and not is_remote:
                mismatches.append(f"Local-only file: {rel_path}")
                continue
            if is_remote and not is_local:
                mismatches.append(f"Remote-only file: {rel_path}")
                continue

            # Both exist — compare hashes
            local_hash = self._hash_local_file(local_file, req.algorithm)
            remote_hash = self._hash_remote_file(req, rel_path, req.algorithm, sshcp)
            if not hmac.compare_digest(local_hash, remote_hash):
                mismatches.append(f"Checksum mismatch for {rel_path}: local={local_hash} remote={remote_hash}")
            else:
                self.logger.debug(f"Validated file {rel_path}: {local_hash}")

        if mismatches:
            raise ChecksumMismatchError(
                "Directory validation failed for {}: {}".format(req.name, "; ".join(mismatches))
            )
        self.logger.info(f"Validated directory {req.name}")

    @staticmethod
    def _hash_local_file(file_path: str, algorithm: str) -> str:
        """Compute hash of a local file using streaming reads."""
        # Normalize algorithm name for hashlib (e.g. sha-256 -> sha256)
        hashlib_name = algorithm.replace("-", "")
        h = hashlib.new(hashlib_name)
        with open(file_path, "rb") as f:
            while True:
                chunk = f.read(8192)
                if not chunk:
                    break
                h.update(chunk)
        return h.hexdigest()

    def _create_ssh(self, req: ValidateRequest):
        """Create an SSH connection for use across multiple remote hash operations."""
        from ssh import Sshcp

        sshcp = Sshcp(
            host=req.remote_address,
            port=req.remote_port,
            user=req.remote_username,
            password=req.remote_password,
        )
        sshcp.set_base_logger(self.logger)
        return sshcp

    @staticmethod
    def _escape_remote(path: str) -> str:
        """Quote a remote path, expanding a leading ~ to $HOME (mirrors scanner/delete)."""
        if path.startswith("~"):
            return escape_remote_path_double(path)
        return escape_remote_path_single(path)

    @staticmethod
    def _remote_key(abs_path: str, name: str) -> str:
        """Derive a `name/subpath` key from a remote `find` result.

        The find command is rooted at a directory whose final component is `name`,
        so every emitted path looks like `.../<name>/<subpath>`. Anchoring on the
        last `<name>` component makes the key independent of whether the remote
        shell expanded a leading ~ to $HOME (issue #519), so remote keys always
        match the local keys (`relpath(local_file, local_path)` == `name/subpath`).

        Known limitation: this is a heuristic. If the tree contains a *nested*
        directory whose name equals `name` (e.g. `.../mydir/mydir/a.txt` for
        name="mydir"), last-occurrence anchoring yields `mydir/a.txt` while the
        local key is `mydir/mydir/a.txt`, producing a false (non-checksum)
        mismatch. No name-based anchor is fully robust without the shell-expanded
        find root; the robust fix (capture the expanded base via `cd <root>;
        pwd; find .` and derive keys from it) is tracked as a #519 follow-up.
        """
        parts = abs_path.split("/")
        # Find the last occurrence of the directory leaf to anchor the key.
        for idx in range(len(parts) - 1, -1, -1):
            if parts[idx] == name:
                return "/".join(parts[idx:])
        # Fallback: leaf not found (unexpected); use the basename under name.
        return os.path.join(name, os.path.basename(abs_path))

    @staticmethod
    def _build_hash_cmd(algorithm: str, quoted_file: str) -> str:
        """Build the remote hash command for the given algorithm."""
        if algorithm == "md5":
            return f"md5sum {quoted_file}"
        if algorithm == "sha256":
            return f"sha256sum {quoted_file}"
        if algorithm == "sha1":
            return f"sha1sum {quoted_file}"
        raise ValueError(f"Unsupported algorithm: {algorithm}")

    def _hash_remote_file(self, req: ValidateRequest, rel_path: str, algorithm: str, sshcp: Sshcp) -> str:
        """Compute hash of a remote file via SSH."""
        remote_file = os.path.join(req.remote_path, rel_path)
        quoted_file = self._escape_remote(remote_file)
        cmd = self._build_hash_cmd(algorithm, quoted_file)

        output = sshcp.shell(cmd)
        # Output format: "<hash>  <filename>\n"
        decoded = output.decode().strip()
        parts = decoded.split()
        if not parts:
            raise ValueError(f"Empty or unexpected output from remote hash command for {rel_path}: {decoded!r}")
        return parts[0]

    @override
    def close_queues(self):
        self.__command_queue.close()
        self.__command_queue.join_thread()
        self.__status_result_queue.close()
        self.__completed_result_queue.close()
        self.__failed_result_queue.close()
        super().close_queues()

    def validate(self, req: ValidateRequest):
        """Process-safe method to queue a validation request."""
        self.__command_queue.put(req)

    def pop_latest_statuses(self) -> ValidateStatusResult | None:
        """Process-safe method to retrieve latest validation status."""
        results = self.__status_result_queue.pop_all()
        return results[-1] if results else None

    def pop_completed(self) -> list[ValidateCompletedResult]:
        """Process-safe method to retrieve newly completed validations."""
        return self.__completed_result_queue.pop_all()

    def pop_failed(self) -> list[ValidateFailedResult]:
        """Process-safe method to retrieve newly failed validations."""
        return self.__failed_result_queue.pop_all()
