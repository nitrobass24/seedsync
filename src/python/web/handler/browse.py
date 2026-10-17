# Copyright 2017, Inderpreet Singh, All rights reserved.

import json
import os
import posixpath
from typing import cast, override

from bottle import HTTPResponse, request

from common import Config, escape_remote_path_double
from ssh import SshcpError, lftp_ssh

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
        path = os.path.abspath(os.path.expanduser(self.__query_path() or "/"))
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
        path = self.__query_path() or lftp.remote_path or "/"
        ssh = lftp_ssh.build_sshcp(lftp)
        try:
            # -L lists symlinked directories and skips dangling links (busybox ls -L
            # exits 1 on a dangling link, failing the whole listing). find has no
            # "--", so a leading "-" gets "./" to keep it from parsing as an option.
            start = f"./{path}" if path.startswith("-") else path
            raw = ssh.shell(f"find -L {escape_remote_path_double(start)} -mindepth 1 -maxdepth 1 -type d")
        except SshcpError as e:
            # 400 for a bad path vs 502 for a failed connection: the picker only
            # walks up to a parent directory on the former.
            message = str(e)
            is_path_error = "No such file or directory" in message or "Not a directory" in message
            return self.__error(message, 400 if is_path_error else 502)
        # Not splitlines(): find separates entries with \n only, and names may
        # contain other line-break characters (\x0b, U+2028, ...).
        lines = raw.decode(errors="replace").split("\n")
        directories = sorted((posixpath.basename(line) for line in lines if line), key=str.lower)
        normalized = path.rstrip("/") or "/"
        parent = (posixpath.dirname(normalized) or None) if normalized != "/" else None
        return self.__ok(normalized, parent, directories)

    @staticmethod
    def __query_path() -> str | None:
        # getunicode re-decodes Bottle's latin-1 WSGI string as UTF-8; bottle is untyped.
        return cast(str | None, request.query.getunicode("path"))  # pyright: ignore[reportAttributeAccessIssue, reportUnknownMemberType]

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
