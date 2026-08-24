# Copyright 2017, Inderpreet Singh, All rights reserved.


# my libs
from typing import override

from common import Context, Job

from .auto_queue import AutoQueue
from .controller import Controller


class ControllerJob(Job):
    """
    The controller service
    Handles querying and downloading of files
    """

    def __init__(self, context: Context, controller: Controller, auto_queue: AutoQueue):
        super().__init__(name=self.__class__.__name__, context=context)
        self.__controller = controller
        self.__auto_queue = auto_queue

    @override
    def setup(self):
        self.__controller.start()

    @override
    def execute(self):
        self.__controller.process()
        self.__auto_queue.process()

    @override
    def cleanup(self):
        self.__controller.exit()
