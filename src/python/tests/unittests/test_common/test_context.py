# Copyright 2017, Inderpreet Singh, All rights reserved.

import unittest
from unittest.mock import MagicMock

from common import Args, Config, Context, Status


class TestContext(unittest.TestCase):
    def test_print_to_log_masks_sensitive_values(self):
        logger = MagicMock()
        config = Config()
        config.lftp.remote_password = "super-secret-password"
        config.web.api_key = "super-secret-api-key"
        config.lftp.remote_address = "seedbox"

        context = Context(
            logger=logger,
            web_access_logger=MagicMock(),
            config=config,
            args=Args(),
            status=Status(),
        )

        context.print_to_log()

        debug_lines = [call.args[0] for call in logger.debug.call_args_list]
        self.assertIn("  Lftp.remote_password: ********", debug_lines)
        self.assertIn("  Web.api_key: ********", debug_lines)
        self.assertNotIn("  Lftp.remote_password: super-secret-password", debug_lines)
        self.assertNotIn("  Web.api_key: super-secret-api-key", debug_lines)
