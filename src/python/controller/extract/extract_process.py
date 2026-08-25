# Copyright 2017, Inderpreet Singh, All rights reserved.

from __future__ import annotations

import logging
import multiprocessing
import queue
import threading
import time
from datetime import datetime
from typing import override

from common import AppProcess, PipeStream

from .dispatch import ExtractDispatch, ExtractDispatchError, ExtractListener, ExtractStatus
from .extract_request import ExtractRequest


class ExtractStatusResult:
    def __init__(self, timestamp: datetime, statuses: list[ExtractStatus]):
        self.timestamp = timestamp
        self.statuses = statuses


class ExtractCompletedResult:
    def __init__(self, timestamp: datetime, name: str, is_dir: bool, pair_id: str | None = None):
        self.timestamp = timestamp
        self.name = name
        self.is_dir = is_dir
        self.pair_id = pair_id


class ExtractFailedResult:
    def __init__(self, timestamp: datetime, name: str, is_dir: bool, pair_id: str | None = None):
        self.timestamp = timestamp
        self.name = name
        self.is_dir = is_dir
        self.pair_id = pair_id


class ExtractProcess(AppProcess):
    __DEFAULT_SLEEP_INTERVAL_IN_SECS = 0.5

    class __ExtractListener(ExtractListener):
        def __init__(
            self,
            logger: logging.Logger,
            completed_queue: PipeStream,
            failed_queue: PipeStream,
            failed_queue_lock: threading.Lock,
        ):
            self.logger = logger
            self.completed_queue = completed_queue
            self.failed_queue = failed_queue
            self.failed_queue_lock = failed_queue_lock

        def extract_completed(self, name: str, is_dir: bool, pair_id: str | None = None):
            self.logger.info(f"Extraction completed for {name}")
            completed_result = ExtractCompletedResult(
                timestamp=datetime.now(), name=name, is_dir=is_dir, pair_id=pair_id
            )
            self.completed_queue.put(completed_result)

        def extract_failed(self, name: str, is_dir: bool, pair_id: str | None = None):
            self.logger.error(f"Extraction failed for {name}")
            failed_result = ExtractFailedResult(timestamp=datetime.now(), name=name, is_dir=is_dir, pair_id=pair_id)
            with self.failed_queue_lock:
                self.failed_queue.put(failed_result)

    def __init__(self):
        super().__init__(name=self.__class__.__name__)
        self.__command_queue: multiprocessing.Queue[ExtractRequest] = multiprocessing.Queue()
        self.__status_result_queue = PipeStream()
        self.__completed_result_queue = PipeStream()
        self.__failed_result_queue = PipeStream()
        self.__dispatch: ExtractDispatch | None = None
        # Serializes the two same-process producer threads of the failed
        # queue (ExtractWorker via the listener, and run_loop's dispatch-error
        # path) — concurrent send() on one Connection end can corrupt data.
        # A threading.Lock suffices (both are child-process threads) and costs
        # no semaphore, unlike an mp.Lock (#654). Created child-side in
        # run_init because locks don't survive spawn pickling.
        self.__failed_queue_lock: threading.Lock | None = None

    @override
    def run_init(self):
        # Create dispatch inside the process
        self.__dispatch = ExtractDispatch()
        self.__failed_queue_lock = threading.Lock()

        # Add extract listener
        listener = ExtractProcess.__ExtractListener(
            logger=self.logger,
            completed_queue=self.__completed_result_queue,
            failed_queue=self.__failed_result_queue,
            failed_queue_lock=self.__failed_queue_lock,
        )
        self.__dispatch.add_listener(listener)

        # Start dispatch
        self.__dispatch.start()

    @override
    def run_cleanup(self):
        assert self.__dispatch is not None
        self.__dispatch.stop()

    @override
    def run_loop(self):
        assert self.__dispatch is not None
        assert self.__failed_queue_lock is not None
        # Forward all the extract commands
        try:
            while True:
                req = self.__command_queue.get(block=False)
                try:
                    self.__dispatch.extract(req)
                except ExtractDispatchError as e:
                    self.logger.warning(str(e))
                    # Report dispatch errors as failures so the controller
                    # can transition the file to EXTRACT_FAILED state
                    failed_result = ExtractFailedResult(
                        timestamp=datetime.now(),
                        name=req.model_file.name,
                        is_dir=req.model_file.is_dir,
                        pair_id=req.pair_id,
                    )
                    with self.__failed_queue_lock:
                        self.__failed_result_queue.put(failed_result)
        except queue.Empty:
            pass

        # Queue the latest status
        statuses = self.__dispatch.status()
        status_result = ExtractStatusResult(timestamp=datetime.now(), statuses=statuses)
        self.__status_result_queue.put(status_result)

        time.sleep(ExtractProcess.__DEFAULT_SLEEP_INTERVAL_IN_SECS)

    @override
    def close_queues(self):
        self.__command_queue.close()
        self.__command_queue.join_thread()
        self.__status_result_queue.close()
        self.__completed_result_queue.close()
        self.__failed_result_queue.close()
        super().close_queues()

    def extract(self, req: ExtractRequest):
        """
        Process-safe method to queue an extraction
        :param req:
        :return:
        """
        self.__command_queue.put(req)

    def pop_latest_statuses(self) -> ExtractStatusResult | None:
        """
        Process-safe method to retrieve latest extract status
        Returns none if no new status is available since the last time
        this method was called
        :return:
        """
        results = self.__status_result_queue.pop_all()
        return results[-1] if results else None

    def pop_completed(self) -> list[ExtractCompletedResult]:
        """
        Process-safe method to retrieve list of newly completed extractions
        Returns an empty list if no new extractions were completed since the
        last time this method was called.
        :return:
        """
        return self.__completed_result_queue.pop_all()

    def pop_failed(self) -> list[ExtractFailedResult]:
        """
        Process-safe method to retrieve list of newly failed extractions
        Returns an empty list if no new failures since the last call.
        :return:
        """
        return self.__failed_result_queue.pop_all()
