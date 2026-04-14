import json
import urllib.request

from bottle import HTTPResponse

from common import Config
from common.types import overrides

from ..web_app import IHandler, WebApp


class IntegrationsHandler(IHandler):
    """Endpoints for testing Sonarr/Radarr connectivity."""

    def __init__(self, config: Config):
        self.__config = config

    @overrides(IHandler)
    def add_routes(self, web_app: WebApp):
        web_app.add_handler("/server/integrations/test/sonarr", self.__handle_test_sonarr)
        web_app.add_handler("/server/integrations/test/radarr", self.__handle_test_radarr)

    def __handle_test_sonarr(self):
        cfg = self.__config.integrations
        return self.__test_arr_connection("Sonarr", cfg.sonarr_url, cfg.sonarr_api_key)

    def __handle_test_radarr(self):
        cfg = self.__config.integrations
        return self.__test_arr_connection("Radarr", cfg.radarr_url, cfg.radarr_api_key)

    @staticmethod
    def __test_arr_connection(service: str, url: str, api_key: str) -> HTTPResponse:
        if not url:
            return HTTPResponse(body=json.dumps({"error": f"{service} URL is not configured"}), status=400)
        if not api_key:
            return HTTPResponse(body=json.dumps({"error": f"{service} API key is not configured"}), status=400)
        if not url.startswith(("http://", "https://")):
            return HTTPResponse(
                body=json.dumps({"error": f"{service} URL must start with http:// or https://"}), status=400
            )

        endpoint = url.rstrip("/") + "/api/v3/system/status"
        try:
            req = urllib.request.Request(
                endpoint,
                headers={"X-Api-Key": api_key},
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                version = data.get("version", "unknown")
            return HTTPResponse(
                body=json.dumps({"success": True, "version": version}),
                status=200,
            )
        except Exception as e:
            return HTTPResponse(
                body=json.dumps({"error": f"Connection failed: {str(e)}"}),
                status=502,
            )
