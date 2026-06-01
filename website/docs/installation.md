---
title: Installation
---

SeedSync runs in Docker. The remote server needs SSH access and Python 3.8+.

## Docker Image

| Tag | Base | Size |
|-----|------|------|
| `latest` | Alpine Linux | ~45 MB (amd64) |

Multi-arch image supporting both `linux/amd64` and `linux/arm64`.

## Requirements

### Remote server

- Linux-based system (64-bit)
- SSH access (password or key-based)
- Python 3.8+ (`python3` must be available on the remote `$PATH`)

### Local machine

- Docker (Desktop or Engine)
- A writable directory for `/config`
- A local downloads directory for `/downloads`

## Docker Compose (recommended)

Create a `docker-compose.yml`:

```yaml
services:
  seedsync:
    image: ghcr.io/nitrobass24/seedsync:latest
    container_name: seedsync
    ports:
      - "8800:8800"
    environment:
      - PUID=1000 # Your user ID (run `id` to find)
      - PGID=1000 # Your group ID
      # - UMASK=002 # Optional: file permission mask (002 for 775/664)
    volumes:
      - ./config:/config
      - /path/to/downloads:/downloads
    restart: unless-stopped
    # Hardened runtime baseline (recommended). The container starts as root
    # only to set up the PUID/PGID user, then drops to it via setpriv — so
    # no-new-privileges is compatible and only a few capabilities are needed.
    security_opt:
      - no-new-privileges:true
    cap_drop:
      - ALL
    cap_add:
      - CHOWN # chown /config and the user's home/.ssh
      - SETUID # create the user and setpriv into it
      - SETGID # create the group and setpriv into it
      - DAC_OVERRIDE # write user/group files during account setup
      - FOWNER # chmod/chown files the root setup step does not own
```

Start the container:

```bash
docker compose up -d
```

Open the UI at `http://localhost:8800` and complete the [configuration](./configuration.md).

## Docker Run

```bash
docker run -d \
  --name seedsync \
  -p 8800:8800 \
  -e PUID=1000 \
  -e PGID=1000 \
  --security-opt no-new-privileges \
  --cap-drop ALL \
  --cap-add CHOWN --cap-add SETUID --cap-add SETGID \
  --cap-add DAC_OVERRIDE --cap-add FOWNER \
  -v /path/to/config:/config \
  -v /path/to/downloads:/downloads \
  ghcr.io/nitrobass24/seedsync:latest
```

:::tip Hardened runtime
The `--security-opt` and `--cap-drop`/`--cap-add` flags above drop all Linux
capabilities except the few the container needs to create the `PUID`/`PGID`
user at startup, and block privilege escalation. They're recommended but
optional — omit them if you hit a permission error in an unusual environment.
:::

:::tip
To control file permissions for downloaded files, add `-e UMASK=002` (for 775/664) or `-e UMASK=000` (for 777/666). See [Configuration](./configuration.md#environment-variables) for details.
:::

## SSH key authentication (recommended)

Password-based SSH works, but key-based auth is more secure and reliable.

1. Generate a key pair and add the public key to your server.
2. Mount your SSH directory into the container:

```bash
-v ~/.ssh:/home/seedsync/.ssh:ro
```

3. In the UI, enable **Use password-less key-based authentication** and restart the container.

:::tip
If you run the container with a custom user (`PUID`/`PGID`), make sure that user can read the mounted `.ssh` directory.
:::

## Unraid

SeedSync is available as a Community Application on Unraid.

### 1. Add the template repository

In the Unraid web UI, go to **Docker → Template Repositories** and add:

```
https://github.com/nitrobass24/unraid-templates
```

Click **Save**.

### 2. Install from Community Applications

Go to the **Apps** tab, search for **SeedSync**, and click **Install**.

### 3. Review settings and apply

The template pre-fills sensible defaults for Unraid:

| Setting | Default |
|---------|---------|
| **Config path** | `/mnt/user/appdata/seedsync` |
| **Downloads path** | `/mnt/user/downloads/seedsync` |
| **Web UI port** | `8800` |
| **PUID / PGID** | `99` / `100` (Unraid `nobody`/`users`) |

Review the paths, adjust if needed, and click **Apply**.

### 4. Access the web UI

Open `http://<your-unraid-ip>:8800` and complete the [configuration](./configuration.md).

:::tip
The default PUID/PGID of `99`/`100` matches Unraid's `nobody`/`users` and is correct for most setups. Only change these if you have a specific reason to use a different user.
:::

:::tip
To use SSH key authentication on Unraid, add an extra path mapping in the template: mount your host key (e.g., `/root/.ssh/id_rsa`) to `/home/seedsync/.ssh/id_rsa` as read-only.
:::
