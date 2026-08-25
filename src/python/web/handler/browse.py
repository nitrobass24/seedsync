# Copyright 2017, Inderpreet Singh, All rights reserved.

import json
import os
import posixpath
import shlex
from typing import override

from bottle import HTTPResponse, request

from common import Config
from ssh import SshcpError

from .. import lftp_ssh
from ..web_app import IHandler, WebApp


class BrowseHandler(IHandler):
    """REST endpoints backing the Server/Local Directory folder pickers in
    Settings: list the subdirectories of a given path on the local machine or
    (over SSH) on the configured remote seedbox.
    """

    def __init__(self, config: Config):
        self.__config = config

    @override
    def add_routes(self, web_app: WebApp):
        web_app.add_handler("/server/browse/local", self.__handle_browse_local)
        web_app.add_handler("/server/browse/remote", self.__handle_browse_remote)

    def __handle_browse_local(self):
        path = os.path.abspath(request.query.get("path") or "/")
        if not os.path.isdir(path):
            return self.__error(f"Not a directory: {path}", 400)
        try:
            entries = os.listdir(path)
        except OSError as e:
            return self.__error(str(e), 502)
        directories = sorted(
            (name for name in entries if os.path.isdir(os.path.join(path, name))),
            key=str.lower,
        )
        parent = os.path.dirname(path.rstrip("/")) if path != "/" else None
        return self.__ok(path, parent, directories)

    def __handle_browse_remote(self):
        lftp = self.__config.lftp
        missing = lftp_ssh.missing_connection_fields(lftp)
        if missing:
            return self.__error(f"Missing required setting(s): {', '.join(missing)}", 400)
        path = request.query.get("path") or lftp.remote_path or "/"
        ssh = lftp_ssh.build_sshcp(lftp)
        try:
            raw = ssh.shell(f"ls -1p {shlex.quote(path)}")
        except SshcpError as e:
            return self.__error(str(e), 502)
        entries = raw.decode(errors="replace").splitlines()
        directories = sorted((entry[:-1] for entry in entries if entry.endswith("/")), key=str.lower)
        normalized = path.rstrip("/") or "/"
        parent = posixpath.dirname(normalized) if normalized != "/" else None
        return self.__ok(normalized, parent, directories)

    @staticmethod
    def __ok(path: str, parent: str | None, directories: list[str]) -> HTTPResponse:
        return HTTPResponse(
            body=json.dumps({"path": path, "parent": parent, "directories": directories}),
            status=200,
            headers={"Content-Type": "application/json"},
        )

    @staticmethod
    def __error(message: str, status: int) -> HTTPResponse:
        return HTTPResponse(
            body=json.dumps({"error": message}),
            status=status,
            headers={"Content-Type": "application/json"},
        )
