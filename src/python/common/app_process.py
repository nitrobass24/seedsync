# Copyright 2017, Inderpreet Singh, All rights reserved.

import logging
import sys
from abc import abstractmethod
from multiprocessing import Process, Queue, Event
import queue
import signal
import threading
from datetime import datetime

import tblib.pickling_support

from common import overrides, ServiceExit


tblib.pickling_support.install()


class ExceptionWrapper:
    """
    An exception wrapper that works across processes
    Source: https://stackoverflow.com/a/26096355/8571324
    """
    def __init__(self, ee):
        self.ee = ee
        __,  __, self.tb = sys.exc_info()

    def re_raise(self):
        raise self.ee.with_traceback(self.tb)


class AppProcess(Process):
    """
    Process with some additional functionality and fixes
      * Support for a multiprocessing logger
      * Removes signals to prevent join problems
      * Propagates exceptions to owner process
      * Safe terminate with timeout, followed by force terminate
    """

    # Timeout before process is force terminated
    __DEFAULT_TERMINATE_TIMEOUT_MS = 1000

    def __init__(self, name: str):
        self.__name = name
        super().__init__(name=self.__name)

        self._mp_log_queue = None
        self._mp_log_level = None
        self.logger = logging.getLogger(self.__name)
        self.__exception_queue = Queue()
        self._terminate = Event()

    def set_mp_log_queue(self, log_queue: Queue, log_level: int):
        """Configure cross-process logging. Must be called before start()."""
        self._mp_log_queue = log_queue
        self._mp_log_level = log_level

    @overrides(Process)
    def run(self):
        # With spawn, child processes start with default signal handlers, so these
        # resets are redundant. They are kept for safety in case the start method
        # is changed back to fork.
        signal.signal(signal.SIGTERM, signal.SIG_DFL)
        signal.signal(signal.SIGINT, signal.SIG_DFL)

        # Set the thread name for convenience
        threading.current_thread().name = self.__name

        # Configure the logger for this process
        if self._mp_log_queue is not None:
            from logging.handlers import QueueHandler
            root = logging.getLogger()
            root.handlers.clear()
            root.addHandler(QueueHandler(self._mp_log_queue))
            root.setLevel(self._mp_log_level)
            self.logger = root.getChild(self.__name)

        self.logger.debug("Started process")

        self.run_init()

        try:
            while not self._terminate.is_set():
                self.run_loop()
            self.logger.debug("Process received terminate flag")
        except ServiceExit:
            self.logger.debug("Process received a ServiceExit")
        except Exception as e:
            self.logger.debug("Process caught an exception")
            self.__exception_queue.put(ExceptionWrapper(e))
            raise
        finally:
            self.run_cleanup()

        self.logger.debug("Exiting process")

    @overrides(Process)
    def terminate(self):
        # Send a terminate signal, and force terminate after a timeout
        self._terminate.set()

        def elapsed_ms(start):
            delta_in_s = (datetime.now() - start).total_seconds()
            delta_in_ms = int(delta_in_s * 1000)
            return delta_in_ms

        timestamp_start = datetime.now()
        while self.is_alive() and \
                elapsed_ms(timestamp_start) < AppProcess.__DEFAULT_TERMINATE_TIMEOUT_MS:
            pass

        super().terminate()

    def close_queues(self):
        """Close multiprocessing queues to prevent file descriptor leaks.

        Must be called after the process has been joined. Subclasses should
        override to close their own queues and call super().
        """
        self.__exception_queue.close()
        self.__exception_queue.join_thread()
        # Release multiprocessing primitives that hold semaphore FDs
        self._terminate = None
        self._mp_log_queue = None

    def propagate_exception(self):
        """
        Raises any exception that was caught by the process
        :return:
        """
        try:
            exc = self.__exception_queue.get(block=False)
            raise exc.re_raise()
        except queue.Empty:
            pass

    @abstractmethod
    def run_init(self):
        """
        Called once before the run loop
        :return:
        """
        pass

    @abstractmethod
    def run_cleanup(self):
        """
        Called once before cleanup
        :return:
        """
        pass

    @abstractmethod
    def run_loop(self):
        """
        Process behaviour should be implemented here.
        This function is repeatedly called until process exits.
        The check for graceful shutdown is performed between the loop iterations,
        so try to limit the run time for this method.
        :return:
        """
        pass


class AppOneShotProcess(AppProcess):
    """
    App process that runs only once and then exits
    """
    def run_loop(self):
        self.run_once()
        self._terminate.set()

    def run_cleanup(self):
        pass

    def run_init(self):
        pass

    @abstractmethod
    def run_once(self):
        """
        Process behaviour should be implemented here
        :return:
        """
        pass
