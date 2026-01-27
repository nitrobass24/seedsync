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

## Where are settings stored?

Inside the container at `/config/settings.cfg`.
