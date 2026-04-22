# Copyright 2017, Inderpreet Singh, All rights reserved.

import os
from threading import Event
from urllib.parse import unquote

from bottle import HTTPResponse, request

from common import overrides
from controller import Controller

from ..web_app import IHandler, WebApp


def _validate_filename(file_name: str) -> bool:
    """
    Validate that a filename is safe to use as a command argument.
    Rejects path traversal attempts, absolute paths, and null bytes.
    """
    if not file_name:
        return False
    # Reject embedded null bytes (path truncation attack)
    if "\x00" in file_name:
        return False
    # Reject control characters (0x00-0x1F, 0x7F)
    if any(ord(c) < 0x20 or ord(c) == 0x7F for c in file_name):
        return False
    # Reject absolute paths
    if os.path.isabs(file_name):
        return False
    # Reject path traversal components
    parts = file_name.replace("\\", "/").split("/")
    return all(part != ".." for part in parts)


def _validate_pair_id(pair_id: str | None) -> str | None:
    """Return validated pair_id or None. Returns empty string to signal rejection."""
    if pair_id is not None and pair_id.strip() == "":
        return ""
    return pair_id


def _decode_and_validate(file_name: str) -> str | HTTPResponse:
    """
    Decode a double-encoded filename and validate it.
    Returns the decoded filename, or an HTTPResponse(400) on failure.
    """
    file_name = unquote(file_name)
    if not _validate_filename(file_name):
        return HTTPResponse(body="Invalid file name", status=400)
    return file_name


class WebResponseActionCallback(Controller.Command.ICallback):
    """
    Controller action callback used by model streams to wait for action
    status.
    Clients should call wait() method to wait for the status,
    then query the status from 'success' and 'error'
    """

    def __init__(self):
        self.__event = Event()
        self.success = None
        self.error = None

    @overrides(Controller.Command.ICallback)
    def on_failure(self, error: str):
        self.success = False
        self.error = error
        self.__event.set()

    @overrides(Controller.Command.ICallback)
    def on_success(self):
        self.success = True
        self.__event.set()

    def wait(self):
        self.__event.wait()


class ControllerHandler(IHandler):
    def __init__(self, controller: Controller):
        self.__controller = controller

    @overrides(IHandler)
    def add_routes(self, web_app: WebApp):
        web_app.add_handler("/server/command/queue/<file_name>", self.__handle_action_queue)
        web_app.add_handler("/server/command/stop/<file_name>", self.__handle_action_stop)
        web_app.add_handler("/server/command/extract/<file_name>", self.__handle_action_extract)
        web_app.add_handler("/server/command/delete_local/<file_name>", self.__handle_action_delete_local)
        web_app.add_handler("/server/command/delete_remote/<file_name>", self.__handle_action_delete_remote)
        web_app.add_handler("/server/command/validate/<file_name>", self.__handle_action_validate)

    def __dispatch_command(self, file_name: str, action: Controller.Command.Action, success_msg: str):
        """Common handler: decode filename, validate pair_id, dispatch command."""
        decoded = _decode_and_validate(file_name)
        if isinstance(decoded, HTTPResponse):
            return decoded

        pair_id = _validate_pair_id(request.params.get("pair_id"))  # type: ignore[attr-defined]
        if pair_id == "":
            return HTTPResponse(body="pair_id must not be blank", status=400)
        command = Controller.Command(action, decoded, pair_id=pair_id)
        callback = WebResponseActionCallback()
        command.add_callback(callback)
        self.__controller.queue_command(command)
        callback.wait()
        if callback.success:
            return HTTPResponse(body=success_msg.format(decoded))
        return HTTPResponse(body=callback.error or "Unknown error", status=400)

    def __handle_action_queue(self, file_name: str):
        return self.__dispatch_command(file_name, Controller.Command.Action.QUEUE, "Queued file '{}'")

    def __handle_action_stop(self, file_name: str):
        return self.__dispatch_command(file_name, Controller.Command.Action.STOP, "Stopped file '{}'")

    def __handle_action_extract(self, file_name: str):
        return self.__dispatch_command(
            file_name, Controller.Command.Action.EXTRACT, "Requested extraction for file '{}'"
        )

    def __handle_action_delete_local(self, file_name: str):
        return self.__dispatch_command(
            file_name, Controller.Command.Action.DELETE_LOCAL, "Requested local delete for file '{}'"
        )

    def __handle_action_delete_remote(self, file_name: str):
        return self.__dispatch_command(
            file_name, Controller.Command.Action.DELETE_REMOTE, "Requested remote delete for file '{}'"
        )

    def __handle_action_validate(self, file_name: str):
        return self.__dispatch_command(
            file_name, Controller.Command.Action.VALIDATE, "Requested validation for file '{}'"
        )
