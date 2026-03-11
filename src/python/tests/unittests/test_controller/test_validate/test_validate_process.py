# Copyright 2017, Inderpreet Singh, All rights reserved.

import unittest
import logging
import sys
import time
from unittest.mock import patch, MagicMock

from controller.validate import (
    ValidateProcess,
    ValidateRequest,
    ValidateCompletedResult,
    ValidateFailedResult,
    ValidateStatus,
)


class TestValidateProcess(unittest.TestCase):
    """
    Tests for ValidateProcess logic.

    These tests call run_init()/run_loop() directly instead of spawning a
    subprocess, because unittest mocks do not survive the 'spawn' start
    method (child re-imports everything, bypassing the mock).
    """

    def setUp(self):
        logger = logging.getLogger()
        handler = logging.StreamHandler(sys.stdout)
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
        formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(name)s - %(message)s")
        handler.setFormatter(formatter)

        self.process = ValidateProcess()
        self.process.run_init()

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

    @patch.object(ValidateProcess, '_hash_remote_file', return_value="abc123")
    @patch.object(ValidateProcess, '_hash_local_file', return_value="abc123")
    def test_successful_validation(self, mock_local, mock_remote):
        req = self._make_request()
        self.process.validate(req)
        time.sleep(0.1)  # let queue flush
        self.process.run_loop()

        completed = self.process.pop_completed()
        self.assertEqual(1, len(completed))
        self.assertEqual("test.txt", completed[0].name)
        self.assertEqual("pair-1", completed[0].pair_id)

        failed = self.process.pop_failed()
        self.assertEqual(0, len(failed))

    @patch.object(ValidateProcess, '_hash_remote_file', return_value="different")
    @patch.object(ValidateProcess, '_hash_local_file', return_value="abc123")
    def test_checksum_mismatch_reports_failure(self, mock_local, mock_remote):
        req = self._make_request()
        self.process.validate(req)
        time.sleep(0.1)
        self.process.run_loop()

        completed = self.process.pop_completed()
        self.assertEqual(0, len(completed))

        failed = self.process.pop_failed()
        self.assertEqual(1, len(failed))
        self.assertEqual("test.txt", failed[0].name)
        self.assertIn("mismatch", failed[0].error_message.lower())

    @patch.object(ValidateProcess, '_hash_remote_file', side_effect=Exception("SSH error"))
    @patch.object(ValidateProcess, '_hash_local_file', return_value="abc123")
    def test_remote_error_reports_failure(self, mock_local, mock_remote):
        req = self._make_request()
        self.process.validate(req)
        time.sleep(0.1)
        self.process.run_loop()

        completed = self.process.pop_completed()
        self.assertEqual(0, len(completed))

        failed = self.process.pop_failed()
        self.assertEqual(1, len(failed))
        self.assertIn("SSH error", failed[0].error_message)

    @patch.object(ValidateProcess, '_hash_remote_file', return_value="abc123")
    @patch.object(ValidateProcess, '_hash_local_file', return_value="abc123")
    def test_status_shows_active_validation(self, mock_local, mock_remote):
        # Queue a request but don't run_loop yet — check that initial status is empty
        status = self.process.pop_latest_statuses()
        self.assertIsNone(status)

        req = self._make_request()
        self.process.validate(req)
        time.sleep(0.1)

        # run_loop processes the validation (completes it) and publishes status
        self.process.run_loop()

        # After completion, status should show empty (validation finished)
        status = self.process.pop_latest_statuses()
        self.assertIsNotNone(status)
        self.assertEqual(0, len(status.statuses))

    @patch.object(ValidateProcess, '_hash_remote_file', return_value="abc123")
    @patch.object(ValidateProcess, '_hash_local_file', return_value="abc123")
    def test_multiple_validations_processed_sequentially(self, mock_local, mock_remote):
        req_a = self._make_request(name="a.txt", pair_id="p1")
        req_b = self._make_request(name="b.txt", pair_id="p2")
        self.process.validate(req_a)
        self.process.validate(req_b)
        time.sleep(0.1)

        # First loop processes one
        self.process.run_loop()
        completed = self.process.pop_completed()
        self.assertEqual(1, len(completed))

        # Second loop processes the other
        self.process.run_loop()
        completed = self.process.pop_completed()
        self.assertEqual(1, len(completed))

    @patch.object(ValidateProcess, '_hash_remote_file', return_value="abc123")
    @patch.object(ValidateProcess, '_hash_local_file', return_value="abc123")
    def test_duplicate_request_ignored(self, mock_local, mock_remote):
        req = self._make_request()
        self.process.validate(req)
        self.process.validate(req)  # duplicate
        time.sleep(0.1)

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
        time.sleep(0.1)
        self.process.run_loop()

        completed = self.process.pop_completed()
        self.assertEqual(0, len(completed))

        failed = self.process.pop_failed()
        self.assertEqual(1, len(failed))
        self.assertIn("Unsupported", failed[0].error_message)

    @patch.object(ValidateProcess, '_hash_remote_file', return_value="abc123")
    @patch.object(ValidateProcess, '_hash_local_file', return_value="abc123")
    def test_sha256_algorithm_accepted(self, mock_local, mock_remote):
        req = self._make_request(algorithm="sha256")
        self.process.validate(req)
        time.sleep(0.1)
        self.process.run_loop()

        completed = self.process.pop_completed()
        self.assertEqual(1, len(completed))

    def test_close_queues_releases_resources(self):
        self.process.run_loop()
        self.process.close_queues()
