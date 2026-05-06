# Copyright 2017, Inderpreet Singh, All rights reserved.

import logging
import os
import shutil
import sys
import tempfile
import unittest
from unittest.mock import MagicMock

from webtest import TestApp

from common import Config, IntegrationsConfig, PathPairsConfig, Status, overrides
from controller import AutoQueuePersist
from web import WebAppBuilder


class BaseTestWebApp(unittest.TestCase):
    """
    Base class for testing web app
    Sets up the web app with mocks
    """

    @overrides(unittest.TestCase)
    def setUp(self):
        self.context = MagicMock()
        self.controller = MagicMock()

        # Mock the base logger
        logger = logging.getLogger()
        handler = logging.StreamHandler(sys.stdout)
        logger.addHandler(handler)
        self.addCleanup(logger.removeHandler, handler)
        logger.setLevel(logging.DEBUG)
        formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(name)s - %(message)s")
        handler.setFormatter(formatter)
        self.context.logger = logger

        # Model files
        self.model_files = []

        # Real status
        self.context.status = Status()

        # Real config
        self.context.config = Config()

        # Real integrations and path pairs configs
        self.context.integrations_config = IntegrationsConfig()
        self.context.path_pairs_config = PathPairsConfig()

        # Real auto-queue persist
        self.auto_queue_persist = AutoQueuePersist()

        # Temp directory for flush-on-write file paths
        self._test_tmpdir = tempfile.mkdtemp()
        self.context.config_path = os.path.join(self._test_tmpdir, "settings.cfg")
        self.context.path_pairs_path = os.path.join(self._test_tmpdir, "path_pairs.json")
        self.context.integrations_path = os.path.join(self._test_tmpdir, "integrations.json")
        self.context.auto_queue_persist_path = os.path.join(self._test_tmpdir, "autoqueue.persist")
        self.context.controller_persist_path = os.path.join(self._test_tmpdir, "controller.persist")

        # Capture the model listener
        def capture_listener(listener):
            self.model_listener = listener
            return self.model_files

        self.model_listener = None
        self.controller.get_model_files_and_add_listener = MagicMock()
        self.controller.get_model_files_and_add_listener.side_effect = capture_listener
        self.controller.remove_model_listener = MagicMock()

        # noinspection PyTypeChecker
        self.web_app_builder = WebAppBuilder(self.context, self.controller, self.auto_queue_persist)
        self.web_app = self.web_app_builder.build()
        self.test_app = TestApp(self.web_app)

    @overrides(unittest.TestCase)
    def tearDown(self):
        shutil.rmtree(self._test_tmpdir, ignore_errors=True)


class TestWebApp(BaseTestWebApp):
    def test_process(self):
        self.web_app.process()
