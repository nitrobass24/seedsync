#!/bin/bash
set -e

# SeedSync Docker Entrypoint
# Handles dynamic user creation and permission management
#
# Supports reusing existing host UID/GID mappings, e.g.:
#   - PUID=1000, PGID=1000 (typical single-user setup)
#   - PUID=1026, PGID=100  (Synology with "users" group)
#   - Custom user:group like "torrentapp:media"

# Get user/group IDs from environment (with defaults)
USER_ID=${PUID:-1000}
GROUP_ID=${PGID:-1000}

echo "Starting SeedSync with UID=$USER_ID, GID=$GROUP_ID"

# Resolve group: check if GID already exists
EXISTING_GROUP=$(getent group "$GROUP_ID" 2>/dev/null | cut -d: -f1 || true)
if [ -n "$EXISTING_GROUP" ]; then
    GROUPNAME="$EXISTING_GROUP"
    echo "Using existing group: $GROUPNAME (GID=$GROUP_ID)"
else
    GROUPNAME="seedsync"
    echo "Creating group: $GROUPNAME (GID=$GROUP_ID)"
    groupadd -g "$GROUP_ID" "$GROUPNAME"
fi

# Resolve user: check if UID already exists
EXISTING_USER=$(getent passwd "$USER_ID" 2>/dev/null | cut -d: -f1 || true)
if [ -n "$EXISTING_USER" ]; then
    USERNAME="$EXISTING_USER"
    echo "Using existing user: $USERNAME (UID=$USER_ID)"

    # Ensure user is in the target group (may differ from their primary group)
    if ! id -nG "$USERNAME" | grep -qw "$GROUPNAME"; then
        usermod -aG "$GROUPNAME" "$USERNAME" 2>/dev/null || true
    fi
else
    USERNAME="seedsync"
    echo "Creating user: $USERNAME (UID=$USER_ID, GID=$GROUP_ID)"
    useradd -u "$USER_ID" -g "$GROUP_ID" -d /home/$USERNAME -m -s /bin/bash "$USERNAME"
fi

# Get the user's home directory (may not be /home/$USERNAME for existing users)
USER_HOME=$(getent passwd "$USERNAME" | cut -d: -f6)
if [ -z "$USER_HOME" ] || [ ! -d "$USER_HOME" ]; then
    USER_HOME="/home/$USERNAME"
    mkdir -p "$USER_HOME"
fi
chown "$USER_ID:$GROUP_ID" "$USER_HOME"

# Create required directories if they don't exist
mkdir -p /config /downloads /staging

# Set ownership of config directory (required for app to write settings)
# Only change ownership if directory is empty or owned by root
if [ -z "$(ls -A /config 2>/dev/null)" ] || [ "$(stat -c '%u' /config)" = "0" ]; then
    chown -R "$USER_ID:$GROUP_ID" /config
fi

# For downloads and staging, just ensure the user can write to them
# Don't recursively chown as they could be large directories
chown "$USER_ID:$GROUP_ID" /downloads || true
chown "$USER_ID:$GROUP_ID" /staging || true

# Verify writability as the target user — fail fast with a clear message
# rather than crashing deep in the application on the first write attempt.
# /downloads is always required. /staging is only checked when externally
# mounted (i.e. the user has explicitly mapped it), since staging is optional.
_check_dirs="/downloads"
if mountpoint -q /staging 2>/dev/null; then
    _check_dirs="$_check_dirs /staging"
fi

for _dir in $_check_dirs; do
    _testfile="$_dir/.seedsync_write_test"
    if ! setpriv --reuid="$USERNAME" --regid="$GROUPNAME" --init-groups -- \
         sh -c "touch '$_testfile' && rm '$_testfile'" 2>/dev/null; then
        echo "ERROR: $_dir is not writable by UID=$USER_ID GID=$GROUP_ID. Check volume permissions." >&2
        exit 1
    fi
done

# Create SSH directory for the user (needed for SSH key management)
mkdir -p "$USER_HOME/.ssh"
chown -R "$USER_ID:$GROUP_ID" "$USER_HOME/.ssh"
chmod 700 "$USER_HOME/.ssh"

# Set HOME environment variable
export HOME="$USER_HOME"

echo "Running as: $USERNAME:$GROUPNAME (UID=$USER_ID, GID=$GROUP_ID)"

# Apply umask if set (controls default file/directory permissions)
if [ -n "$UMASK" ]; then
    umask "$UMASK"
    echo "Setting umask: $UMASK"
fi

# Execute the command as the resolved user
exec setpriv --reuid="$USERNAME" --regid="$GROUPNAME" --init-groups -- "$@"
