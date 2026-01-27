# Copyright 2017, Inderpreet Singh, All rights reserved.

import threading

from bottle import HTTPResponse

from common import Context, overrides
from ..web_app import IHandler, WebApp


class ServerHandler(IHandler):
    def __init__(self, context: Context):
        self.logger = context.logger.getChild("ServerActionHandler")
        self._restart_event = threading.Event()

    @overrides(IHandler)
    def add_routes(self, web_app: WebApp):
        web_app.add_handler("/server/command/restart", self._handle_action_restart)

    def is_restart_requested(self):
        """
        Returns true is a restart is requested
        :return:
        """
        return self._restart_event.is_set()

    def _handle_action_restart(self):
        """
        Request a server restart
        :return:
        """
        self.logger.info("Received a restart action")
        self._restart_event.set()
        return HTTPResponse(body="Requested restart")
