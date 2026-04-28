# Copyright 2017, Inderpreet Singh, All rights reserved.

import json
from typing import Any, cast

from bottle import HTTPResponse, request

from common import PathPair, PathPairsConfig, overrides

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
        return HTTPResponse(body=json.dumps(pairs), headers={"Content-Type": "application/json"})

    @staticmethod
    def __validate_pair_params(
        data: dict[str, Any],
        defaults: PathPair | None = None,
    ) -> "HTTPResponse | tuple[str, str, str, bool, bool, list[str]]":
        """Validate and extract path pair parameters from request data.

        Returns (name, remote_path, local_path, enabled, auto_queue, arr_target_ids)
        or an HTTPResponse on error. When defaults is provided (a PathPair), missing
        keys fall back to its values.
        """
        d = defaults
        name = data.get("name", d.name if d else "")
        remote_path = data.get("remote_path", d.remote_path if d else "")
        local_path = data.get("local_path", d.local_path if d else "")
        enabled = data.get("enabled", d.enabled if d else True)
        auto_queue = data.get("auto_queue", d.auto_queue if d else True)
        arr_target_ids_raw = data.get("arr_target_ids", list(d.arr_target_ids) if d else [])
        if not isinstance(name, str) or not isinstance(remote_path, str) or not isinstance(local_path, str):
            return HTTPResponse(body="name, remote_path, and local_path must be strings", status=400)
        if not isinstance(enabled, bool) or not isinstance(auto_queue, bool):
            return HTTPResponse(body="enabled and auto_queue must be booleans", status=400)
        if not isinstance(arr_target_ids_raw, list):
            return HTTPResponse(body="arr_target_ids must be a list of strings", status=400)
        arr_target_ids: list[str] = []
        for t in cast(list[Any], arr_target_ids_raw):
            if not isinstance(t, str):
                return HTTPResponse(body="arr_target_ids must be a list of strings", status=400)
            arr_target_ids.append(t)
        name = name.strip()
        remote_path = remote_path.strip()
        local_path = local_path.strip()
        if not name:
            return HTTPResponse(body="name must not be empty", status=400)
        if not remote_path:
            return HTTPResponse(body="remote_path must not be empty", status=400)
        if not local_path:
            return HTTPResponse(body="local_path must not be empty", status=400)
        return name, remote_path, local_path, enabled, auto_queue, arr_target_ids

    def __handle_create(self):
        try:
            raw_data: Any = json.loads(request.body.read().decode("utf-8"))  # type: ignore[attr-defined]
        except (json.JSONDecodeError, UnicodeDecodeError):
            return HTTPResponse(body="Invalid JSON", status=400)
        if not isinstance(raw_data, dict):
            return HTTPResponse(body="Expected JSON object", status=400)
        data = cast(dict[str, Any], raw_data)

        result = self.__validate_pair_params(data)
        if isinstance(result, HTTPResponse):
            return result
        name, remote_path, local_path, enabled, auto_queue, arr_target_ids = result

        pair = PathPair(
            name=name,
            remote_path=remote_path,
            local_path=local_path,
            enabled=enabled,
            auto_queue=auto_queue,
            arr_target_ids=arr_target_ids,
        )
        try:
            self.__config.add_pair(pair)
        except ValueError as e:
            if "name" in str(e) and "already exists" in str(e):
                return HTTPResponse(body=str(e), status=409)
            raise
        return HTTPResponse(body=json.dumps(pair.to_dict()), status=201, headers={"Content-Type": "application/json"})

    def __handle_update(self, pair_id: str):
        existing = self.__config.get_pair(pair_id)
        if existing is None:
            return HTTPResponse(body="Path pair not found", status=404)

        try:
            raw_data: Any = json.loads(request.body.read().decode("utf-8"))  # type: ignore[attr-defined]
        except (json.JSONDecodeError, UnicodeDecodeError):
            return HTTPResponse(body="Invalid JSON", status=400)
        if not isinstance(raw_data, dict):
            return HTTPResponse(body="Expected JSON object", status=400)
        data = cast(dict[str, Any], raw_data)

        result = self.__validate_pair_params(data, defaults=existing)
        if isinstance(result, HTTPResponse):
            return result
        name, remote_path, local_path, enabled, auto_queue, arr_target_ids = result

        updated = PathPair(
            pair_id=pair_id,
            name=name,
            remote_path=remote_path,
            local_path=local_path,
            enabled=enabled,
            auto_queue=auto_queue,
            arr_target_ids=arr_target_ids,
        )
        try:
            self.__config.update_pair(updated)
        except ValueError as e:
            if "name" in str(e) and "already exists" in str(e):
                return HTTPResponse(body=str(e), status=409)
            return HTTPResponse(body="Path pair not found", status=404)
        return HTTPResponse(body=json.dumps(updated.to_dict()), headers={"Content-Type": "application/json"})

    def __handle_delete(self, pair_id: str):
        try:
            self.__config.remove_pair(pair_id)
        except ValueError:
            return HTTPResponse(body="Path pair not found", status=404)
        return HTTPResponse(status=204)
