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
- **Multiple path pairs** — sync from multiple remote directories independently
- Queue or auto-queue transfers by pattern
- **Exclude patterns** — filter out unwanted files with glob patterns
- **Multi-select** — bulk queue, stop, or delete files
- Extract archives after download
- Stage downloads on a fast disk, then move to final location
- **Webhook notifications** — HTTP POST on download/extract events
- Manage local and remote deletes
- Monitor transfer status from the web UI
- **Lightweight Docker image** — ~45 MB Alpine-based, multi-arch (amd64/arm64)

## Quick start

1. Follow the [Installation](./installation.md) guide to run the container.
2. Open the web UI at `http://localhost:8800`.
3. Go to Settings and configure your remote server and local paths.
4. Set up the [recommended workflow](./usage.md#recommended-setup) with hard links and auto-delete for a sync-once, never-re-download setup.

## Docs

- [Installation](./installation.md)
- [Usage](./usage.md)
- [Configuration](./configuration.md)
- [FAQ](./faq.md)
