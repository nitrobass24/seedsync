# Copyright 2017, Inderpreet Singh, All rights reserved.

import json

from bottle import HTTPResponse, request

from common import overrides, PathPairsConfig, PathPair
from ..web_app import IHandler, WebApp


class PathPairsHandler(IHandler):
    def __init__(self, path_pairs_config: PathPairsConfig):
        self.__config = path_pairs_config

    @overrides(IHandler)
    def add_routes(self, web_app: WebApp):
        web_app.add_handler("/server/pathpairs", self.__handle_list)
        web_app.add_post_handler("/server/pathpairs", self.__handle_create)
        web_app.add_put_handler("/server/pathpairs/<pair_id>", self.__handle_update)
        web_app.add_delete_handler("/server/pathpairs/<pair_id>", self.__handle_delete)

    def __handle_list(self):
        pairs = [p.to_dict() for p in self.__config.pairs]
        return HTTPResponse(
            body=json.dumps(pairs),
            headers={"Content-Type": "application/json"}
        )

    def __handle_create(self):
        try:
            data = json.loads(request.body.read().decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return HTTPResponse(body="Invalid JSON", status=400)
        if not isinstance(data, dict):
            return HTTPResponse(body="Expected JSON object", status=400)

        name = data.get("name", "")
        remote_path = data.get("remote_path", "")
        local_path = data.get("local_path", "")
        enabled = data.get("enabled", True)
        auto_queue = data.get("auto_queue", True)
        if not isinstance(name, str) or not isinstance(remote_path, str) or not isinstance(local_path, str):
            return HTTPResponse(body="name, remote_path, and local_path must be strings", status=400)
        if not isinstance(enabled, bool) or not isinstance(auto_queue, bool):
            return HTTPResponse(body="enabled and auto_queue must be booleans", status=400)
        name = name.strip()
        remote_path = remote_path.strip()
        local_path = local_path.strip()
        if not name:
            return HTTPResponse(body="name must not be empty", status=400)

        pair = PathPair(
            name=name,
            remote_path=remote_path,
            local_path=local_path,
            enabled=enabled,
            auto_queue=auto_queue,
        )
        self.__config.add_pair(pair)
        return HTTPResponse(
            body=json.dumps(pair.to_dict()),
            status=201,
            headers={"Content-Type": "application/json"}
        )

    def __handle_update(self, pair_id: str):
        existing = self.__config.get_pair(pair_id)
        if existing is None:
            return HTTPResponse(body="Path pair not found", status=404)

        try:
            data = json.loads(request.body.read().decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return HTTPResponse(body="Invalid JSON", status=400)
        if not isinstance(data, dict):
            return HTTPResponse(body="Expected JSON object", status=400)

        name = data.get("name", existing.name)
        remote_path = data.get("remote_path", existing.remote_path)
        local_path = data.get("local_path", existing.local_path)
        enabled = data.get("enabled", existing.enabled)
        auto_queue = data.get("auto_queue", existing.auto_queue)
        if not isinstance(name, str) or not isinstance(remote_path, str) or not isinstance(local_path, str):
            return HTTPResponse(body="name, remote_path, and local_path must be strings", status=400)
        if not isinstance(enabled, bool) or not isinstance(auto_queue, bool):
            return HTTPResponse(body="enabled and auto_queue must be booleans", status=400)
        name = name.strip()
        remote_path = remote_path.strip()
        local_path = local_path.strip()
        if not name:
            return HTTPResponse(body="name must not be empty", status=400)

        updated = PathPair(
            pair_id=pair_id,
            name=name,
            remote_path=remote_path,
            local_path=local_path,
            enabled=enabled,
            auto_queue=auto_queue,
        )
        try:
            self.__config.update_pair(updated)
        except ValueError:
            return HTTPResponse(body="Path pair not found", status=404)
        return HTTPResponse(
            body=json.dumps(updated.to_dict()),
            headers={"Content-Type": "application/json"}
        )

    def __handle_delete(self, pair_id: str):
        try:
            self.__config.remove_pair(pair_id)
        except ValueError:
            return HTTPResponse(body="Path pair not found", status=404)
        return HTTPResponse(body="Deleted")
