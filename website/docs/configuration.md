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
- **Remote Port**: SSH port, defaults to `22`. This is the **SSH/SFTP control port** and is **always used for scanning** (file discovery). When the transfer protocol is `sftp`, it is also the port used for transfers. It is **not** the FTPS port — see [Transfer Protocol (FTPS)](#transfer-protocol-ftps) below.
- **Username**: Remote SSH user
- **Password or SSH Key**: Use key-based auth when possible
- **Remote Path**: Path on the server to sync
- **Local Path**: Must be `/downloads` inside the container
- **Server Script Path**: Directory on the remote server where SeedSync copies its scanner utility. Defaults to `/tmp`. Some seedbox providers restrict writes to `/tmp` — if you see an SCP permission error on startup, change this to a directory you own (e.g. `~` or `~/.local`).
- **Remote Python Path**: Path to the Python 3 binary on the remote server. Leave empty to use the default `python3`. Set this if your seedbox has a custom Python install (e.g. `~/python3/bin/python3`).

## Transfer Protocol (FTPS)

By default SeedSync transfers files over **SFTP** (the SSH file-transfer protocol). You can optionally switch the transfer protocol to **FTPS** (FTP over TLS), which on high-latency links can reach significantly higher throughput than SFTP because it sidesteps the SSH layer and lets the raw TCP window autotune to the link's bandwidth-delay product.

These options live in the main Settings page:

- **Transfer Protocol**: `sftp` (default) or `ftps`. Selects how bulk file transfers are moved. Requires a restart to take effect.
- **Remote FTP Port**: The FTPS port on the remote server, defaults to `21`. **Only used when Transfer Protocol is `ftps`.** This is distinct from **Remote Port** (SSH); the two are almost always different (`21` vs `22`).
- **Verify FTPS Certificate**: Whether to validate the server's TLS certificate. **Off by default** — see the security note below. Requires a restart to take effect.

:::important Scanning always uses SSH
FTPS has no remote command execution, so SeedSync **always** discovers files (scans the remote directory) over SSH using your **Remote Server**, **Remote Port**, and credentials — regardless of the transfer protocol. This means FTPS mode is a hybrid: you need **both** working SSH access (for scanning) **and** working FTPS access (for transfers). Virtually all seedboxes offer both.

```
File discovery / scan  ── always ──▶  SSH   (Remote Port, e.g. 22)
Bulk file transfer     ── toggle ──▶  SFTP (Remote Port) | FTPS (Remote FTP Port, e.g. 21)
```

If scanning works (files appear in the dashboard) but transfers never start, the FTPS side is the likely culprit — see the [FAQ](./faq.md#ftps-transfers-never-start-but-scanning-works).
:::

### FTPS performance tuning differs from SFTP

When you select `ftps`, SeedSync automatically applies an FTPS-tuned connection profile that **overrides** the SFTP-oriented connection settings on the Connections panel. The two protocols want opposite shapes:

- **SFTP** needs many connections with heavy per-file parallelism (pget) to beat its per-stream cap.
- **FTPS** wants **file-level parallelism with low per-file connection counts** (pget-n of 1–2) and is actively hurt by pget-heavy configs.

The FTPS profile applied at transfer time is: 4 parallel files per directory, 1 connection per directory file, 4 connections per root single file, and a total connection limit of 8. Your manually-tuned SFTP **Connections** values are not used while `protocol = ftps`; switching back to `sftp` restores them.

:::note Per-pair connection limit caveat
The FTPS total-connection limit of 8 is **per LFTP instance** (per active path pair). If you run *N* enabled path pairs that all transfer from the same FTPS account, they can collectively open up to *N* × 8 connections. Some seedbox providers enforce a per-account FTP connection cap; if late transfers stall or drop to a crawl, reduce the number of simultaneously-enabled pairs.
:::

### FTPS certificate verification (security)

**Certificate verification is OFF by default.** The data channel is always TLS-encrypted, but with verification off SeedSync does **not** authenticate the server's certificate. This is **encryption without authentication**: an attacker positioned between SeedSync and the seedbox could present any certificate (a man-in-the-middle) and intercept the credential exchange. This is a real downgrade compared to SFTP, which authenticates the server via its SSH host key.

The default is off because many seedboxes ship self-signed or hostname-mismatched certificates that would otherwise fail validation. Each time an FTPS transfer starts with verification off, SeedSync logs a `WARNING` so the downgrade is never silent.

**Remediation — to close the MITM exposure, do one of the following:**

- Use a server with a properly-issued (CA-signed, hostname-matching) certificate, then enable **Verify FTPS Certificate**.
- If your provider's certificate validates, simply enable **Verify FTPS Certificate**.

If you cannot enable verification, treat the connection as encrypted-but-unauthenticated and weigh that against your threat model.

:::note FTPS tuning was validated on a specific lftp build
The FTPS parallelism profile was measured against Homebrew lftp 4.9.3, not the Alpine lftp shipped in the container image. If you see worse-than-expected FTPS throughput, the conservative fallback is to keep per-file connection counts low (`pget-n` of 1) and rely on file-level parallelism rather than raising pget.
:::

## Path Pairs

Path pairs let you sync from multiple remote directories independently. Each pair has its own remote path, local path, and settings.

To configure, go to **Settings → Path Pairs** and add entries. Each pair supports:

- **Name**: Display label for the pair
- **Remote Path**: Directory on the remote server
- **Local Path**: Directory inside the container (must be under `/downloads`)
- **Enabled**: Toggle the pair on or off
- **Auto Queue**: Automatically queue new files found in this pair's remote path
- **Exclude Patterns**: Glob patterns to skip (e.g. `*.nfo`, `Sample/`, `*.txt`)

When path pairs are active, the legacy Remote Path and Local Path fields in the main settings are disabled.

:::tip
Each path pair runs its own LFTP and scanner instance, so downloads and scanning happen independently per pair.
:::

## Exclude Patterns

Exclude patterns filter out files on the remote server before they appear in the dashboard or get auto-queued. Patterns use glob syntax:

- `*.nfo` — skip all `.nfo` files
- `Sample/` — skip directories named `Sample`
- `*.txt` — skip all `.txt` files

Configure exclude patterns per path pair, or in the main settings when using a single remote/local path.

## Connections

- **Max Parallel Downloads**: Number of items downloading simultaneously
- **Max Total Connections**: Overall connection limit (`0` = unlimited)
- **Max Connections Per File**: Per-file connection count for single files and directories
- **Max Parallel Files**: Number of files fetched in parallel within a directory download
- **Rename unfinished files**: Downloading files get a `.lftp` extension
- **Bandwidth Limit**: Cap download speed with values like `500K`, `2M`, or raw bytes/sec. Set to `0` or leave empty for unlimited.

:::note
These connection values are tuned for **SFTP** (the default). When the [transfer protocol](#transfer-protocol-ftps) is set to `ftps`, SeedSync applies its own FTPS-tuned profile at transfer time and these values are not used.
:::

## Integrity Check

SeedSync can verify that downloaded files match their remote originals. There are two independent mechanisms:

### Transfer verification (inline)

- **Verify transfers inline (recommended)**: When enabled, LFTP compares checksums during the download itself, catching corruption in real-time. Enabled by default.

### Post-download validation

- **Enable post-download validation**: Enables a separate validation step after download completes, comparing local and remote checksums via SSH. Disabled by default.
- **Auto-validate after download**: Automatically queue files for validation when their download finishes. Requires post-download validation to be enabled.
- **Hash Algorithm**: Algorithm used for both inline verification and post-download validation. Options: `md5`, `sha1`, `sha256`.

Once post-download validation is enabled, a **Validate** button appears next to downloaded files in the dashboard. Click it to manually verify a file at any time. Files show a status of **Validated** (checksum match) or **Corrupt** (mismatch).

:::note
Post-download validation is not available when **Delete from remote after download** is enabled, since the remote files are no longer available for comparison.
:::

## Logging

- **Verbose LFTP Logging**: Enable detailed LFTP transfer logging for troubleshooting. Off by default.

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

## Integrations (Sonarr / Radarr)

SeedSync can notify Sonarr and Radarr when a download completes, triggering an automatic import scan so your media library updates immediately.

### Setup

1. Go to **Settings → Integrations**
2. Enable the integration (Sonarr, Radarr, or both)
3. Enter the base URL (e.g. `http://sonarr:8989` or `http://radarr:7878`)
4. Enter the API key (found in the Arr app under **Settings → General → API Key**)
5. Click **Test Connection** to verify

### How it works

When a file transitions to the **Downloaded** state, SeedSync sends a `POST` to the Arr app's command API:

| App | Endpoint | Command |
| --- | --- | --- |
| Sonarr | `POST /api/v3/command` | `DownloadedEpisodesScan` |
| Radarr | `POST /api/v3/command` | `DownloadedMoviesScan` |

The request includes the absolute local path of the downloaded file, so the Arr app scans only that path instead of the entire download directory.

Notifications are fire-and-forget — they run in background threads and never block the download pipeline. Failed notifications are logged as warnings.

:::tip
If you run SeedSync and Arr apps in Docker, use the Docker service name as the host (e.g. `http://sonarr:8989`) and make sure all containers share a Docker network.
:::

:::note
The local path sent to the Arr app is the path **inside the SeedSync container**. If your Arr app sees a different mount path for the same files, configure a [remote path mapping](https://wiki.servarr.com/sonarr/settings#remote-path-mappings) in the Arr app.
:::

### Configuration reference

| Setting | Description |
| --- | --- |
| **Enable Sonarr/Radarr integration** | Toggle notifications on or off |
| **URL** | Base URL of the Arr app (e.g. `http://localhost:8989`) |
| **API Key** | Arr app API key (masked in the UI) |

## Webhooks

SeedSync can send HTTP POST notifications when file events occur. Configure the webhook URL in Settings under **Notifications**.

### Events

| Event | Trigger |
| --- | --- |
| `download_complete` | File finished downloading |
| `extraction_complete` | Archive extraction succeeded |
| `extraction_failed` | Archive extraction failed |
| `delete_complete` | File deleted |

Each event can be individually enabled or disabled via the checkboxes in Settings.

### Payload

Webhook requests are `POST` with `Content-Type: application/json`:

```json
{
  "event_type": "download_complete",
  "filename": "Movie.2024.mkv",
  "timestamp": "2024-01-15T12:34:56.789012+00:00",
  "pair_id": "abc123",
  "path": "Movie.2024.mkv"
}
```

| Field | Description |
| --- | --- |
| `event_type` | One of the event types above |
| `filename` | Name of the file or directory |
| `timestamp` | UTC ISO 8601 timestamp |
| `pair_id` | Path pair ID (omitted if not using path pairs) |
| `path` | Relative file path within the download directory |

## Advanced config file

SeedSync reads settings from `/config/settings.cfg`. You can edit it directly if needed, but the UI is preferred for most setups.
