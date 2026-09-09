# Copyright 2017, Inderpreet Singh, All rights reserved.

import json

from common import Status

from .serialize import Serialize


class SerializeStatusJson:
    @staticmethod
    def status(status: Status) -> str:
        json_dict = {
            "server": {
                "up": status.server.up,
                "error_msg": status.server.error_msg,
            },
            "controller": {
                "latest_local_scan_time": (
                    str(status.controller.latest_local_scan_time.timestamp())
                    if status.controller.latest_local_scan_time
                    else None
                ),
                "latest_remote_scan_time": (
                    str(status.controller.latest_remote_scan_time.timestamp())
                    if status.controller.latest_remote_scan_time
                    else None
                ),
                "latest_remote_scan_failed": status.controller.latest_remote_scan_failed,
                "latest_remote_scan_error": status.controller.latest_remote_scan_error,
                "no_enabled_pairs": status.controller.no_enabled_pairs,
            },
        }
        return json.dumps(json_dict)


class SerializeStatus(Serialize):
    """
    This class defines the serialization interface between python backend
    and the EventSource client frontend for the status stream.
    """

    def status(self, status: Status) -> str:
        status_json = SerializeStatusJson.status(status)
        return self._sse_pack(event="status", data=status_json)
