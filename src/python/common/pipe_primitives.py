# Copyright 2017, Inderpreet Singh, All rights reserved.

from __future__ import annotations

import contextlib
import multiprocessing
from typing import Any


class PipeStream:
    """
    SPSC mp.Queue replacement backed by mp.Pipe. Costs 0 semaphores.
    put() is called from the child process, pop_all() from the parent.

    Each process must drop its unused end after the fork/spawn point
    (AppProcess does this) so the other process's death turns into EOF
    instead of a permanent block: without it, a child killed mid-send
    leaves a partial message whose recv() hangs the parent forever, and
    an orphaned child's put() blocks forever on a full pipe.
    """

    def __init__(self):
        self.__recv_conn, self.__send_conn = multiprocessing.Pipe(duplex=False)

    def put(self, obj: Any):
        # Raises BrokenPipeError once every recv fd is closed (parent gone),
        # so an orphaned child dies instead of hanging in send
        self.__send_conn.send(obj)

    def pop_all(self) -> list[Any]:
        # EOFError: sender gone and buffer drained — a dead child's buffered
        # results remain readable until then (#571 contract).
        # OSError: message truncated by a child killed mid-send; only
        # observable (instead of a blocking recv) because the parent dropped
        # its send-end copy via close_unused_in_parent().
        items = []
        with contextlib.suppress(EOFError, OSError):
            while self.__recv_conn.poll():
                items.append(self.__recv_conn.recv())
        return items

    def close_unused_in_parent(self):
        """Parent calls after start(): drops the parent's send-end copy so a
        dead child yields EOF rather than a partial message that blocks recv()."""
        if not self.__send_conn.closed:
            self.__send_conn.close()

    def close_unused_in_child(self):
        """Child calls at the top of run(): drops the child's recv-end copy so
        put() raises BrokenPipeError when the parent dies without terminate()."""
        if not self.__recv_conn.closed:
            self.__recv_conn.close()

    def close(self):
        if not self.__send_conn.closed:
            self.__send_conn.close()
        if not self.__recv_conn.closed:
            self.__recv_conn.close()


class PipeFlag:
    """
    Parent-set/child-read mp.Event replacement. Costs 0 semaphores.
    Level-triggered: bytes accumulate until clear(); is_set()/wait() poll
    without consuming.

    After close_unused_in_child(), a dead parent reads as a set flag on the
    child side: EOF makes poll() return True, so the child exits its run
    loop instead of running orphaned forever.
    """

    def __init__(self):
        self.__recv_conn, self.__send_conn = multiprocessing.Pipe(duplex=False)

    def set(self):
        # Dedup: poll does not consume, and once the child recvs the pending
        # byte the poll goes false again — so repeated sets against a busy or
        # stopped child coalesce into at most one buffered byte instead of
        # accumulating toward a pipe-buffer block of the setting thread
        if not self.__recv_conn.closed and self.__recv_conn.poll(0):
            return
        with contextlib.suppress(BrokenPipeError):
            self.__send_conn.send_bytes(b"\x01")

    def is_set(self) -> bool:
        return self.__recv_conn.poll(0)

    def wait(self, timeout: float | None = None) -> bool:
        return self.__recv_conn.poll(timeout)

    def clear(self):
        # On EOF (sender gone) poll() stays True and recv_bytes raises
        # EOFError — suppressed, leaving the flag permanently set
        with contextlib.suppress(EOFError):
            while self.__recv_conn.poll():
                self.__recv_conn.recv_bytes()

    def close_unused_in_parent(self):
        """Parent calls after start(): keeps BOTH ends, unlike PipeStream.

        The recv end is retained so set()'s dedup poll stays usable — without
        it every set() sends a byte and repeated force_scan() against a busy
        or stopped child accumulates toward a pipe-buffer block of the
        setting thread. Retaining it does not weaken orphan detection: the
        child's EOF-reads-as-set depends only on send fds closing, and parent
        death closes every parent fd anyway."""

    def close_unused_in_child(self):
        """Child calls at the top of run(): drops the child's send-end copy so
        parent death produces EOF (reads as set) on the child's recv end."""
        if not self.__send_conn.closed:
            self.__send_conn.close()

    def close(self):
        if not self.__send_conn.closed:
            self.__send_conn.close()
        if not self.__recv_conn.closed:
            self.__recv_conn.close()
