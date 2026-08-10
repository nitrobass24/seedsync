# Copyright 2017, Inderpreet Singh, All rights reserved.

import multiprocessing
import os
import struct
import time
import unittest

import timeout_decorator

from common import PipeFlag, PipeStream

# Module-level so the class pickles through the spawn start method
_ctx = multiprocessing.get_context("spawn")


class PutterProcess(_ctx.Process):
    """Puts the given items on the stream, then exits."""

    def __init__(self, stream: PipeStream, items: list):
        super().__init__()
        self.stream = stream
        self.items = items

    def run(self):
        for item in self.items:
            self.stream.put(item)


class TestPipeStream(unittest.TestCase):
    @timeout_decorator.timeout(20)
    def test_put_and_pop_all_across_processes(self):
        stream = PipeStream()
        process = PutterProcess(stream, ["a", {"b": 2}, 3])
        process.start()
        items = []
        end_time = time.time() + 10
        while len(items) < 3 and time.time() < end_time:
            items += stream.pop_all()
            time.sleep(0.01)
        process.join()
        self.assertEqual(["a", {"b": 2}, 3], items)
        stream.close()

    @timeout_decorator.timeout(20)
    def test_pop_all_after_child_death(self):
        # Buffered results must remain readable after the child exits (#571)
        stream = PipeStream()
        process = PutterProcess(stream, [1, 2, 3])
        process.start()
        process.join()
        self.assertEqual([1, 2, 3], stream.pop_all())
        stream.close()

    def test_pop_all_empty_returns_empty_list(self):
        stream = PipeStream()
        self.assertEqual([], stream.pop_all())
        stream.close()

    def test_close_is_idempotent(self):
        stream = PipeStream()
        stream.close()
        stream.close()

    @timeout_decorator.timeout(5)
    def test_pop_all_does_not_block_on_partial_message(self):
        # A child killed mid-send leaves a truncated message. Once the parent
        # has dropped its send-end copy, pop_all must return the complete
        # messages instead of blocking forever in recv() on the partial one.
        stream = PipeStream()
        stream.put("complete")
        # Fake a truncated message: header claims 100 bytes, body has 7
        send_conn = stream._PipeStream__send_conn
        os.write(send_conn.fileno(), struct.pack("!i", 100) + b"partial")
        stream.close_unused_in_parent()
        self.assertEqual(["complete"], stream.pop_all())
        stream.close()

    @timeout_decorator.timeout(5)
    def test_put_raises_broken_pipe_when_receiver_gone(self):
        # An orphaned child (parent died without terminate()) must get a
        # BrokenPipeError from put() instead of blocking forever
        stream = PipeStream()
        stream.close_unused_in_child()
        with self.assertRaises(BrokenPipeError):
            stream.put("x")
        stream.close()

    def test_pop_all_after_close_returns_empty_list(self):
        stream = PipeStream()
        stream.close()
        self.assertEqual([], stream.pop_all())


class TestPipeFlag(unittest.TestCase):
    def test_initially_not_set(self):
        flag = PipeFlag()
        self.assertFalse(flag.is_set())
        flag.close()

    def test_set_and_is_set_does_not_consume(self):
        flag = PipeFlag()
        flag.set()
        self.assertTrue(flag.is_set())
        self.assertTrue(flag.is_set())
        flag.close()

    def test_wait_returns_promptly_when_set(self):
        flag = PipeFlag()
        flag.set()
        start = time.time()
        self.assertTrue(flag.wait(5))
        self.assertLess(time.time() - start, 1)
        # wait does not consume
        self.assertTrue(flag.is_set())
        flag.close()

    def test_wait_times_out_when_not_set(self):
        flag = PipeFlag()
        start = time.time()
        self.assertFalse(flag.wait(0.2))
        self.assertGreaterEqual(time.time() - start, 0.2)
        flag.close()

    def test_clear_resets_flag(self):
        flag = PipeFlag()
        flag.set()
        flag.set()  # no-op while already set
        flag.clear()
        self.assertFalse(flag.is_set())
        self.assertFalse(flag.wait(0.05))
        flag.close()

    def test_set_after_clear_works(self):
        flag = PipeFlag()
        flag.set()
        flag.clear()
        flag.set()
        self.assertTrue(flag.is_set())
        flag.close()

    def test_close_is_idempotent(self):
        flag = PipeFlag()
        flag.close()
        flag.close()

    def test_set_does_not_raise_after_parent_drops_recv_end(self):
        # The parent drops its recv-end copy after start(); set() must still
        # work (no dedup poll on a closed conn, no error on repeated sets)
        flag = PipeFlag()
        flag.close_unused_in_parent()
        flag.set()
        flag.set()
        flag.close()

    def test_reads_as_set_when_sender_gone(self):
        # A dead parent closes the last send fd; EOF is pollable, so the
        # child sees the terminate flag as permanently set and exits
        flag = PipeFlag()
        flag.close_unused_in_child()
        self.assertTrue(flag.is_set())
        self.assertTrue(flag.wait(0.1))
        flag.clear()  # must not spin or raise on EOF
        self.assertTrue(flag.is_set())
        flag.close()
