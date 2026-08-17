# Copyright 2017, Inderpreet Singh, All rights reserved.

from common import Config
from ssh import Sshcp


def missing_connection_fields(lftp: "Config.Lftp") -> list[str]:
    """Return the names of any required lftp connection fields that are unset."""
    required = (
        ("remote_address", lftp.remote_address),
        ("remote_username", lftp.remote_username),
        ("remote_port", lftp.remote_port),
    )
    return [name for name, value in required if not value]


def build_sshcp(lftp: "Config.Lftp") -> Sshcp:
    """Build an Sshcp from the current lftp config, omitting the password when
    SSH key authentication is enabled.
    """
    password = None if lftp.use_ssh_key else lftp.remote_password
    return Sshcp(host=lftp.remote_address, port=lftp.remote_port, user=lftp.remote_username, password=password)
