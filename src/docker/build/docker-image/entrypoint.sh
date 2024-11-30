#!/bin/bash

# Use the PUID and PGID from the environment variables
USER_ID=${PUID:-1000}
GROUP_ID=${PGID:-1000}

# Create group if it doesn't exist
if ! getent group seedsync >/dev/null; then
    groupadd -g "$GROUP_ID" seedsync
fi

# Create user if it doesn't exist
if ! id -u seedsync >/dev/null 2>&1; then
    useradd -u "$USER_ID" -g "$GROUP_ID" -m seedsync
fi

# Set ownership of necessary directories
chown -R seedsync:seedsync /config /downloads

# Execute the command as the specified user
exec gosu seedsync "$@"
