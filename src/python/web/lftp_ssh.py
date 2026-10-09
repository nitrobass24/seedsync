# Copyright 2017, Inderpreet Singh, All rights reserved.

from common import Config
from ssh import Sshcp


def missing_connection_fields(lftp: "Config.Lftp") -> list[str]:
    """Return the names of any required lftp connection fields that are unset.
    remote_password is only required for password auth: with an empty
    password and use_ssh_key False, build_sshcp() would still pass a
    non-None password to Sshcp, which disables key auth and attempts an
    empty-password login instead of surfacing this as a config problem.
    """
    required = [
        ("remote_address", lftp.remote_address),
        ("remote_username", lftp.remote_username),
        ("remote_port", lftp.remote_port),
    ]
    if not lftp.use_ssh_key:
        required.append(("remote_password", lftp.remote_password))
    return [name for name, value in required if not value]


def build_sshcp(lftp: "Config.Lftp") -> Sshcp:
    """Build an Sshcp from the current lftp config, omitting the password when
    SSH key authentication is enabled.
    """
    password = None if lftp.use_ssh_key else lftp.remote_password
    return Sshcp(
        host=lftp.remote_address,  # type: ignore[arg-type]
        port=lftp.remote_port,  # type: ignore[arg-type]
        user=lftp.remote_username,
        password=password,
    )


def is_credential_error(message: str) -> bool:
    """Whether an SshcpError message indicates bad credentials (wrong
    password, or a rejected key), as opposed to a network/host-level failure
    (bad hostname, connection refused, timeout). Repeatedly retrying a
    connection test after a credential failure -- as opposed to a transient
    network blip -- risks tripping fail2ban-style bans on the remote server,
    so callers use this to stop offering retries until the credentials
    actually change.
    """
    return "Incorrect password" in message or "Permission denied" in message
