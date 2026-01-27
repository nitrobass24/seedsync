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
