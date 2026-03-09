---
title: FAQ
---

## How do I keep settings across updates?

Mount a host directory to `/config`:

```bash
-v /path/to/config:/config
```

## Does SeedSync collect any data?

No. SeedSync does not collect or transmit data.

## SeedSync can't connect to my remote server

- Verify the hostname/IP and SSH port
- Confirm username/password or SSH key
- Check the Logs page for specific errors

## Locale errors in logs

Some servers require a matching locale. Add these environment variables to the container:

```bash
-e LC_ALL=en_US.UTF-8
-e LANG=en_US.UTF-8
```

## SeedSync can't find a shell on my remote server

SeedSync automatically detects the available shell on the remote server, checking `/bin/bash`, `/usr/bin/bash`, and `/bin/sh` in order. If none of these are available or your provider restricts shell access, check with your provider for the correct shell path.

## SeedSync fails with "scp: dest open '/tmp/scanfs': Permission denied"

Some seedbox providers restrict writes to `/tmp` on the remote server. SeedSync copies its scanner utility there by default.

To fix this, open the Settings page, find **Server Script Path**, and change it from `/tmp` to a directory you own on the remote server — for example:

- `~` (your home directory)
- `~/.local`
- `/home/yourusername`

Save and restart. SeedSync will copy the scanner to the new path on its next startup.

## SeedSync fails with "Server Script Path is a directory on the remote server"

This happens when **Server Script Path** overlaps with your sync directory. For example, if your remote sync path is `/home/user/downloads` and the script path is also set to `/home/user/downloads`, SeedSync tries to install `scanfs` there — but if a folder named `scanfs` already exists (from a previous sync), it can't be overwritten.

To fix:

1. Change **Server Script Path** to a location outside your sync tree, such as `~` or `~/.local`.
2. Remove the conflicting directory from the remote server:

   ```bash
   rm -rf /home/user/downloads/scanfs
   ```

   Replace `/home/user/downloads` with your actual remote sync path.

3. Save and restart the container.

## SeedSync fails with "command not found: python3"

SeedSync requires Python 3 on the remote server to run its filesystem scanner. Most Linux servers include Python 3 by default, but some minimal or container-based seedbox environments may not.

To fix, install Python 3 on your remote server:

```bash
# Debian/Ubuntu
sudo apt-get install python3

# CentOS/RHEL
sudo yum install python3
```

If you don't have root access, check with your seedbox provider — most will have Python 3 available at a different path or can install it on request.

## What is the recommended way to set up SeedSync with my torrent client?

The best approach is to use **hard links** with a dedicated completion directory. This keeps SeedSync's sync directory clean, avoids downloading files you don't want, and lets your torrents continue seeding without interference.

### How it works

1. **Configure your torrent client** (ruTorrent, qBittorrent, etc.) to hard link completed downloads into a dedicated directory. For example, if your client downloads to `/downloads/tv`, have it hard link completed files to `/downloads/complete`.
2. **Point SeedSync** at the completion directory (`/downloads/complete`).
3. **Enable Auto-Queue** and turn on **"Delete remote file after syncing"** in SeedSync settings.

Hard links don't consume extra disk space on the seedbox — they create another reference to the same data on disk. When SeedSync finishes syncing and deletes from `/downloads/complete`, only the hard link is removed. The original file stays intact for seeding.

### Setting up hard links

- **qBittorrent**: Use [qbit-hardlinker](https://github.com/gravelfreeman/qbit-hardlinker) to automatically hard link completed downloads to your SeedSync directory.
- **ruTorrent**: Use the "Autotools" plugin with the "Move to" option, or a post-completion script that creates hard links.

### Example directory layout

```
/downloads/
├── tv/              ← Sonarr downloads here, torrents continue seeding
├── movies/          ← Radarr downloads here
└── complete/        ← Hard links go here, SeedSync watches this directory
```

:::tip
This setup also solves the common problem of setting up SeedSync on a seedbox that already has many existing files. Since only newly completed downloads get hard linked into the completion directory, SeedSync won't try to sync your entire library.
:::

## Where are settings stored?

Inside the container at `/config/settings.cfg`.
