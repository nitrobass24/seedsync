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

## FTPS transfers fail with a TLS or certificate error

When the [transfer protocol](./configuration.md#transfer-protocol-ftps) is `ftps`, the Logs page may show TLS handshake or certificate-validation errors such as "certificate verification failed", "self-signed certificate", or "hostname mismatch".

This means **Verify FTPS Certificate** is enabled and the server's certificate could not be validated — common with seedboxes that use self-signed or hostname-mismatched certificates.

To fix:

- If your provider's certificate is properly issued (CA-signed, matching hostname), this usually indicates a real problem worth investigating with them.
- Otherwise, open **Settings**, turn **Verify FTPS Certificate** off, and restart. The data channel stays TLS-encrypted, but the certificate is no longer authenticated (SeedSync logs a `WARNING` each time it connects this way). See the [security note](./configuration.md#ftps-certificate-verification-security) for the trade-off.

If the error is a generic TLS handshake failure (not a certificate error), confirm the server actually offers FTPS on the configured **Remote FTP Port** (commonly `21`) and that it supports explicit `AUTH TLS`.

## FTPS transfers stall or never start behind a firewall/NAT

FTPS uses **passive mode**, which opens extra outbound data connections to ephemeral high-numbered ports on the server. If scanning works but transfers hang at "Logging in..." or never move data, a restrictive egress firewall is the usual cause.

- Allow outbound TCP from the container to the seedbox on the FTPS control port (typically `21`) **and** the provider's passive-mode port range.
- The container only makes *outbound* connections, so it works behind NAT without inbound port-forwarding — but the egress range must be open. See the [egress note](./installation.md#network-egress-ftps-only).

## FTPS transfers never start, but scanning works

If files appear in the dashboard (scanning succeeds) but downloads never begin when the transfer protocol is `ftps`, the most likely cause is a **protocol mismatch**: your seedbox offers SSH/SFTP but does **not** offer FTPS (or offers it on a different port than configured).

Scanning **always** uses SSH, so it keeps working even when FTPS is misconfigured — which makes this symptom look confusing. The transfer side, meanwhile, can't establish an FTPS session.

To fix:

- Confirm your provider actually offers FTPS, and on which port. Set that as **Remote FTP Port** in Settings (it is **not** the same as **Remote Port**, which is SSH).
- Check the Logs page for FTPS connection errors (connection refused, TLS handshake failure, certificate errors).
- If your provider does not offer FTPS at all, switch **Transfer Protocol** back to `sftp` in Settings and restart. SFTP uses the same SSH connection that scanning already relies on.

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
