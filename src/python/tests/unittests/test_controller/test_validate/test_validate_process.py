# Copyright 2017, Inderpreet Singh, All rights reserved.

import queue
import unittest
import logging
import sys
from unittest.mock import patch, MagicMock

from controller.validate import (
    ValidateProcess,
    ValidateRequest,
    ValidateCompletedResult,
    ValidateFailedResult,
    ValidateStatus,
    ChecksumMismatchError,
)


class _SyncQueue(queue.Queue):
    """A queue.Queue with close/join_thread stubs so it can replace
    multiprocessing.Queue in single-process tests (no feeder-thread race)."""
    def close(self):
        pass

    def join_thread(self):
        pass


class TestValidateProcess(unittest.TestCase):
    """
    Tests for ValidateProcess logic.

    These tests call run_init()/run_loop() directly instead of spawning a
    subprocess, because unittest mocks do not survive the 'spawn' start
    method (child re-imports everything, bypassing the mock).

    multiprocessing.Queue is replaced with _SyncQueue to avoid the feeder-
    thread race condition that causes get(block=False) to miss items that
    were just put().
    """

    def setUp(self):
        logger = logging.getLogger()
        self.handler = logging.StreamHandler(sys.stdout)
        logger.addHandler(self.handler)
        logger.setLevel(logging.DEBUG)
        formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(name)s - %(message)s")
        self.handler.setFormatter(formatter)

        with patch('controller.validate.validate_process.multiprocessing.Queue', _SyncQueue):
            self.process = ValidateProcess()
        self.process.run_init()

    def tearDown(self):
        self.process.close_queues()
        logging.getLogger().removeHandler(self.handler)

    def _make_request(self, name="test.txt", is_dir=False, pair_id="pair-1",
                      local_path="/local", remote_path="/remote",
                      algorithm="md5"):
        return ValidateRequest(
            name=name, is_dir=is_dir, pair_id=pair_id,
            local_path=local_path, remote_path=remote_path,
            algorithm=algorithm,
            remote_address="server.com", remote_username="user",
            remote_password="pass", remote_port=22,
        )

    @patch('controller.validate.validate_process.os.path.exists', return_value=True)
    @patch.object(ValidateProcess, '_create_ssh', return_value=MagicMock())
    @patch.object(ValidateProcess, '_hash_remote_file', return_value="abc123")
    @patch.object(ValidateProcess, '_hash_local_file', return_value="abc123")
    def test_successful_validation(self, mock_local, mock_remote, mock_ssh, mock_exists):
        req = self._make_request()
        self.process.validate(req)
        self.process.run_loop()

        completed = self.process.pop_completed()
        self.assertEqual(1, len(completed))
        self.assertEqual("test.txt", completed[0].name)
        self.assertEqual("pair-1", completed[0].pair_id)

        failed = self.process.pop_failed()
        self.assertEqual(0, len(failed))

    @patch('controller.validate.validate_process.os.path.exists', return_value=True)
    @patch.object(ValidateProcess, '_create_ssh', return_value=MagicMock())
    @patch.object(ValidateProcess, '_hash_remote_file', return_value="different")
    @patch.object(ValidateProcess, '_hash_local_file', return_value="abc123")
    def test_checksum_mismatch_reports_failure(self, mock_local, mock_remote, mock_ssh, mock_exists):
        req = self._make_request()
        self.process.validate(req)
        self.process.run_loop()

        completed = self.process.pop_completed()
        self.assertEqual(0, len(completed))

        failed = self.process.pop_failed()
        self.assertEqual(1, len(failed))
        self.assertEqual("test.txt", failed[0].name)
        self.assertIn("mismatch", failed[0].error_message.lower())
        self.assertTrue(failed[0].is_checksum_mismatch)

    @patch('controller.validate.validate_process.os.path.exists', return_value=True)
    @patch.object(ValidateProcess, '_create_ssh', return_value=MagicMock())
    @patch.object(ValidateProcess, '_hash_remote_file', side_effect=Exception("SSH error"))
    @patch.object(ValidateProcess, '_hash_local_file', return_value="abc123")
    def test_remote_error_reports_failure(self, mock_local, mock_remote, mock_ssh, mock_exists):
        req = self._make_request()
        self.process.validate(req)
        self.process.run_loop()

        completed = self.process.pop_completed()
        self.assertEqual(0, len(completed))

        failed = self.process.pop_failed()
        self.assertEqual(1, len(failed))
        self.assertIn("SSH error", failed[0].error_message)
        self.assertFalse(failed[0].is_checksum_mismatch)

    @patch('controller.validate.validate_process.os.path.exists', return_value=True)
    @patch.object(ValidateProcess, '_create_ssh', return_value=MagicMock())
    @patch.object(ValidateProcess, '_hash_remote_file', return_value="abc123")
    @patch.object(ValidateProcess, '_hash_local_file', return_value="abc123")
    def test_status_shows_active_validation(self, mock_local, mock_remote, mock_ssh, mock_exists):
        # Queue a request but don't run_loop yet — check that initial status is empty
        status = self.process.pop_latest_statuses()
        self.assertIsNone(status)

        req = self._make_request()
        self.process.validate(req)

        # run_loop emits status before the blocking call (with VALIDATING) and
        # after completion (empty). pop_latest_statuses drains the queue and
        # returns the last result — which should be the post-completion empty one.
        self.process.run_loop()

        status = self.process.pop_latest_statuses()
        self.assertIsNotNone(status)
        self.assertEqual(0, len(status.statuses))

    @patch('controller.validate.validate_process.os.path.exists', return_value=True)
    @patch.object(ValidateProcess, '_create_ssh', return_value=MagicMock())
    @patch.object(ValidateProcess, '_hash_remote_file', return_value="abc123")
    @patch.object(ValidateProcess, '_hash_local_file', return_value="abc123")
    def test_multiple_validations_processed_sequentially(self, mock_local, mock_remote, mock_ssh, mock_exists):
        req_a = self._make_request(name="a.txt", pair_id="p1")
        req_b = self._make_request(name="b.txt", pair_id="p2")
        self.process.validate(req_a)
        self.process.validate(req_b)

        # First loop processes one
        self.process.run_loop()
        completed = self.process.pop_completed()
        self.assertEqual(1, len(completed))

        # Second loop processes the other
        self.process.run_loop()
        completed = self.process.pop_completed()
        self.assertEqual(1, len(completed))

    @patch('controller.validate.validate_process.os.path.exists', return_value=True)
    @patch.object(ValidateProcess, '_create_ssh', return_value=MagicMock())
    @patch.object(ValidateProcess, '_hash_remote_file', return_value="abc123")
    @patch.object(ValidateProcess, '_hash_local_file', return_value="abc123")
    def test_duplicate_request_ignored(self, mock_local, mock_remote, mock_ssh, mock_exists):
        req = self._make_request()
        self.process.validate(req)
        self.process.validate(req)  # duplicate

        self.process.run_loop()
        completed = self.process.pop_completed()
        self.assertEqual(1, len(completed))

        # Second loop should have nothing
        self.process.run_loop()
        completed = self.process.pop_completed()
        self.assertEqual(0, len(completed))

    def test_unsupported_algorithm_reports_failure(self):
        req = self._make_request(algorithm="invalid_algo")
        self.process.validate(req)
        self.process.run_loop()

        completed = self.process.pop_completed()
        self.assertEqual(0, len(completed))

        failed = self.process.pop_failed()
        self.assertEqual(1, len(failed))
        self.assertIn("Unsupported", failed[0].error_message)

    @patch('controller.validate.validate_process.os.path.exists', return_value=True)
    @patch.object(ValidateProcess, '_create_ssh', return_value=MagicMock())
    @patch.object(ValidateProcess, '_hash_remote_file', return_value="abc123")
    @patch.object(ValidateProcess, '_hash_local_file', return_value="abc123")
    def test_sha256_algorithm_accepted(self, mock_local, mock_remote, mock_ssh, mock_exists):
        req = self._make_request(algorithm="sha256")
        self.process.validate(req)
        self.process.run_loop()

        completed = self.process.pop_completed()
        self.assertEqual(1, len(completed))

    def test_missing_local_file_reports_failure(self):
        req = self._make_request(local_path="/nonexistent/path")
        self.process.validate(req)
        self.process.run_loop()

        completed = self.process.pop_completed()
        self.assertEqual(0, len(completed))

        failed = self.process.pop_failed()
        self.assertEqual(1, len(failed))
        self.assertIn("does not exist", failed[0].error_message)
        self.assertFalse(failed[0].is_checksum_mismatch)

    @patch('controller.validate.validate_process.os.path.exists', return_value=True)
    @patch.object(ValidateProcess, '_create_ssh', return_value=MagicMock())
    @patch.object(ValidateProcess, '_hash_remote_file', return_value="abc123")
    @patch.object(ValidateProcess, '_hash_local_file', return_value="abc123")
    def test_cross_pair_same_name_both_processed(self, mock_local, mock_remote, mock_ssh, mock_exists):
        req_a = self._make_request(name="shared.txt", pair_id="pair-A")
        req_b = self._make_request(name="shared.txt", pair_id="pair-B")
        self.process.validate(req_a)
        self.process.validate(req_b)

        self.process.run_loop()
        self.process.run_loop()

        completed = self.process.pop_completed()
        self.assertEqual(2, len(completed))
        pair_ids = {r.pair_id for r in completed}
        self.assertEqual({"pair-A", "pair-B"}, pair_ids)

    @patch('controller.validate.validate_process.os.path.exists', return_value=True)
    @patch('controller.validate.validate_process.os.path.isdir', return_value=True)
    @patch('controller.validate.validate_process.os.walk')
    @patch.object(ValidateProcess, '_create_ssh')
    @patch.object(ValidateProcess, '_hash_remote_file', return_value="abc123")
    @patch.object(ValidateProcess, '_hash_local_file', return_value="abc123")
    def test_directory_validation_detects_symmetric_diff(
            self, mock_local_hash, mock_remote_hash, mock_ssh,
            mock_walk, mock_isdir, mock_exists):
        """_validate_directory should detect local-only, remote-only, and hash-mismatch files."""
        # Local has: mydir/a.txt, mydir/b.txt (b.txt is local-only)
        mock_walk.return_value = [
            ("/local/mydir", [], ["a.txt", "b.txt"]),
        ]
        # Remote has: mydir/a.txt, mydir/c.txt (c.txt is remote-only)
        ssh_mock = MagicMock()
        ssh_mock.shell.return_value = b"/remote/mydir/a.txt\n/remote/mydir/c.txt\n"
        mock_ssh.return_value = ssh_mock

        req = self._make_request(name="mydir", is_dir=True)
        self.process.validate(req)
        self.process.run_loop()

        completed = self.process.pop_completed()
        self.assertEqual(0, len(completed))

        failed = self.process.pop_failed()
        self.assertEqual(1, len(failed))
        self.assertTrue(failed[0].is_checksum_mismatch)
        self.assertIn("Local-only", failed[0].error_message)
        self.assertIn("Remote-only", failed[0].error_message)
        self.assertIn("mydir/b.txt", failed[0].error_message)
        self.assertIn("mydir/c.txt", failed[0].error_message)

    @patch('controller.validate.validate_process.os.path.exists', return_value=True)
    @patch('controller.validate.validate_process.os.path.isdir', return_value=True)
    @patch('controller.validate.validate_process.os.walk')
    @patch.object(ValidateProcess, '_create_ssh')
    @patch.object(ValidateProcess, '_hash_remote_file', return_value="abc123")
    @patch.object(ValidateProcess, '_hash_local_file', return_value="abc123")
    def test_directory_validation_succeeds_when_all_match(
            self, mock_local_hash, mock_remote_hash, mock_ssh,
            mock_walk, mock_isdir, mock_exists):
        """_validate_directory should succeed when local and remote file sets match with equal hashes."""
        mock_walk.return_value = [
            ("/local/mydir", [], ["a.txt", "b.txt"]),
        ]
        ssh_mock = MagicMock()
        ssh_mock.shell.return_value = b"/remote/mydir/a.txt\n/remote/mydir/b.txt\n"
        mock_ssh.return_value = ssh_mock

        req = self._make_request(name="mydir", is_dir=True)
        self.process.validate(req)
        self.process.run_loop()

        completed = self.process.pop_completed()
        self.assertEqual(1, len(completed))
        self.assertEqual("mydir", completed[0].name)

        failed = self.process.pop_failed()
        self.assertEqual(0, len(failed))

    def test_close_queues_releases_resources(self):
        # close_queues is also called in tearDown; calling it twice should be safe
        self.process.run_loop()
        self.process.close_queues()
        # Prevent tearDown from calling close_queues again on already-closed queues
        with patch('controller.validate.validate_process.multiprocessing.Queue', _SyncQueue):
            self.process = ValidateProcess()
        self.process.run_init()
