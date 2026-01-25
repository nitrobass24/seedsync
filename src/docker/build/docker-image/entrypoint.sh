#!/bin/bash
set -e

# SeedSync Docker Entrypoint
# Handles dynamic user creation and permission management

# Get user/group IDs from environment (with defaults)
USER_ID=${PUID:-1000}
GROUP_ID=${PGID:-1000}
USERNAME="seedsync"

echo "Starting SeedSync with UID=$USER_ID, GID=$GROUP_ID"

# Create group if it doesn't exist
if ! getent group "$USERNAME" >/dev/null 2>&1; then
    groupadd -g "$GROUP_ID" "$USERNAME"
elif [ "$(getent group "$USERNAME" | cut -d: -f3)" != "$GROUP_ID" ]; then
    # Group exists but with wrong GID - modify it
    groupmod -g "$GROUP_ID" "$USERNAME"
fi

# Create user if it doesn't exist
if ! id -u "$USERNAME" >/dev/null 2>&1; then
    useradd -u "$USER_ID" -g "$GROUP_ID" -d /home/$USERNAME -m -s /bin/bash "$USERNAME"
elif [ "$(id -u "$USERNAME")" != "$USER_ID" ]; then
    # User exists but with wrong UID - modify it
    usermod -u "$USER_ID" "$USERNAME"
fi

# Ensure home directory exists
mkdir -p /home/$USERNAME
chown "$USER_ID:$GROUP_ID" /home/$USERNAME

# Create required directories if they don't exist
mkdir -p /config /downloads

# Set ownership of config directory (required for app to write settings)
# Only change ownership if directory is empty or owned by root
if [ -z "$(ls -A /config 2>/dev/null)" ] || [ "$(stat -c '%u' /config)" = "0" ]; then
    chown -R "$USER_ID:$GROUP_ID" /config
fi

# For downloads, just ensure the user can write to it
# Don't recursively chown as it could be a large directory
chown "$USER_ID:$GROUP_ID" /downloads 2>/dev/null || true

# Create SSH directory for the user (needed for SSH key management)
mkdir -p /home/$USERNAME/.ssh
chown -R "$USER_ID:$GROUP_ID" /home/$USERNAME/.ssh
chmod 700 /home/$USERNAME/.ssh

# Set HOME environment variable
export HOME=/home/$USERNAME

# Execute the command as the seedsync user
exec gosu "$USERNAME" "$@"
