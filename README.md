<p align="center">
    <img src="https://user-images.githubusercontent.com/12875506/85908858-c637a100-b7cb-11ea-8ab3-75c0c0ddf756.png" alt="SeedSync" />
</p>

<p align="center">
  <a href="https://github.com/nitrobass24/seedsync">
    <img src="https://img.shields.io/github/stars/nitrobass24/seedsync" alt="Stars">
  </a>
  <a href="https://github.com/nitrobass24/seedsync/pkgs/container/seedsync">
    <img src="https://ghcr-badge.elias.eu.org/shield/nitrobass24/seedsync/seedsync" alt="Docker Pulls">
  </a>
  <a href="https://github.com/nitrobass24/seedsync/pkgs/container/seedsync">
    <img src="https://ghcr-badge.egpl.dev/nitrobass24/seedsync/size" alt="Image Size">
  </a>
  <a href="https://github.com/nitrobass24/seedsync/blob/master/LICENSE.txt">
    <img src="https://img.shields.io/github/license/nitrobass24/seedsync" alt="License">
  </a>
  <a href="https://nitrobass24.github.io/seedsync/">
    <img src="https://img.shields.io/badge/docs-website-blue" alt="Documentation">
  </a>
</p>

SeedSync is a tool to sync files from a remote Linux server (like your seedbox) to your local machine.
It uses LFTP to transfer files fast!

> **Note**: This is a modernized fork of [ipsingh06/seedsync](https://github.com/ipsingh06/seedsync) with updated dependencies and Docker-only deployment.

## Features

* Built on top of [LFTP](http://lftp.tech/), the fastest file transfer program
* Web UI - track and control your transfers from anywhere
* Automatically extract your files after sync
* Auto-Queue - only sync the files you want based on pattern matching
* Delete local and remote files easily
* Fully open source!

## Documentation

Full documentation is available at **[nitrobass24.github.io/seedsync](https://nitrobass24.github.io/seedsync/)**

## Quick Start (Docker)

### Using Docker Compose (Recommended)

1. Create a `docker-compose.yml`:

```yaml
services:
  seedsync:
    image: ghcr.io/nitrobass24/seedsync:latest
    container_name: seedsync
    ports:
      - "8800:8800"
    environment:
      - PUID=1000  # Your user ID (run 'id' to find)
      - PGID=1000  # Your group ID
    volumes:
      - ./config:/config
      - /path/to/downloads:/downloads
    restart: unless-stopped
```

2. Start the container:

```bash
docker compose up -d
```

3. Access the web UI at **http://localhost:8800**

### Using Docker Run

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

## Configuration

On first run, access the web UI and configure:

1. **Remote Server**: Your seedbox SSH hostname/IP
2. **SSH Credentials**: Username and password (or SSH key)
3. **Remote Path**: Directory on the seedbox to sync from
4. **Local Path**: Maps to `/downloads` in the container

## Building from Source

```bash
# Clone the repository
git clone https://github.com/nitrobass24/seedsync.git
cd seedsync

# Build and run
make build
make run

# View logs
make logs
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PUID` | 1000 | User ID for file permissions |
| `PGID` | 1000 | Group ID for file permissions |

## Volumes

| Path | Description |
|------|-------------|
| `/config` | Configuration and state files |
| `/downloads` | Download destination directory |

## Ports

| Port | Description |
|------|-------------|
| 8800 | Web UI |

## Troubleshooting

### View Logs

```bash
docker logs seedsync
```

### Permission Issues

Ensure your `PUID` and `PGID` match your host user:

```bash
id  # Shows your UID and GID
```

### SSH Connection Issues

- Verify your seedbox allows SSH connections
- Check that the SSH port is correct (default: 22)
- Ensure your credentials are correct

## Report an Issue

Please report issues on the [issues page](https://github.com/nitrobass24/seedsync/issues).
Include container logs: `docker logs seedsync`

## License

SeedSync is distributed under Apache License Version 2.0.
See [LICENSE.txt](LICENSE.txt) for more information.

---

![SeedSync Screenshot](https://user-images.githubusercontent.com/12875506/37031587-3a5df834-20f4-11e8-98a0-e42ee764f2ea.png)
