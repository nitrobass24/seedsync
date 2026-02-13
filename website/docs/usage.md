---
title: Usage
---

## Dashboard

The Dashboard lists files and folders on the remote server and the local machine. From here you can:

- Queue items for transfer
- Extract archives after download
- Delete local or remote files
- Track progress and status

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

## Remote Diagnostics

On first connection to a remote server, SeedSync automatically runs diagnostics and logs useful information about the server environment (shell, LFTP version, disk space, etc.). Check the Logs page after initial setup to review.

## Settings

All connection, path, and automation options live under Settings. Changes take effect after a restart.
