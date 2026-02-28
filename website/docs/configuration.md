---
title: Configuration
---

SeedSync stores its state and settings in `/config` inside the container. Mount this to persist settings across updates.

```bash
-v /path/to/config:/config
```

## Web UI settings

Open the UI and fill out the Settings page:

- **Remote Server**: SSH hostname or IP
- **Remote Port**: Defaults to `22`
- **Username**: Remote SSH user
- **Password or SSH Key**: Use key-based auth when possible
- **Remote Path**: Path on the server to sync
- **Local Path**: Must be `/downloads` inside the container

## Connections

- **Max Parallel Downloads**: Number of items downloading simultaneously
- **Max Total Connections**: Overall connection limit (`0` = unlimited)
- **Max Connections Per File**: Per-file connection count for single files and directories
- **Max Parallel Files**: Number of files fetched in parallel within a directory download
- **Rename unfinished files**: Downloading files get a `.lftp` extension
- **Bandwidth Limit**: Cap download speed with values like `500K`, `2M`, or raw bytes/sec. Set to `0` or leave empty for unlimited.

## AutoQueue

- **Enabled**: Automatically queue new remote files
- **Patterns only**: Only queue items that match patterns
- **Auto extract**: Extract archives after download
- **Delete from remote after download**: Automatically delete files from the remote server after a successful download. When used with auto-extract, extraction runs first.

## Staging Directory

Use a fast staging disk (e.g. NVMe) for downloads and extraction, then automatically move completed files to your final downloads folder.

- **Use staging directory**: Enable or disable the staging workflow
- **Staging Path**: Path inside the container where files are temporarily downloaded and extracted

When enabled, the download flow becomes:

1. LFTP downloads to the **staging path** (fast disk)
2. Archives are extracted **in staging** (fast disk)
3. Completed files are moved to `/downloads` (final location)
4. Staging copy is deleted after size verification

:::tip
Mount your fast disk as a Docker volume and set the staging path in the UI. For example:

```yaml
volumes:
  - /mnt/nvme/staging:/staging
  - /mnt/hdd/downloads:/downloads
```

Then set **Staging Path** to `/staging` in Settings.
:::

## Environment variables

| Variable | Default | Description |
| --- | --- | --- |
| `PUID` | 1000 | User ID for file ownership |
| `PGID` | 1000 | Group ID for file ownership |
| `UMASK` | *(unset)* | File permission mask (e.g. `002` for 775/664, `000` for 777/666) |

## Volumes

| Path | Description |
| --- | --- |
| `/config` | Settings, state, and logs |
| `/downloads` | Local download destination |

## Ports

| Port | Description |
| --- | --- |
| `8800` | Web UI |

## Advanced LFTP

These settings are collapsed by default under **Advanced LFTP** in the Settings page. They map directly to LFTP configuration options and are useful for tuning performance on fast or unreliable links.

- **Socket Buffer Size**: Socket buffer size. Supports suffixes like `8M`, `16M`. Larger values improve throughput on fast links. (`net:socket-buffer`)
- **Min Chunk Size**: Minimum chunk size for parallel file downloads. Supports suffixes like `100M`. (`pget:min-chunk-size`)
- **Parallel Directories**: Download directory contents in parallel rather than sequentially. (`mirror:parallel-directories`)
- **Network Timeout (s)**: Seconds to wait for network operations before timing out. (`net:timeout`)
- **Max Retries**: Maximum number of retries on network errors. `0` for unlimited. (`net:max-retries`)
- **Reconnect Interval Base (s)**: Base delay in seconds before reconnecting after a failure. (`net:reconnect-interval-base`)
- **Reconnect Interval Multiplier**: Multiplier applied to the reconnect delay after each consecutive failure. (`net:reconnect-interval-multiplier`)

## Advanced config file

SeedSync reads settings from `/config/settings.cfg`. You can edit it directly if needed, but the UI is preferred for most setups.
