# Copyright 2017, Inderpreet Singh, All rights reserved.

import json
import unittest
import urllib.error
from unittest.mock import MagicMock, patch

from common import ArrInstance, IntegrationsConfig, PathPair, PathPairsConfig, overrides
from tests.integration.test_web.test_web_app import BaseTestWebApp


class TestIntegrationsHandler(BaseTestWebApp):
    """Integration tests for the *arr instances CRUD + test handler."""

    @overrides(BaseTestWebApp)
    def setUp(self):
        self.integrations_config = IntegrationsConfig()
        self.path_pairs_config = PathPairsConfig()
        super().setUp()
        self.context.integrations_config = self.integrations_config
        self.context.path_pairs_config = self.path_pairs_config
        from webtest import TestApp

        from web import WebAppBuilder

        self.web_app_builder = WebAppBuilder(self.context, self.controller, self.auto_queue_persist)
        self.web_app = self.web_app_builder.build()
        self.test_app = TestApp(self.web_app, extra_environ={"REMOTE_ADDR": "127.0.0.1"})

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _add_instance(self, name="Sonarr", kind="sonarr", url="http://localhost:8989", api_key="key", enabled=True):
        instance = ArrInstance(name=name, kind=kind, url=url, api_key=api_key, enabled=enabled)
        self.integrations_config.add_instance(instance)
        return instance

    def _post(self, url, data, expect_errors=False):
        return self.test_app.post(
            url,
            params=json.dumps(data),
            content_type="application/json",
            expect_errors=expect_errors,
        )

    def _put(self, url, data, expect_errors=False):
        return self.test_app.put(
            url,
            params=json.dumps(data),
            content_type="application/json",
            expect_errors=expect_errors,
        )

    # ------------------------------------------------------------------
    # GET /server/integrations
    # ------------------------------------------------------------------
    def test_list_empty(self):
        resp = self.test_app.get("/server/integrations")
        self.assertEqual(200, resp.status_int)
        self.assertEqual([], json.loads(resp.text))

    def test_list_redacts_api_key(self):
        self._add_instance(name="Sonarr", api_key="secret")
        resp = self.test_app.get("/server/integrations")
        body = json.loads(resp.text)
        self.assertEqual(1, len(body))
        self.assertEqual("********", body[0]["api_key"])
        self.assertNotIn("secret", resp.text)

    def test_list_blank_api_key_is_not_redacted(self):
        """A truly empty api_key surfaces as '' rather than the sentinel."""
        self._add_instance(name="Sonarr", api_key="", enabled=False)
        body = json.loads(self.test_app.get("/server/integrations").text)
        self.assertEqual("", body[0]["api_key"])

    # ------------------------------------------------------------------
    # POST /server/integrations
    # ------------------------------------------------------------------
    def test_create_valid(self):
        data = {"name": "Sonarr", "kind": "sonarr", "url": "http://localhost:8989", "api_key": "abc"}
        resp = self._post("/server/integrations", data)
        self.assertEqual(201, resp.status_int)
        body = json.loads(resp.text)
        self.assertEqual("Sonarr", body["name"])
        self.assertEqual("sonarr", body["kind"])
        self.assertEqual("********", body["api_key"])
        self.assertIn("id", body)
        self.assertEqual(1, len(self.integrations_config.instances))

    def test_create_rejects_unknown_kind(self):
        resp = self._post(
            "/server/integrations",
            {"name": "X", "kind": "lidarr", "url": "http://x", "api_key": "k"},
            expect_errors=True,
        )
        self.assertEqual(400, resp.status_int)
        self.assertIn("kind", resp.text.lower())

    def test_create_rejects_bad_scheme(self):
        resp = self._post(
            "/server/integrations",
            {"name": "X", "kind": "sonarr", "url": "ftp://x", "api_key": "k"},
            expect_errors=True,
        )
        self.assertEqual(400, resp.status_int)

    def test_create_allows_empty_url(self):
        """Empty URL is allowed at create time so users can save partial config."""
        resp = self._post(
            "/server/integrations",
            {"name": "X", "kind": "sonarr", "url": "", "api_key": ""},
        )
        self.assertEqual(201, resp.status_int)

    def test_create_rejects_empty_name(self):
        resp = self._post(
            "/server/integrations",
            {"name": "  ", "kind": "sonarr", "url": "http://x", "api_key": "k"},
            expect_errors=True,
        )
        self.assertEqual(400, resp.status_int)

    def test_create_rejects_duplicate_name(self):
        self._add_instance(name="Sonarr — TV")
        resp = self._post(
            "/server/integrations",
            {"name": "Sonarr — TV", "kind": "sonarr", "url": "http://y", "api_key": "k"},
            expect_errors=True,
        )
        self.assertEqual(409, resp.status_int)

    def test_create_invalid_json(self):
        resp = self.test_app.post(
            "/server/integrations",
            params="not json",
            content_type="application/json",
            expect_errors=True,
        )
        self.assertEqual(400, resp.status_int)

    # ------------------------------------------------------------------
    # PUT /server/integrations/<id>
    # ------------------------------------------------------------------
    def test_update_valid(self):
        inst = self._add_instance(api_key="old")
        resp = self._put(
            f"/server/integrations/{inst.id}",
            {"name": "Renamed", "kind": "sonarr", "url": "http://new", "api_key": "new"},
        )
        self.assertEqual(200, resp.status_int)
        body = json.loads(resp.text)
        self.assertEqual("Renamed", body["name"])
        # Persisted
        self.assertEqual("new", self.integrations_config.get_instance(inst.id).api_key)

    def test_update_with_redacted_sentinel_keeps_existing_key(self):
        inst = self._add_instance(api_key="real-secret")
        resp = self._put(
            f"/server/integrations/{inst.id}",
            {"name": inst.name, "kind": "sonarr", "url": inst.url, "api_key": "********"},
        )
        self.assertEqual(200, resp.status_int)
        # Existing secret preserved
        self.assertEqual("real-secret", self.integrations_config.get_instance(inst.id).api_key)

    def test_update_partial_fields(self):
        inst = self._add_instance(name="Original", url="http://orig", api_key="k")
        resp = self._put(f"/server/integrations/{inst.id}", {"enabled": False})
        self.assertEqual(200, resp.status_int)
        updated = self.integrations_config.get_instance(inst.id)
        self.assertEqual("Original", updated.name)
        self.assertEqual("http://orig", updated.url)
        self.assertEqual("k", updated.api_key)
        self.assertFalse(updated.enabled)

    def test_update_not_found(self):
        resp = self._put(
            "/server/integrations/nonexistent",
            {"name": "X", "kind": "sonarr", "url": "http://x", "api_key": "k"},
            expect_errors=True,
        )
        self.assertEqual(404, resp.status_int)

    def test_update_duplicate_name(self):
        a = self._add_instance(name="A")
        b = self._add_instance(name="B", url="http://b")
        resp = self._put(f"/server/integrations/{b.id}", {"name": "A"}, expect_errors=True)
        self.assertEqual(409, resp.status_int)
        # Original a unchanged
        self.assertEqual("A", self.integrations_config.get_instance(a.id).name)

    # ------------------------------------------------------------------
    # DELETE /server/integrations/<id>
    # ------------------------------------------------------------------
    def test_delete_valid(self):
        inst = self._add_instance()
        resp = self.test_app.delete(f"/server/integrations/{inst.id}")
        self.assertEqual(204, resp.status_int)
        self.assertEqual(0, len(self.integrations_config.instances))

    def test_delete_not_found(self):
        resp = self.test_app.delete("/server/integrations/nonexistent", expect_errors=True)
        self.assertEqual(404, resp.status_int)

    def test_delete_detaches_from_path_pairs(self):
        """Deleting an instance must remove it from any pair's arr_target_ids."""
        inst = self._add_instance()
        pair = PathPair(
            name="TV",
            remote_path="/r/tv",
            local_path="/l/tv",
            arr_target_ids=[inst.id],
        )
        self.path_pairs_config.add_pair(pair)
        self.test_app.delete(f"/server/integrations/{inst.id}")
        refreshed = self.path_pairs_config.get_pair(pair.id)
        self.assertEqual([], refreshed.arr_target_ids)

    # ------------------------------------------------------------------
    # POST /server/integrations/<id>/test
    # ------------------------------------------------------------------
    @patch("web.handler.integrations.urllib.request.urlopen")
    def test_test_success(self, mock_urlopen):
        inst = self._add_instance(kind="sonarr", url="http://s", api_key="k")
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"version": "4.0.0.1"}).encode("utf-8")
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        resp = self._post(f"/server/integrations/{inst.id}/test", {})
        self.assertEqual(200, resp.status_int)
        body = json.loads(resp.text)
        self.assertTrue(body["success"])
        self.assertEqual("4.0.0.1", body["version"])

    @patch("web.handler.integrations.urllib.request.urlopen")
    def test_test_failure_does_not_leak_details(self, mock_urlopen):
        inst = self._add_instance(kind="sonarr", url="http://192.168.1.50:8989", api_key="k")
        mock_urlopen.side_effect = urllib.error.URLError("connection refused to 192.168.1.50:8989")
        resp = self._post(f"/server/integrations/{inst.id}/test", {}, expect_errors=True)
        self.assertEqual(502, resp.status_int)
        raw = resp.text
        body = json.loads(raw)
        self.assertIn("connection failed", body["error"].lower())
        self.assertNotIn("192.168.1.50", raw)
        self.assertNotIn("URLError", raw)

    def test_test_missing_url(self):
        inst = self._add_instance(url="", api_key="k")
        resp = self._post(f"/server/integrations/{inst.id}/test", {}, expect_errors=True)
        self.assertEqual(400, resp.status_int)

    def test_test_missing_api_key(self):
        inst = self._add_instance(url="http://x", api_key="")
        resp = self._post(f"/server/integrations/{inst.id}/test", {}, expect_errors=True)
        self.assertEqual(400, resp.status_int)

    def test_test_unknown_instance(self):
        resp = self._post("/server/integrations/nonexistent/test", {}, expect_errors=True)
        self.assertEqual(404, resp.status_int)


if __name__ == "__main__":
    unittest.main()
