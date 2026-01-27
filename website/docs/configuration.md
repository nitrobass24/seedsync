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

## AutoQueue

- **Enabled**: Automatically queue new remote files
- **Patterns only**: Only queue items that match patterns
- **Auto extract**: Extract archives after download

## Environment variables

| Variable | Default | Description |
| --- | --- | --- |
| `PUID` | 1000 | User ID for file ownership |
| `PGID` | 1000 | Group ID for file ownership |

## Volumes

| Path | Description |
| --- | --- |
| `/config` | Settings, state, and logs |
| `/downloads` | Local download destination |

## Ports

| Port | Description |
| --- | --- |
| `8800` | Web UI |

## Advanced config file

SeedSync reads settings from `/config/settings.cfg`. You can edit it directly if needed, but the UI is preferred for most setups.
