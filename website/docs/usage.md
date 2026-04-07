---
title: Usage
---

## Recommended Setup

The best way to use SeedSync is with **hard links** and a dedicated completion directory. This ensures each file is downloaded exactly once and is never re-downloaded — even after a container restart.

### How it works

1. **Configure your torrent client** (qBittorrent, ruTorrent, etc.) to hard link completed downloads into a dedicated directory. For example, if your client downloads to `/downloads/tv`, have it hard link completed files to `/downloads/complete`.
2. **Point SeedSync** at the completion directory (`/downloads/complete`).
3. **Enable Auto-Queue** and turn on **"Delete remote file after syncing"** in Settings.

Hard links don't consume extra disk space on the seedbox — they create another reference to the same data on disk. When SeedSync finishes syncing and deletes from `/downloads/complete`, only the hard link is removed. The original file stays intact for seeding.

:::note
Hard links only work when both directories are on the **same filesystem**. If your download and completion directories are on different mounts, use a bind mount to place them on the same filesystem, or use a copy-on-complete script instead (at the cost of extra disk space).
:::

### Setting up hard links

- **qBittorrent**: Use [qbit-hardlinker](https://github.com/gravelfreeman/qbit-hardlinker) to automatically hard link completed downloads to your SeedSync directory.
- **ruTorrent**: Use a post-completion script that creates hard links. Note that the Autotools "Move to" option performs a *move*, not a hard link — this would break seeding since the original file is relocated.

### Example directory layout

```text
/downloads/
├── tv/              ← Sonarr downloads here, torrents continue seeding
├── movies/          ← Radarr downloads here
└── complete/        ← Hard links go here, SeedSync watches this directory
```

:::tip
This setup also solves the common problem of setting up SeedSync on a seedbox that already has many existing files. Since only newly completed downloads get hard-linked into the completion directory, SeedSync won't try to sync your entire library.
:::

## Dashboard

The Dashboard lists files and folders on the remote server and the local machine. From here you can:

- Queue items for transfer
- Extract archives after download
- Delete local or remote files
- Track progress and status
- **Multi-select** files using checkboxes, then apply bulk actions (queue, stop, delete)

## AutoQueue

AutoQueue can automatically queue new files discovered on the remote server.

- **Patterns only** lets you limit auto-queueing to specific matches.
- **Auto extract** automatically extracts archives after download completes.
- **Delete from remote** automatically removes files from the remote server after download, keeping your seedbox from filling up. When both auto-extract and delete-from-remote are enabled, extraction always runs before deletion.
- Patterns are managed from the AutoQueue page.

## Staging Directory

If you have a fast disk (NVMe/SSD) with limited space and a larger slow disk (HDD) for long-term storage, enable the staging directory feature under Settings. Downloads and extraction happen on the fast disk, then completed files are automatically moved to your final downloads folder for the Arrs or other tools to pick up.

See [Configuration](./configuration.md#staging-directory) for setup details.

## Dark Mode

Use the theme toggle in the navbar to switch between light and dark mode. Your preference is saved in the browser.

## Logs

The Logs page provides real-time streaming logs. Use it to diagnose connectivity or permission issues.

You can also query historical logs with search and level filters via the log query interface.

## Remote Diagnostics

On first connection to a remote server, SeedSync automatically runs diagnostics and logs useful information about the server environment (shell, LFTP version, disk space, etc.). Check the Logs page after initial setup to review.

## Path Pairs

If you sync from multiple remote directories, configure **Path Pairs** in Settings. Each pair runs its own LFTP and scanner instance. See [Configuration](./configuration.md#path-pairs) for details.

## Integrity Check

SeedSync can verify downloaded files match their remote originals using checksums.

- **Inline verification** runs automatically during transfer (enabled by default via LFTP's `xfer:verify`).
- **Post-download validation** is an optional second check that compares checksums via SSH after the file is on disk. Enable it in Settings under **Integrity Check**.

When post-download validation is enabled, a **Validate** button appears next to downloaded files. Click it to verify a file on demand. Files are marked **Validated** or **Corrupt** based on the result.

See [Configuration](./configuration.md#integrity-check) for setup details.

## Settings

All connection, path, and automation options live under Settings. Changes take effect after a restart.
