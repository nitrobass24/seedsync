# Copyright 2017, Inderpreet Singh, All rights reserved.

import logging
import unittest

from common import Args, Config, Context, PathPairsConfig, Status
from common.path_pairs_config import PathPair


def _make_context():
    """Create a basic Context for testing."""
    # Tests use self.assertLogs(...) which installs its own capture handler,
    # so we don't need to attach a StreamHandler here. Attaching one would
    # leak across tests because loggers are singletons.
    logger = logging.getLogger("test_context")
    logger.setLevel(logging.DEBUG)
    web_logger = logging.getLogger("test_context.web")
    config = Config()
    args = Args()
    status = Status()
    return Context(logger=logger, web_access_logger=web_logger, config=config, args=args, status=status)


class TestCreateChildContext(unittest.TestCase):
    """Tests for Context.create_child_context."""

    def test_returns_copy_with_child_logger(self):
        ctx = _make_context()
        child = ctx.create_child_context("child1")
        self.assertEqual(child.logger.name, "test_context.child1")
        # Parent logger unchanged
        self.assertEqual(ctx.logger.name, "test_context")

    def test_child_shares_config_reference(self):
        ctx = _make_context()
        child = ctx.create_child_context("child2")
        self.assertIs(child.config, ctx.config)
        self.assertIs(child.status, ctx.status)
        self.assertIs(child.args, ctx.args)


class TestPrintToLog(unittest.TestCase):
    """Tests for Context.print_to_log."""

    def test_redacts_sensitive_fields(self):
        """Sensitive fields (passwords) are redacted in log output."""
        ctx = _make_context()
        ctx.config.lftp.remote_password = "supersecret"

        with self.assertLogs("test_context", level="DEBUG") as log_ctx:
            ctx.print_to_log()

        all_output = "\n".join(log_ctx.output)
        self.assertNotIn("supersecret", all_output)
        self.assertIn("********", all_output)

    def test_handles_no_path_pairs(self):
        """print_to_log handles absent path pairs without error."""
        ctx = _make_context()
        ctx.path_pairs_config = PathPairsConfig()

        with self.assertLogs("test_context", level="DEBUG") as log_ctx:
            ctx.print_to_log()

        all_output = "\n".join(log_ctx.output)
        self.assertIn("Path Pairs: (none)", all_output)

    def test_handles_present_path_pairs(self):
        """print_to_log logs path pair details when pairs are present."""
        ctx = _make_context()
        ppc = PathPairsConfig()
        pair = PathPair(remote_path="/remote/test", local_path="/local/test")
        pair.name = "TestPair"
        pair.enabled = True
        pair.auto_queue = True
        ppc._pairs = [pair]
        ctx.path_pairs_config = ppc

        with self.assertLogs("test_context", level="DEBUG") as log_ctx:
            ctx.print_to_log()

        all_output = "\n".join(log_ctx.output)
        self.assertIn("TestPair", all_output)
        self.assertIn("/remote/test", all_output)


class TestArgsAsDict(unittest.TestCase):
    """Tests for Args.as_dict."""

    def test_serializes_all_fields(self):
        args = Args()
        args.local_path_to_scanfs = "/scan"
        args.html_path = "/html"
        args.debug = True
        args.exit = False
        args.logdir = "/logs"

        d = args.as_dict()
        self.assertEqual(d["local_path_to_scanfs"], "/scan")
        self.assertEqual(d["html_path"], "/html")
        self.assertEqual(d["debug"], "True")
        self.assertEqual(d["exit"], "False")
        self.assertEqual(d["logdir"], "/logs")

    def test_none_values_serialized_as_string(self):
        args = Args()
        d = args.as_dict()
        self.assertEqual(d["local_path_to_scanfs"], "None")
        self.assertEqual(d["html_path"], "None")
