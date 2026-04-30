# Copyright 2017, Inderpreet Singh, All rights reserved.

import json
import logging
import urllib.request
from typing import Any, cast

from bottle import HTTPResponse, request

from common import ArrInstance, IntegrationsConfig, PathPairsConfig
from common.config import Config
from common.types import overrides

from ..web_app import IHandler, WebApp


class IntegrationsHandler(IHandler):
    """REST endpoints for managing *arr (Sonarr/Radarr) instances."""

    def __init__(self, integrations_config: IntegrationsConfig, path_pairs_config: PathPairsConfig):
        self.__config = integrations_config
        self.__path_pairs_config = path_pairs_config
        self._logger = logging.getLogger(self.__class__.__name__)

    @overrides(IHandler)
    def add_routes(self, web_app: WebApp):
        web_app.add_handler("/server/integrations", self.__handle_list)
        web_app.add_post_handler("/server/integrations", self.__handle_create)
        web_app.add_put_handler("/server/integrations/<instance_id>", self.__handle_update)
        web_app.add_delete_handler("/server/integrations/<instance_id>", self.__handle_delete)
        web_app.add_post_handler("/server/integrations/<instance_id>/test", self.__handle_test)

    def __handle_list(self):
        instances = [self._redact(i.to_dict()) for i in self.__config.instances]
        return HTTPResponse(body=json.dumps(instances), headers={"Content-Type": "application/json"})

    def __handle_create(self):
        data = self.__read_json_object()
        if isinstance(data, HTTPResponse):
            return data

        result = self.__validate_instance_params(data)
        if isinstance(result, HTTPResponse):
            return result
        name, kind, url, api_key, enabled = result

        instance = ArrInstance(name=name, kind=kind, url=url, api_key=api_key, enabled=enabled)
        try:
            self.__config.add_instance(instance)
        except ValueError as e:
            return HTTPResponse(body=str(e), status=409)
        return HTTPResponse(
            body=json.dumps(self._redact(instance.to_dict())),
            status=201,
            headers={"Content-Type": "application/json"},
        )

    def __handle_update(self, instance_id: str):
        existing = self.__config.get_instance(instance_id)
        if existing is None:
            return HTTPResponse(body="Integration not found", status=404)

        data = self.__read_json_object()
        if isinstance(data, HTTPResponse):
            return data

        result = self.__validate_instance_params(data, defaults=existing)
        if isinstance(result, HTTPResponse):
            return result
        name, kind, url, api_key, enabled = result

        # If the client sent the redacted sentinel, keep the existing key.
        if api_key == Config.REDACTED_SENTINEL:
            api_key = existing.api_key

        updated = ArrInstance(
            instance_id=instance_id,
            name=name,
            kind=kind,
            url=url,
            api_key=api_key,
            enabled=enabled,
        )
        try:
            self.__config.update_instance(updated)
        except ValueError as e:
            msg = str(e)
            if "already exists" in msg:
                return HTTPResponse(body=msg, status=409)
            if "not found" in msg:
                return HTTPResponse(body="Integration not found", status=404)
            return HTTPResponse(body=msg, status=400)
        return HTTPResponse(
            body=json.dumps(self._redact(updated.to_dict())),
            headers={"Content-Type": "application/json"},
        )

    def __handle_delete(self, instance_id: str):
        try:
            self.__config.remove_instance(instance_id)
        except ValueError:
            return HTTPResponse(body="Integration not found", status=404)
        # Detach from any path pair that referenced it so we don't leave dangling pointers.
        self.__path_pairs_config.detach_arr_target(instance_id)
        return HTTPResponse(status=204)

    def __handle_test(self, instance_id: str):
        instance = self.__config.get_instance(instance_id)
        if instance is None:
            return HTTPResponse(body=json.dumps({"error": "Integration not found"}), status=404)
        return self.__test_arr_connection(instance)

    @staticmethod
    def _redact(d: dict[str, Any]) -> dict[str, Any]:
        out = dict(d)
        if out.get("api_key"):
            out["api_key"] = Config.REDACTED_SENTINEL
        return out

    @staticmethod
    def __read_json_object() -> "HTTPResponse | dict[str, Any]":
        try:
            raw: Any = json.loads(request.body.read().decode("utf-8"))  # type: ignore[attr-defined]
        except (json.JSONDecodeError, UnicodeDecodeError):
            return HTTPResponse(body="Invalid JSON", status=400)
        if not isinstance(raw, dict):
            return HTTPResponse(body="Expected JSON object", status=400)
        return cast(dict[str, Any], raw)

    @staticmethod
    def __validate_instance_params(
        data: dict[str, Any],
        defaults: ArrInstance | None = None,
    ) -> "HTTPResponse | tuple[str, str, str, str, bool]":
        d = defaults
        name = data.get("name", d.name if d else "")
        kind = data.get("kind", d.kind if d else "")
        url = data.get("url", d.url if d else "")
        api_key = data.get("api_key", d.api_key if d else "")
        enabled = data.get("enabled", d.enabled if d else True)
        if not isinstance(name, str) or not isinstance(kind, str) or not isinstance(url, str):
            return HTTPResponse(body="name, kind, and url must be strings", status=400)
        if not isinstance(api_key, str):
            return HTTPResponse(body="api_key must be a string", status=400)
        if not isinstance(enabled, bool):
            return HTTPResponse(body="enabled must be a boolean", status=400)
        name = name.strip()
        url = url.strip()
        if not name:
            return HTTPResponse(body="name must not be empty", status=400)
        if kind not in ArrInstance.ALLOWED_KINDS:
            return HTTPResponse(
                body="kind must be one of: " + ", ".join(ArrInstance.ALLOWED_KINDS),
                status=400,
            )
        if url and not url.startswith(("http://", "https://")):
            return HTTPResponse(body="url must start with http:// or https://", status=400)
        return name, kind, url, api_key, enabled

    def __test_arr_connection(self, instance: ArrInstance) -> HTTPResponse:
        service = "Sonarr" if instance.kind == ArrInstance.KIND_SONARR else "Radarr"
        if not instance.url:
            return HTTPResponse(body=json.dumps({"error": f"{service} URL is not configured"}), status=400)
        if not instance.api_key:
            return HTTPResponse(body=json.dumps({"error": f"{service} API key is not configured"}), status=400)
        if not instance.url.startswith(("http://", "https://")):
            return HTTPResponse(
                body=json.dumps({"error": f"{service} URL must start with http:// or https://"}), status=400
            )

        endpoint = instance.url.rstrip("/") + "/api/v3/system/status"
        try:
            req = urllib.request.Request(
                endpoint,
                headers={"X-Api-Key": instance.api_key},
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                version = data.get("version", "unknown")
            return HTTPResponse(
                body=json.dumps({"success": True, "version": version}),
                status=200,
            )
        except Exception:
            self._logger.exception("%s connection test failed", service)
            return HTTPResponse(
                body=json.dumps({"error": f"{service} connection failed. Check server logs for details."}),
                status=502,
            )
