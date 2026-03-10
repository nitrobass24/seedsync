# Copyright 2017, Inderpreet Singh, All rights reserved.

import json

from common import overrides, PathPairsConfig, PathPair
from tests.integration.test_web.test_web_app import BaseTestWebApp


class TestPathPairsHandler(BaseTestWebApp):
    """Integration tests for the path pairs CRUD handler."""

    @overrides(BaseTestWebApp)
    def setUp(self):
        # Inject a real PathPairsConfig before the builder wires the handler
        self.path_pairs_config = PathPairsConfig()
        # We need context to exist before we can set path_pairs_config on it,
        # but super creates it. So we call super first, then rebuild with
        # the real config.
        super().setUp()
        # The builder already ran with context.path_pairs_config as a MagicMock.
        # Replace it with a real config and rebuild.
        self.context.path_pairs_config = self.path_pairs_config
        from web import WebAppBuilder
        from webtest import TestApp
        self.web_app_builder = WebAppBuilder(self.context,
                                             self.controller,
                                             self.auto_queue_persist)
        self.web_app = self.web_app_builder.build()
        self.test_app = TestApp(self.web_app,
                                extra_environ={"REMOTE_ADDR": "127.0.0.1"})

    # ---------------------------------------------------------------
    # Helper
    # ---------------------------------------------------------------
    def _add_pair(self, name="Movies", remote_path="/remote/movies",
                  local_path="/local/movies", enabled=True, auto_queue=True):
        """Add a pair directly to the config and return it."""
        pair = PathPair(name=name, remote_path=remote_path,
                        local_path=local_path, enabled=enabled,
                        auto_queue=auto_queue)
        self.path_pairs_config.add_pair(pair)
        return pair

    def _post_json(self, url, data, expect_errors=False):
        return self.test_app.post(
            url,
            params=json.dumps(data),
            content_type="application/json",
            expect_errors=expect_errors,
        )

    def _put_json(self, url, data, expect_errors=False):
        return self.test_app.put(
            url,
            params=json.dumps(data),
            content_type="application/json",
            expect_errors=expect_errors,
        )

    # ---------------------------------------------------------------
    # GET /server/pathpairs  (list)
    # ---------------------------------------------------------------
    def test_list_empty(self):
        resp = self.test_app.get("/server/pathpairs")
        self.assertEqual(200, resp.status_int)
        self.assertEqual([], json.loads(resp.text))

    def test_list_single(self):
        pair = self._add_pair()
        resp = self.test_app.get("/server/pathpairs")
        self.assertEqual(200, resp.status_int)
        pairs = json.loads(resp.text)
        self.assertEqual(1, len(pairs))
        self.assertEqual(pair.to_dict(), pairs[0])

    def test_list_multiple(self):
        p1 = self._add_pair(name="Movies", remote_path="/r/movies",
                            local_path="/l/movies")
        p2 = self._add_pair(name="TV", remote_path="/r/tv",
                            local_path="/l/tv")
        p3 = self._add_pair(name="Music", remote_path="/r/music",
                            local_path="/l/music")
        resp = self.test_app.get("/server/pathpairs")
        self.assertEqual(200, resp.status_int)
        pairs = json.loads(resp.text)
        self.assertEqual(3, len(pairs))
        ids = [p["id"] for p in pairs]
        self.assertIn(p1.id, ids)
        self.assertIn(p2.id, ids)
        self.assertIn(p3.id, ids)

    def test_list_response_content_type(self):
        resp = self.test_app.get("/server/pathpairs")
        self.assertIn("application/json", resp.content_type)

    def test_list_json_structure(self):
        """Verify the JSON shape matches what the Angular frontend expects."""
        self._add_pair(name="Test", remote_path="/r", local_path="/l",
                       enabled=False, auto_queue=False)
        resp = self.test_app.get("/server/pathpairs")
        pairs = json.loads(resp.text)
        pair = pairs[0]
        self.assertIn("id", pair)
        self.assertIn("name", pair)
        self.assertIn("remote_path", pair)
        self.assertIn("local_path", pair)
        self.assertIn("enabled", pair)
        self.assertIn("auto_queue", pair)
        self.assertEqual("Test", pair["name"])
        self.assertEqual("/r", pair["remote_path"])
        self.assertEqual("/l", pair["local_path"])
        self.assertFalse(pair["enabled"])
        self.assertFalse(pair["auto_queue"])

    # ---------------------------------------------------------------
    # POST /server/pathpairs  (create)
    # ---------------------------------------------------------------
    def test_create_valid(self):
        data = {
            "name": "Movies",
            "remote_path": "/remote/movies",
            "local_path": "/local/movies",
        }
        resp = self._post_json("/server/pathpairs", data)
        self.assertEqual(201, resp.status_int)
        body = json.loads(resp.text)
        self.assertEqual("Movies", body["name"])
        self.assertEqual("/remote/movies", body["remote_path"])
        self.assertEqual("/local/movies", body["local_path"])
        self.assertTrue(body["enabled"])
        self.assertTrue(body["auto_queue"])
        self.assertIn("id", body)
        # Verify persisted
        self.assertEqual(1, len(self.path_pairs_config.pairs))

    def test_create_with_booleans(self):
        data = {
            "name": "Disabled",
            "remote_path": "/r",
            "local_path": "/l",
            "enabled": False,
            "auto_queue": False,
        }
        resp = self._post_json("/server/pathpairs", data)
        self.assertEqual(201, resp.status_int)
        body = json.loads(resp.text)
        self.assertFalse(body["enabled"])
        self.assertFalse(body["auto_queue"])

    def test_create_missing_name(self):
        data = {"remote_path": "/r", "local_path": "/l"}
        resp = self._post_json("/server/pathpairs", data, expect_errors=True)
        self.assertEqual(400, resp.status_int)

    def test_create_empty_name(self):
        data = {"name": "  ", "remote_path": "/r", "local_path": "/l"}
        resp = self._post_json("/server/pathpairs", data, expect_errors=True)
        self.assertEqual(400, resp.status_int)
        self.assertIn("name", resp.text.lower())

    def test_create_missing_remote_path(self):
        data = {"name": "X", "local_path": "/l"}
        resp = self._post_json("/server/pathpairs", data, expect_errors=True)
        self.assertEqual(400, resp.status_int)

    def test_create_missing_local_path(self):
        data = {"name": "X", "remote_path": "/r"}
        resp = self._post_json("/server/pathpairs", data, expect_errors=True)
        self.assertEqual(400, resp.status_int)

    def test_create_empty_remote_path(self):
        data = {"name": "X", "remote_path": "  ", "local_path": "/l"}
        resp = self._post_json("/server/pathpairs", data, expect_errors=True)
        self.assertEqual(400, resp.status_int)
        self.assertIn("remote_path", resp.text.lower())

    def test_create_empty_local_path(self):
        data = {"name": "X", "remote_path": "/r", "local_path": " "}
        resp = self._post_json("/server/pathpairs", data, expect_errors=True)
        self.assertEqual(400, resp.status_int)
        self.assertIn("local_path", resp.text.lower())

    def test_create_duplicate_name(self):
        self._add_pair(name="Movies")
        data = {"name": "Movies", "remote_path": "/other", "local_path": "/other"}
        resp = self._post_json("/server/pathpairs", data, expect_errors=True)
        self.assertEqual(409, resp.status_int)
        self.assertIn("already exists", resp.text.lower())

    def test_create_invalid_json(self):
        resp = self.test_app.post(
            "/server/pathpairs",
            params="not json",
            content_type="application/json",
            expect_errors=True,
        )
        self.assertEqual(400, resp.status_int)

    def test_create_non_object_json(self):
        resp = self.test_app.post(
            "/server/pathpairs",
            params=json.dumps([1, 2, 3]),
            content_type="application/json",
            expect_errors=True,
        )
        self.assertEqual(400, resp.status_int)

    def test_create_invalid_boolean_type(self):
        data = {
            "name": "X",
            "remote_path": "/r",
            "local_path": "/l",
            "enabled": "yes",
        }
        resp = self._post_json("/server/pathpairs", data, expect_errors=True)
        self.assertEqual(400, resp.status_int)

    def test_create_special_characters_in_paths(self):
        data = {
            "name": "Sp3c!@l",
            "remote_path": "/remote/path with spaces/file (1)",
            "local_path": "/local/über/日本語",
        }
        resp = self._post_json("/server/pathpairs", data)
        self.assertEqual(201, resp.status_int)
        body = json.loads(resp.text)
        self.assertEqual("/remote/path with spaces/file (1)", body["remote_path"])
        self.assertEqual("/local/über/日本語", body["local_path"])

    # ---------------------------------------------------------------
    # PUT /server/pathpairs/<id>  (update)
    # ---------------------------------------------------------------
    def test_update_valid(self):
        pair = self._add_pair(name="Old Name")
        data = {
            "name": "New Name",
            "remote_path": "/new/remote",
            "local_path": "/new/local",
        }
        resp = self._put_json("/server/pathpairs/{}".format(pair.id), data)
        self.assertEqual(200, resp.status_int)
        body = json.loads(resp.text)
        self.assertEqual("New Name", body["name"])
        self.assertEqual("/new/remote", body["remote_path"])
        self.assertEqual("/new/local", body["local_path"])
        # Verify persisted
        updated = self.path_pairs_config.get_pair(pair.id)
        self.assertEqual("New Name", updated.name)

    def test_update_partial_fields(self):
        """Only the provided fields should change; others keep defaults."""
        pair = self._add_pair(name="Original", remote_path="/r/orig",
                              local_path="/l/orig", enabled=True, auto_queue=True)
        data = {"name": "Updated"}
        resp = self._put_json("/server/pathpairs/{}".format(pair.id), data)
        self.assertEqual(200, resp.status_int)
        body = json.loads(resp.text)
        self.assertEqual("Updated", body["name"])
        # Original values preserved
        self.assertEqual("/r/orig", body["remote_path"])
        self.assertEqual("/l/orig", body["local_path"])
        self.assertTrue(body["enabled"])
        self.assertTrue(body["auto_queue"])

    def test_update_toggle_booleans(self):
        pair = self._add_pair(name="Test", enabled=True, auto_queue=True)
        data = {"enabled": False, "auto_queue": False}
        resp = self._put_json("/server/pathpairs/{}".format(pair.id), data)
        self.assertEqual(200, resp.status_int)
        body = json.loads(resp.text)
        self.assertFalse(body["enabled"])
        self.assertFalse(body["auto_queue"])

    def test_update_not_found(self):
        data = {"name": "Ghost"}
        resp = self._put_json("/server/pathpairs/nonexistent-id", data,
                              expect_errors=True)
        self.assertEqual(404, resp.status_int)

    def test_update_duplicate_name(self):
        self._add_pair(name="Movies")
        p2 = self._add_pair(name="TV", remote_path="/r/tv",
                            local_path="/l/tv")
        data = {"name": "Movies"}
        resp = self._put_json("/server/pathpairs/{}".format(p2.id), data,
                              expect_errors=True)
        self.assertEqual(409, resp.status_int)
        self.assertIn("already exists", resp.text.lower())

    def test_update_same_name_on_same_pair(self):
        """Renaming a pair to its own name should succeed."""
        pair = self._add_pair(name="Movies")
        data = {"name": "Movies", "remote_path": "/new/r", "local_path": "/new/l"}
        resp = self._put_json("/server/pathpairs/{}".format(pair.id), data)
        self.assertEqual(200, resp.status_int)

    def test_update_invalid_json(self):
        pair = self._add_pair(name="Test")
        resp = self.test_app.put(
            "/server/pathpairs/{}".format(pair.id),
            params="bad json",
            content_type="application/json",
            expect_errors=True,
        )
        self.assertEqual(400, resp.status_int)

    def test_update_empty_name(self):
        pair = self._add_pair(name="Test")
        data = {"name": "  "}
        resp = self._put_json("/server/pathpairs/{}".format(pair.id), data,
                              expect_errors=True)
        self.assertEqual(400, resp.status_int)

    # ---------------------------------------------------------------
    # DELETE /server/pathpairs/<id>
    # ---------------------------------------------------------------
    def test_delete_valid(self):
        pair = self._add_pair(name="Delete Me")
        resp = self.test_app.delete(
            "/server/pathpairs/{}".format(pair.id))
        self.assertEqual(204, resp.status_int)
        self.assertEqual(0, len(self.path_pairs_config.pairs))

    def test_delete_not_found(self):
        resp = self.test_app.delete(
            "/server/pathpairs/nonexistent-id",
            expect_errors=True)
        self.assertEqual(404, resp.status_int)

    def test_delete_only_target(self):
        """Deleting one pair should not affect others."""
        p1 = self._add_pair(name="Keep")
        p2 = self._add_pair(name="Remove", remote_path="/r2", local_path="/l2")
        resp = self.test_app.delete(
            "/server/pathpairs/{}".format(p2.id))
        self.assertEqual(204, resp.status_int)
        remaining = self.path_pairs_config.pairs
        self.assertEqual(1, len(remaining))
        self.assertEqual(p1.id, remaining[0].id)

    # ---------------------------------------------------------------
    # Full CRUD round-trip
    # ---------------------------------------------------------------
    def test_crud_round_trip(self):
        """Create, read, update, delete through the HTTP API."""
        # Create
        create_resp = self._post_json("/server/pathpairs", {
            "name": "RoundTrip",
            "remote_path": "/r/rt",
            "local_path": "/l/rt",
        })
        self.assertEqual(201, create_resp.status_int)
        pair_id = json.loads(create_resp.text)["id"]

        # List
        list_resp = self.test_app.get("/server/pathpairs")
        pairs = json.loads(list_resp.text)
        self.assertEqual(1, len(pairs))
        self.assertEqual(pair_id, pairs[0]["id"])

        # Update
        update_resp = self._put_json(
            "/server/pathpairs/{}".format(pair_id),
            {"name": "RoundTrip Updated", "enabled": False},
        )
        self.assertEqual(200, update_resp.status_int)
        body = json.loads(update_resp.text)
        self.assertEqual("RoundTrip Updated", body["name"])
        self.assertFalse(body["enabled"])

        # Delete
        del_resp = self.test_app.delete(
            "/server/pathpairs/{}".format(pair_id))
        self.assertEqual(204, del_resp.status_int)

        # Confirm gone
        list_resp2 = self.test_app.get("/server/pathpairs")
        self.assertEqual([], json.loads(list_resp2.text))
