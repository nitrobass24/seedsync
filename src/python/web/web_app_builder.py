# Copyright 2017, Inderpreet Singh, All rights reserved.

import os

from common import Constants, Context
from controller import AutoQueuePersist, Controller

from .handler.auto_queue import AutoQueueHandler
from .handler.config import ConfigHandler
from .handler.controller import ControllerHandler
from .handler.integrations import IntegrationsHandler
from .handler.logs import LogsHandler
from .handler.notifications import NotificationsHandler
from .handler.path_pairs import PathPairsHandler
from .handler.server import ServerHandler
from .handler.status import StatusHandler
from .handler.stream_log import LogStreamHandler
from .handler.stream_model import ModelStreamHandler
from .handler.stream_status import StatusStreamHandler
from .security import install_security_middleware
from .web_app import WebApp


class WebAppBuilder:
    """
    Helper class to build WebApp with all the extensions
    """

    def __init__(self, context: Context, controller: Controller, auto_queue_persist: AutoQueuePersist):
        self.__context = context
        self.__controller = controller

        assert context.config_path is not None
        assert context.path_pairs_path is not None
        assert context.integrations_path is not None
        assert context.auto_queue_persist_path is not None

        self.controller_handler = ControllerHandler(controller)
        self.server_handler = ServerHandler(context)
        self.config_handler = ConfigHandler(
            context.config, context.config_path, on_lftp_config_change=controller.request_lftp_reconfigure
        )
        self.auto_queue_handler = AutoQueueHandler(auto_queue_persist, context.auto_queue_persist_path)
        self.status_handler = StatusHandler(context.status)
        self.logs_handler = LogsHandler(logdir=context.args.logdir, service_name=Constants.SERVICE_NAME)
        self.path_pairs_handler = PathPairsHandler(
            context.path_pairs_config, context.integrations_config, context.path_pairs_path
        )
        self.integrations_handler = IntegrationsHandler(
            context.integrations_config, context.path_pairs_config, context.integrations_path, context.path_pairs_path
        )
        self.notifications_handler = NotificationsHandler(context.config)

    def build(self) -> WebApp:
        web_app = WebApp(context=self.__context, controller=self.__controller)

        # Install security middleware (headers, CSRF, rate limiting, API key auth)
        install_security_middleware(
            web_app,
            get_api_key=lambda: self.__context.config.web.api_key,
            disable_rate_limiting=os.environ.get("SEEDSYNC_DISABLE_RATE_LIMIT", "").lower() in ("1", "true", "yes"),
        )

        StatusStreamHandler.register(web_app=web_app, status=self.__context.status)

        LogStreamHandler.register(web_app=web_app, logger=self.__context.logger)

        ModelStreamHandler.register(web_app=web_app, controller=self.__controller)

        self.controller_handler.add_routes(web_app)
        self.server_handler.add_routes(web_app)
        self.config_handler.add_routes(web_app)
        self.auto_queue_handler.add_routes(web_app)
        self.status_handler.add_routes(web_app)
        self.logs_handler.add_routes(web_app)
        self.path_pairs_handler.add_routes(web_app)
        self.integrations_handler.add_routes(web_app)
        self.notifications_handler.add_routes(web_app)

        web_app.add_default_routes()

        return web_app
