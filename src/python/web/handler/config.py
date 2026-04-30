# Copyright 2017, Inderpreet Singh, All rights reserved.

from collections.abc import Callable
from urllib.parse import unquote

from bottle import HTTPResponse

from common import Config, ConfigError, overrides

from ..serialize import SerializeConfig
from ..web_app import IHandler, WebApp

# LFTP tuning keys that can be hot-reloaded without restart
_LFTP_TUNING_KEYS = frozenset(
    {
        "num_max_parallel_downloads",
        "num_max_parallel_files_per_download",
        "num_max_connections_per_root_file",
        "num_max_connections_per_dir_file",
        "num_max_total_connections",
        "use_temp_file",
        "net_limit_rate",
        "net_socket_buffer",
        "pget_min_chunk_size",
        "mirror_parallel_directories",
        "net_timeout",
        "net_max_retries",
        "net_reconnect_interval_base",
        "net_reconnect_interval_multiplier",
    }
)


class ConfigHandler(IHandler):
    def __init__(
        self,
        config: Config,
        config_path: str,
        on_lftp_config_change: Callable[[], None] | None = None,
    ):
        self.__config = config
        self.__config_path = config_path
        self.__on_lftp_config_change = on_lftp_config_change

    @overrides(IHandler)
    def add_routes(self, web_app: WebApp):
        web_app.add_handler("/server/config/get", self.__handle_get_config)
        # The regex allows slashes in values
        web_app.add_handler("/server/config/set/<section>/<key>/<value:re:.+>", self.__handle_set_config)

    def __handle_get_config(self):
        out_json = SerializeConfig.config(self.__config)
        return HTTPResponse(body=out_json)

    def __handle_set_config(self, section: str, key: str, value: str):
        # value is double encoded
        value = unquote(value)
        # Handle empty value sentinel from frontend
        if value == "__empty__":
            value = ""

        if not self.__config.has_section(section):
            return HTTPResponse(body=f"There is no section '{section}' in config", status=400)
        inner_config = getattr(self.__config, section)
        if not inner_config.has_property(key):
            return HTTPResponse(body=f"Section '{section}' in config has no option '{key}'", status=400)
        # Reject the redacted sentinel to prevent accidentally overwriting
        # real credentials with "********"
        if Config.is_sensitive(section, key) and value == Config.REDACTED_SENTINEL:
            return HTTPResponse(body="Cannot set sensitive field to redacted value", status=400)
        try:
            inner_config.set_property(key, value)
            self.__config.to_file(self.__config_path)
            if section == "lftp" and key in _LFTP_TUNING_KEYS and self.__on_lftp_config_change:
                self.__on_lftp_config_change()
            if Config.is_sensitive(section, key):
                return HTTPResponse(body=f"{section}.{key} updated")
            return HTTPResponse(body=f"{section}.{key} set to {value}")
        except ConfigError as e:
            return HTTPResponse(body=str(e), status=400)
