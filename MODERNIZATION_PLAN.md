# SeedSync Modernization - Complete

This document summarizes the modernization work completed on SeedSync.

## Project Status: COMPLETE

The fork at [github.com/nitrobass24/seedsync](https://github.com/nitrobass24/seedsync) is now fully functional with modern dependencies and Docker-only deployment.

---

## What Was Done

### Phase 1: Fix Docker Build

| Task | Status |
|------|--------|
| Create complete multi-stage Dockerfile | Done |
| Update Python 3.8 to 3.12 | Done |
| Fix Angular build (node-sass to sass) | Done |
| Fix entrypoint.sh permissions | Done |
| Verify web UI loads | Done |

### Phase 2: Dependency Updates

| Task | Status |
|------|--------|
| Update Python dependencies | Done |
| Remove Poetry (use pip) | Done |
| Remove mkdocs from runtime | Done |
| Fix Python 3.12 deprecation warnings | Done |

### Phase 3: Simplify for Docker-Only

| Task | Status |
|------|--------|
| Remove Debian packaging | Done |
| Remove legacy build files | Done |
| Simplify Makefile | Done |
| Update GitHub Actions | Done |
| Update documentation | Done |

### Phase 4: Angular Modernization

Angular 21 migration completed in v0.11.0 (fresh rewrite, not based on earlier v0.10.0 attempt).

| Task | Status |
|------|--------|
| Upgrade Angular 4 to 21 | Done |
| Standalone components (no NgModules) | Done |
| Bootstrap 4 to 5.3 with JS bundle | Done |
| Replace Immutable.js with native TypeScript | Done |
| Replace ngx-modialog with inline patterns | Done |
| RxJS 5 to 7 pipe operators | Done |
| Update Dockerfile to Node 22 | Done |
| Font Awesome 4 to 7 | Done |
| Replace css-element-queries with ResizeObserver | Done |

### Phase 5: Security Hardening (v0.12.10)

| Task | PR | Status |
|------|-----|--------|
| Security response headers (CSP, X-Frame-Options, etc.) | #130 | Done |
| CSRF protection with Origin/Referer validation | #130 | Done |
| Per-IP rate limiting (120 req/60s sliding window) | #130 | Done |
| Optional API key authentication | #130 | Done |
| Filename validation and path traversal protection | #130 | Done |
| Zip-slip extraction protection (pre/post validation) | #130 | Done |
| Config file auto-backup (keeps last 10) | #130 | Done |
| CSP-compliant Angular build | #134 | Done |
| Eager ConfigService initialization | #136 | Done |
| Scanner home directory fallback | #114 | Done |
| SFTP umask fix | #115 | Done |

### Phase 6: Multi-Pair Architecture & Infrastructure (v0.13.0)

| Task | PR(s) | Status |
|------|-------|--------|
| Multiple path pairs with per-pair LFTP/scanner | #122, #149, #155, #161 | Done |
| Path pairs settings UI | #160, #162, #163 | Done |
| Exclude patterns for remote files | #146 | Done |
| Multi-select and bulk operations | #123 | Done |
| Webhook notifications | #128 | Done |
| Historical log query endpoint | #124 | Done |
| Structured JSON logging | #127 | Done |
| Replace paste WSGI with Bottle built-in | #140 | Done |
| Replace patool with direct subprocess | #141, #145 | Done |
| Python scanfs replaces PyInstaller binary | #148 | Done |
| JSON serialization for scanfs | #129 | Done |
| Alpine Docker image variant | #164 | Done |
| Dual-image CI (Debian + Alpine) | #164 | Done |
| Docker HEALTHCHECK | #164 | Done |
| Startup log improvements | #165 | Done |

---

## Results

### Image Size Reduction

| Version | Image Size | Notes |
|---------|-----------|-------|
| Original fork | 439 MB | Python 3.8, Poetry, Debian packaging |
| v0.10.0 | 240 MB | Modernized deps, multi-stage build |
| v0.12.10 | 170 MB | Security hardening release |
| v0.13.0 (Debian) | 126 MB (amd64) | Multi-pair architecture, slim build |
| v0.13.0 (Alpine) | 45 MB (amd64) | Lightweight Alpine variant |

### Files Changed

**Removed:**
- `src/debian/` - Debian packaging (12 files)
- `src/docker/build/deb/` - Deb build Dockerfile
- `src/docker/stage/` - Legacy staging (20+ files)
- `.github/workflows/master.yml` - Old complex workflow
- `.github/workflows/docker-image.yml` - Broken workflow

**Added/Updated:**
- `src/docker/build/docker-image/Dockerfile` - Complete multi-stage build
- `src/python/requirements.txt` - Minimal runtime deps
- `.github/workflows/ci.yml` - Simplified CI/CD
- `Makefile` - Docker-focused commands
- `README.md` - Docker-only instructions
- `CHANGELOG.md` - Release notes

---

## Architecture

```
+------------------------------------------------------------------+
|                      Docker Container                             |
|                (126 MB Debian / 45 MB Alpine)                     |
|                                                                   |
|  +-------------+       +-------------+                            |
|  | Python 3.12 |       | Angular 21  |                            |
|  |   Bottle    |<------|   Web UI    |                            |
|  |  REST API   |       |             |                            |
|  +------+------+       +-------------+                            |
|         |                                                         |
|  +------v-------------------------------------------------+       |
|  |                    Controller                           |       |
|  |                                                         |       |
|  |  +-- PathPair 1 --+   +-- PathPair 2 --+   ...         |       |
|  |  | LFTP  Scanner  |   | LFTP  Scanner  |               |       |
|  |  +-------+--------+   +-------+--------+               |       |
|  |          |                     |                        |       |
|  +----------+---------------------+------------------------+       |
|             |                     |                               |
|             v                     v                               |
|          Seedbox (per-pair remote/local paths)                    |
|                                                                   |
|  +-------------+                                                  |
|  |  Security   | CSP, CSRF, Rate Limit, API Key                  |
|  +-------------+                                                  |
+------------------------------------------------------------------+
```

---

## Known Limitations

### 1. scanfs Compatibility
- Replaced PyInstaller binary with plain Python script in v0.13.0
- Requires Python 3.8+ on the remote seedbox
- Home directory fallback when `/tmp` is restricted (v0.12.10)

### 2. LFTP Parsing
- Some edge cases in LFTP output parsing
- May affect certain server configurations
- Report issues if encountered

### 3. Multi-Pair Extraction (v0.13.0)
- Extraction is hard-wired to the first path pair's filesystem paths (#167)
- Per-pair extraction requires a separate `ExtractProcess` per pair — tracked for future release

### 4. Shared Staging Directory (v0.13.0)
- All path pairs share a single staging directory when staging is enabled (#168)
- Same-named files from different pairs will collide
- Fix: per-pair staging subdirectories

### 5. Pair Name Uniqueness (v0.13.0)
- Duplicate pair names are not rejected (#169)
- Can cause ambiguous lookups when `pair_id` is omitted from API requests
- Fix: validate uniqueness on create/update

### 6. All Pairs Disabled (v0.13.0)
- Controller falls back to legacy pair instead of pausing gracefully (#170)
- Better UX would be an idle state with UI indication

---

## Quick Reference

### Build & Run
```bash
make build    # Build image
make run      # Start container
make logs     # View logs
make stop     # Stop container
```

### Release
```bash
git tag vX.Y.Z
git push origin vX.Y.Z
# GitHub Actions handles the rest
```

### Container Access
```
Web UI: http://localhost:8800
Volumes: /config, /downloads
Env: PUID, PGID, UMASK
```

---

## Credits

- Original project: [ipsingh06/seedsync](https://github.com/ipsingh06/seedsync)
- Modernization: [nitrobass24/seedsync](https://github.com/nitrobass24/seedsync)
