---
title: Installation
---

SeedSync runs in Docker and does not require anything installed on the remote server beyond SSH access.

## Requirements

### Remote server

- Linux-based system (64-bit)
- SSH access (password or key-based)

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
  -v /path/to/config:/config \
  -v /path/to/downloads:/downloads \
  ghcr.io/nitrobass24/seedsync:latest
```

:::tip
To control file permissions for downloaded files, add `-e UMASK=002` (for 775/664) or `-e UMASK=000` (for 777/666). See [Configuration](./configuration.md#environment-variables) for details.
:::

## SSH key authentication (recommended)

Password-based SSH works, but key-based auth is more secure and reliable.

1. Generate a key pair and add the public key to your server.
2. Mount your SSH directory into the container:

```bash
-v ~/.ssh:/home/seedsync/.ssh
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
