---
title: SeedSync
slug: /
---

SeedSync is a Docker-first tool that syncs files from a remote Linux server (like a seedbox) to your local machine. It uses LFTP for fast transfers and provides a web UI for monitoring, queueing, and automation.

:::note
This is the modernized fork of `ipsingh06/seedsync`, with updated dependencies and Docker-only deployment.
:::

## What you can do

- Sync files quickly using LFTP
- Queue or auto-queue transfers by pattern
- Extract archives after download
- Stage downloads on a fast disk, then move to final location
- Manage local and remote deletes
- Monitor transfer status from the web UI

## Quick start

1. Follow the [Installation](./installation.md) guide to run the container.
2. Open the web UI at `http://localhost:8800`.
3. Go to Settings and configure your remote server and local paths.

## Docs

- [Installation](./installation.md)
- [Usage](./usage.md)
- [Configuration](./configuration.md)
- [FAQ](./faq.md)
