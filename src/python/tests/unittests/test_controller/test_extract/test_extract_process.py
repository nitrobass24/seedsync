# Copyright 2017, Inderpreet Singh, All rights reserved.

import unittest
import logging
from unittest.mock import patch
import sys
import time

from model import ModelFile
from controller.extract import ExtractProcess, ExtractStatus, ExtractRequest


class TestExtractProcess(unittest.TestCase):
    """
    Tests for ExtractProcess logic.

    These tests call run_init()/run_loop() directly instead of spawning a
    subprocess, because unittest mocks do not survive the 'spawn' start
    method (child re-imports everything, bypassing the mock).
    """

    def setUp(self):
        self.dispatch_patcher = patch('controller.extract.extract_process.ExtractDispatch')
        self.mock_dispatch_cls = self.dispatch_patcher.start()
        self.mock_dispatch = self.mock_dispatch_cls.return_value

        # by default mock returns empty statuses
        self.mock_dispatch.status.return_value = []

        logger = logging.getLogger()
        handler = logging.StreamHandler(sys.stdout)
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
        formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(name)s - %(message)s")
        handler.setFormatter(formatter)

        self.process = ExtractProcess()

    def tearDown(self):
        self.dispatch_patcher.stop()

    def test_calls_start_dispatch(self):
        self.process.run_init()
        self.mock_dispatch.start.assert_called_once()

    def test_retrieves_status(self):
        s_a = ExtractStatus(name="a", is_dir=True, state=ExtractStatus.State.EXTRACTING)
        s_b = ExtractStatus(name="b", is_dir=False, state=ExtractStatus.State.EXTRACTING)
        s_c = ExtractStatus(name="c", is_dir=True, state=ExtractStatus.State.EXTRACTING)

        self.process.run_init()

        # Status with one entry
        self.mock_dispatch.status.return_value = [s_a]
        self.process.run_loop()
        status_result = self.process.pop_latest_statuses()
        self.assertEqual(1, len(status_result.statuses))
        self.assertEqual("a", status_result.statuses[0].name)
        self.assertEqual(True, status_result.statuses[0].is_dir)
        self.assertEqual(ExtractStatus.State.EXTRACTING, status_result.statuses[0].state)

        # Status with two entries
        self.mock_dispatch.status.return_value = [s_a, s_b]
        self.process.run_loop()
        status_result = self.process.pop_latest_statuses()
        self.assertEqual(2, len(status_result.statuses))
        self.assertEqual("a", status_result.statuses[0].name)
        self.assertEqual("b", status_result.statuses[1].name)
        self.assertEqual(False, status_result.statuses[1].is_dir)

        # Status changes
        self.mock_dispatch.status.return_value = [s_c]
        self.process.run_loop()
        status_result = self.process.pop_latest_statuses()
        self.assertEqual(1, len(status_result.statuses))
        self.assertEqual("c", status_result.statuses[0].name)

        # Empty status
        self.mock_dispatch.status.return_value = []
        self.process.run_loop()
        status_result = self.process.pop_latest_statuses()
        self.assertEqual(0, len(status_result.statuses))

    def test_retrieves_completed(self):
        self.process.run_init()

        # Capture the listener that was registered
        self.mock_dispatch.add_listener.assert_called_once()
        listener = self.mock_dispatch.add_listener.call_args[0][0]

        # Simulate a completion callback
        listener.extract_completed(name="a", is_dir=True)
        time.sleep(0.1)  # let multiprocessing.Queue background thread flush
        completed = self.process.pop_completed()
        self.assertEqual(1, len(completed))
        self.assertEqual("a", completed[0].name)
        self.assertEqual(True, completed[0].is_dir)

        # Next pop should be empty
        completed = self.process.pop_completed()
        self.assertEqual(0, len(completed))

        # Simulate multiple completions
        listener.extract_completed(name="b", is_dir=False)
        listener.extract_completed(name="c", is_dir=True)
        time.sleep(0.1)  # let multiprocessing.Queue background thread flush
        completed = self.process.pop_completed()
        self.assertEqual(2, len(completed))
        self.assertEqual("b", completed[0].name)
        self.assertEqual(False, completed[0].is_dir)
        self.assertEqual("c", completed[1].name)
        self.assertEqual(True, completed[1].is_dir)

        # Next pop should be empty
        completed = self.process.pop_completed()
        self.assertEqual(0, len(completed))

    def test_forwards_extract_commands(self):
        a = ModelFile("a", True)
        a.local_size = 100
        aa = ModelFile("aa", False)
        aa.local_size = 60
        a.add_child(aa)
        ab = ModelFile("ab", False)
        ab.local_size = 40
        a.add_child(ab)

        b = ModelFile("b", True)
        b.local_size = 10
        ba = ModelFile("ba", True)
        ba.local_size = 10
        b.add_child(ba)
        baa = ModelFile("baa", False)
        baa.local_size = 10
        ba.add_child(baa)

        c = ModelFile("c", False)
        c.local_size = 1234

        self.process.run_init()

        req_a = ExtractRequest(model_file=a, local_path="/local", out_dir_path="/out")
        req_b = ExtractRequest(model_file=b, local_path="/local", out_dir_path="/out")
        req_c = ExtractRequest(model_file=c, local_path="/local", out_dir_path="/out")

        # Queue commands and let multiprocessing.Queue background thread flush
        self.process.extract(req_a)
        self.process.extract(req_b)
        self.process.extract(req_c)
        time.sleep(0.1)
        self.process.run_loop()

        # Verify all three were forwarded to dispatch
        self.assertEqual(3, self.mock_dispatch.extract.call_count)

        # Verify first call
        call_0 = self.mock_dispatch.extract.call_args_list[0][0][0]
        self.assertEqual("a", call_0.model_file.name)
        self.assertEqual(True, call_0.model_file.is_dir)
        self.assertEqual(100, call_0.model_file.local_size)
        children = call_0.model_file.get_children()
        self.assertEqual(2, len(children))
        self.assertEqual("aa", children[0].name)
        self.assertEqual("ab", children[1].name)

        # Verify second call
        call_1 = self.mock_dispatch.extract.call_args_list[1][0][0]
        self.assertEqual("b", call_1.model_file.name)
        self.assertEqual(True, call_1.model_file.is_dir)
        child = call_1.model_file.get_children()[0]
        self.assertEqual("ba", child.name)
        subchild = child.get_children()[0]
        self.assertEqual("baa", subchild.name)

        # Verify third call
        call_2 = self.mock_dispatch.extract.call_args_list[2][0][0]
        self.assertEqual("c", call_2.model_file.name)
        self.assertEqual(False, call_2.model_file.is_dir)
        self.assertEqual(1234, call_2.model_file.local_size)
