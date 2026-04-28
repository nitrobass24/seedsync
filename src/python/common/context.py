# Copyright 2017, Inderpreet Singh, All rights reserved.

import collections
import copy
import logging

# my libs
from .config import Config
from .integrations_config import IntegrationsConfig
from .path_pairs_config import PathPairsConfig
from .status import Status


class Args:
    """
    Container for args
    These are settings that aren't part of config but still needed by
    sub-components
    """

    def __init__(self):
        self.local_path_to_scanfs: str | None = None
        self.html_path: str | None = None
        self.debug: bool | None = None
        self.exit: bool | None = None
        self.logdir: str | None = None

    def as_dict(self) -> dict[str, str]:
        dct: collections.OrderedDict[str, str] = collections.OrderedDict()
        dct["local_path_to_scanfs"] = str(self.local_path_to_scanfs)
        dct["html_path"] = str(self.html_path)
        dct["debug"] = str(self.debug)
        dct["exit"] = str(self.exit)
        dct["logdir"] = str(self.logdir)
        return dct


class Context:
    """
    Stores contextual information for the entire application
    """

    def __init__(
        self,
        logger: logging.Logger,
        web_access_logger: logging.Logger,
        config: Config,
        args: Args,
        status: Status,
        path_pairs_config: PathPairsConfig | None = None,
        integrations_config: IntegrationsConfig | None = None,
    ):
        """
        Primary constructor to construct the top-level context
        """
        # Config
        self.logger = logger
        self.web_access_logger = web_access_logger
        self.config = config
        self.args = args
        self.status = status
        self.path_pairs_config = path_pairs_config or PathPairsConfig()
        self.integrations_config = integrations_config or IntegrationsConfig()

    def create_child_context(self, context_name: str) -> "Context":
        child_context = copy.copy(self)
        child_context.logger = self.logger.getChild(context_name)
        return child_context

    def print_to_log(self):
        # Print the config
        self.logger.debug("Config:")
        config_dict = self.config.as_dict()
        sensitive = Config.sensitive_property_names()
        for section in config_dict:
            sensitive_options = sensitive.get(section, set())
            for option in config_dict[section]:
                value = config_dict[section][option]
                if option in sensitive_options:
                    value = "********" if value else ""
                self.logger.debug(f"  {section}.{option}: {value}")

        # Print path pairs
        if self.path_pairs_config and self.path_pairs_config.pairs:
            self.logger.debug("Path Pairs:")
            for pair in self.path_pairs_config.pairs:
                status = "enabled" if pair.enabled else "disabled"
                aq = "auto_queue=on" if pair.auto_queue else "auto_queue=off"
                self.logger.debug(
                    "  [{}] {} ({}, {})".format(
                        pair.name or pair.id[:8], pair.remote_path + " -> " + pair.local_path, status, aq
                    )
                )
        else:
            self.logger.debug("Path Pairs: (none)")

        # Print integrations
        if self.integrations_config and self.integrations_config.instances:
            self.logger.debug("Integrations:")
            for inst in self.integrations_config.instances:
                self.logger.debug(
                    "  [{}] {} {} ({})".format(
                        inst.id[:8],
                        inst.kind,
                        inst.name,
                        "enabled" if inst.enabled else "disabled",
                    )
                )
        else:
            self.logger.debug("Integrations: (none)")

        self.logger.debug("Args:")
        for name, value in self.args.as_dict().items():
            self.logger.debug(f"  {name}: {value}")
