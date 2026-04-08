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

SeedSync requires Python 3.5+ on the remote server to run its filesystem scanner. Most Linux servers include Python 3 by default, but some minimal or container-based seedbox environments may not.

To fix, install Python 3 on your remote server:

```bash
# Debian/Ubuntu
sudo apt-get install python3

# CentOS/RHEL
sudo yum install python3
```

If you don't have root access, check with your seedbox provider — most will have Python 3 available at a different path or can install it on request.

## My seedbox has Python 3 installed at a custom path

Some seedbox providers ship an older system Python or don't include Python 3 on the default `PATH`. If you've installed Python 3 to a custom location (e.g. your home directory), set **Remote Python Path** in Settings to the full path to the binary:

- Example: `~/python3/bin/python3`
- Example: `/home/user/.local/bin/python3`

Leave it empty to use the system default `python3`.

## What is the recommended way to set up SeedSync with my torrent client?

Use hard links with a dedicated completion directory and enable "Delete from remote after download." See the [Recommended Setup](./usage.md#recommended-setup) guide for full details.

## Where are settings stored?

Inside the container at `/config/settings.cfg`.
