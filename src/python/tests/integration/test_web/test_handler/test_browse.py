# Copyright 2017, Inderpreet Singh, All rights reserved.

import json
import os
from unittest.mock import patch

from ssh import SshcpError
from tests.integration.test_web.test_web_app import BaseTestWebApp


class TestBrowseHandlerLocal(BaseTestWebApp):
    def setUp(self):
        super().setUp()
        self.browse_root = os.path.join(self._test_tmpdir, "browse-root")
        os.makedirs(os.path.join(self.browse_root, "sub_b"))
        os.makedirs(os.path.join(self.browse_root, "Sub_a"))
        with open(os.path.join(self.browse_root, "a_file.txt"), "w") as f:
            f.write("not a directory")

    def test_lists_only_directories_case_insensitive_sorted(self):
        resp = self.test_app.get("/server/browse/local", {"path": self.browse_root})
        self.assertEqual(200, resp.status_int)
        body = json.loads(resp.text)
        self.assertEqual(self.browse_root, body["path"])
        self.assertEqual(["Sub_a", "sub_b"], body["directories"])

    def test_parent_is_dirname_of_path(self):
        resp = self.test_app.get("/server/browse/local", {"path": self.browse_root})
        body = json.loads(resp.text)
        self.assertEqual(os.path.dirname(self.browse_root), body["parent"])

    def test_root_has_no_parent(self):
        resp = self.test_app.get("/server/browse/local", {"path": "/"})
        self.assertEqual(200, resp.status_int)
        body = json.loads(resp.text)
        self.assertIsNone(body["parent"])

    def test_missing_path_defaults_to_root(self):
        resp = self.test_app.get("/server/browse/local")
        self.assertEqual(200, resp.status_int)
        body = json.loads(resp.text)
        self.assertEqual("/", body["path"])

    def test_not_a_directory_is_rejected(self):
        file_path = os.path.join(self.browse_root, "a_file.txt")
        resp = self.test_app.get("/server/browse/local", {"path": file_path}, expect_errors=True)
        self.assertEqual(400, resp.status_int)
        body = json.loads(resp.text)
        self.assertIn("Not a directory", body["error"])

    def test_nonexistent_path_is_rejected(self):
        resp = self.test_app.get(
            "/server/browse/local", {"path": os.path.join(self.browse_root, "does-not-exist")}, expect_errors=True
        )
        self.assertEqual(400, resp.status_int)


class TestBrowseHandlerRemote(BaseTestWebApp):
    def _configure_remote(self):
        self.context.config.lftp.remote_address = "example.com"
        self.context.config.lftp.remote_username = "user"
        self.context.config.lftp.remote_password = "pass"
        self.context.config.lftp.remote_port = 22

    def test_missing_required_settings(self):
        # lftp fields default to None/unset; never call _configure_remote().
        resp = self.test_app.get("/server/browse/remote", expect_errors=True)
        self.assertEqual(400, resp.status_int)
        body = json.loads(resp.text)
        self.assertIn("remote_address", body["error"])

    def test_lists_only_directory_entries_from_ls_dash_1p(self):
        self._configure_remote()
        raw_output = b"sub_b/\na_file.txt\nSub_a/\n"
        with patch("web.lftp_ssh.Sshcp.shell", return_value=raw_output):
            resp = self.test_app.get("/server/browse/remote", {"path": "/remote/dir"})
        self.assertEqual(200, resp.status_int)
        body = json.loads(resp.text)
        self.assertEqual("/remote/dir", body["path"])
        self.assertEqual(["Sub_a", "sub_b"], body["directories"])
        self.assertEqual("/remote", body["parent"])

    def test_path_defaults_to_configured_remote_path(self):
        self._configure_remote()
        self.context.config.lftp.remote_path = "/configured/path"
        with patch("web.lftp_ssh.Sshcp.shell", return_value=b"") as mock_shell:
            resp = self.test_app.get("/server/browse/remote")
        self.assertEqual(200, resp.status_int)
        self.assertIn("/configured/path", mock_shell.call_args[0][0])

    def test_root_path_has_no_parent(self):
        self._configure_remote()
        with patch("web.lftp_ssh.Sshcp.shell", return_value=b""):
            resp = self.test_app.get("/server/browse/remote", {"path": "/"})
        body = json.loads(resp.text)
        self.assertIsNone(body["parent"])

    def test_ssh_failure_surfaces_error(self):
        self._configure_remote()
        with patch("web.lftp_ssh.Sshcp.shell", side_effect=SshcpError("Connection refused")):
            resp = self.test_app.get("/server/browse/remote", {"path": "/remote/dir"}, expect_errors=True)
        self.assertEqual(502, resp.status_int)
        body = json.loads(resp.text)
        self.assertEqual("Connection refused", body["error"])

    def test_path_with_spaces_is_shell_quoted(self):
        self._configure_remote()
        with patch("web.lftp_ssh.Sshcp.shell", return_value=b"") as mock_shell:
            resp = self.test_app.get("/server/browse/remote", {"path": "/remote/has space"})
        self.assertEqual(200, resp.status_int)
        sent_command = mock_shell.call_args[0][0]
        self.assertIn("'/remote/has space'", sent_command)
