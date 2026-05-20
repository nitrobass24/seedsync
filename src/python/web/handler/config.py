# Copyright 2017, Inderpreet Singh, All rights reserved.

import logging
import threading
from collections.abc import Callable
from urllib.parse import unquote

from bottle import HTTPResponse

from common import Config, ConfigError, overrides

from ..serialize import SerializeConfig
from ..web_app import IHandler, WebApp

# (section, key) pairs for settings that can be hot-reloaded into the
# running LFTP process without a full restart.
_LFTP_TUNING_KEYS: frozenset[tuple[str, str]] = frozenset(
    {
        ("lftp", "num_max_parallel_downloads"),
        ("lftp", "num_max_parallel_files_per_download"),
        ("lftp", "num_max_connections_per_root_file"),
        ("lftp", "num_max_connections_per_dir_file"),
        ("lftp", "num_max_total_connections"),
        ("lftp", "use_temp_file"),
        ("lftp", "net_limit_rate"),
        ("lftp", "net_socket_buffer"),
        ("lftp", "pget_min_chunk_size"),
        ("lftp", "mirror_parallel_directories"),
        ("lftp", "net_timeout"),
        ("lftp", "net_max_retries"),
        ("lftp", "net_reconnect_interval_base"),
        ("lftp", "net_reconnect_interval_multiplier"),
        ("general", "verbose"),
        ("validate", "xfer_verify"),
        ("validate", "algorithm"),
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
        self.__logger = logging.getLogger(self.__class__.__name__)
        # Serializes the mutate → persist → rollback sequence in
        # __handle_set_config. Without it, two concurrent writers can
        # interleave (the in-memory mutation, the whole-config to_file,
        # or the post-failure rollback) and leave on-disk and in-memory
        # state diverged.
        self.__write_lock = threading.Lock()

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
        # Hold __write_lock across the mutate → persist → rollback sequence so
        # writers can't interleave. With the lock, the rollback is unconditional:
        # no other writer can have changed the value between set_property and
        # the OSError handler.
        with self.__write_lock:
            old_value = getattr(inner_config, key)
            try:
                inner_config.set_property(key, value)
            except ConfigError as e:
                return HTTPResponse(body=str(e), status=400)
            try:
                self.__config.to_file(self.__config_path)
            except OSError:
                inner_config.set_property(key, old_value)
                self.__logger.exception("Failed to persist config %s.%s", section, key)
                return HTTPResponse(body=f"Failed to persist config {section}.{key}", status=500)
        if (section, key) in _LFTP_TUNING_KEYS and self.__on_lftp_config_change:
            self.__on_lftp_config_change()
        if Config.is_sensitive(section, key):
            return HTTPResponse(body=f"{section}.{key} updated")
        return HTTPResponse(body=f"{section}.{key} set to {value}")
