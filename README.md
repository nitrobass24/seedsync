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
      # - UMASK=002  # Optional: file permission mask (002 for 775/664)
    volumes:
      - ./config:/config
      - /path/to/downloads:/downloads
      # Uncomment below to use SSH key authentication
      # - ~/.ssh/id_rsa:/home/seedsync/.ssh/id_rsa:ro
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

# Optional: control file permissions with UMASK
# -e UMASK=002  # 775/664 permissions
```

> **SSH Key Auth**: To use key-based authentication, mount your private key:
> `-v ~/.ssh/id_rsa:/home/seedsync/.ssh/id_rsa:ro`

### Unraid

SeedSync is available as a Community Application on Unraid.

1. In the Unraid web UI, go to **Docker → Template Repositories** and add:
   ```
   https://github.com/nitrobass24/unraid-templates
   ```
2. Go to the **Apps** tab, search for **SeedSync**, and click **Install**.
3. Review the default paths and click **Apply**:
   - **Config**: `/mnt/user/appdata/seedsync`
   - **Downloads**: `/mnt/user/downloads/seedsync`
4. Access the web UI at `http://<your-unraid-ip>:8800`

> **Note**: PUID/PGID default to `99`/`100` (Unraid's `nobody`/`users`), which is correct for most Unraid setups.

## Configuration

On first run, access the web UI and configure:

1. **Remote Server**: Your seedbox SSH hostname/IP
2. **SSH Credentials**: Username and password
3. **Remote Path**: Directory on the seedbox to sync from
4. **Local Path**: Maps to `/downloads` in the container

### SSH Key Authentication

To use password-less SSH key authentication:

1. Mount your private key into the container (see volume examples above)
2. In the web UI Settings, enable **"Use password-less key-based authentication"**
3. The password field can be left blank when key auth is enabled

### Bandwidth Limiting

You can limit download speed in Settings under the **Connections** section. The **Bandwidth Limit** field accepts:
- Numeric values in bytes/sec (e.g., `102400` for 100 KB/s)
- Values with suffixes: `K` for KB/s, `M` for MB/s (e.g., `500K`, `2M`)
- `0` or empty for unlimited

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
| `UMASK` | *(unset)* | File permission mask (e.g. `002` for 775/664, `000` for 777/666) |

## Volumes

| Path | Description |
|------|-------------|
| `/config` | Configuration and state files |
| `/downloads` | Download destination directory |
| `/home/seedsync/.ssh/id_rsa` | SSH private key (optional, for key-based auth) |

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
- If using SSH key auth, ensure the key is mounted at `/home/seedsync/.ssh/id_rsa` (read-only is fine)

### Remote Shell Not Found

If you see an error about `/bin/bash` not found, SeedSync will attempt to auto-detect the available shell on your remote server. Check the logs for the detected shell path. If detection fails, create a symlink on the remote server:

```bash
sudo ln -s /usr/bin/bash /bin/bash
```

## Report an Issue

Please report issues on the [issues page](https://github.com/nitrobass24/seedsync/issues).
Include container logs: `docker logs seedsync`

## License

SeedSync is distributed under Apache License Version 2.0.
See [LICENSE.txt](LICENSE.txt) for more information.

---

![SeedSync Screenshot](https://user-images.githubusercontent.com/12875506/37031587-3a5df834-20f4-11e8-98a0-e42ee764f2ea.png)
