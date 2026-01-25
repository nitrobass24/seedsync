# SeedSync Modernization Plan

## Project Overview

SeedSync is a file synchronization tool that uses LFTP to transfer files from remote seedboxes.
This document outlines the current state, issues, and plan to get it working again.

---

## Current Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Docker Container                          │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                    Python Backend                         │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐   │   │
│  │  │ Controller  │  │   WebApp    │  │    AutoQueue    │   │   │
│  │  │ (LFTP sync) │  │  (Bottle)   │  │  (Pattern match)│   │   │
│  │  └─────────────┘  └─────────────┘  └─────────────────┘   │   │
│  │         │                │                               │   │
│  │         ▼                ▼                               │   │
│  │  ┌─────────────────────────────────────────────────────┐ │   │
│  │  │              Shared Model & State                    │ │   │
│  │  └─────────────────────────────────────────────────────┘ │   │
│  └──────────────────────────────────────────────────────────┘   │
│                              │                                   │
│                              ▼                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              Angular Frontend (Port 8800)                 │   │
│  │  • File browser                                           │   │
│  │  • Settings configuration                                 │   │
│  │  • Log viewer                                             │   │
│  │  • Auto-queue management                                  │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
         │                                    │
         ▼                                    ▼
   ┌───────────┐                      ┌──────────────┐
   │  /config  │                      │  /downloads  │
   │  volume   │                      │    volume    │
   └───────────┘                      └──────────────┘
```

---

## Critical Issues Identified

### Issue 1: Incomplete Docker Image (BLOCKING)

**Problem:** The simplified Dockerfile at `src/docker/build/docker-image/Dockerfile` is missing:
- Angular frontend build (no `/app/html`)
- scanfs binary (no `/app/scanfs`)

**Impact:** Container starts but web UI doesn't work, filesystem scanning fails.

**Solution:** Create a complete multi-stage Dockerfile that builds all components.

### Issue 2: PUID/PGID Not Applied (GitHub #137)

**Problem:** The entrypoint script creates the user but the application may fail
to write to mounted volumes if permissions don't match.

**Solution:** Ensure proper permission handling in entrypoint script.

### Issue 3: libz.so.1 Errors (GitHub #136, #97)

**Problem:** The scanfs binary is built with PyInstaller and depends on glibc/zlib
that may not match the remote server environment.

**Note:** This affects remote server scanning, not the Docker container itself.
May require running scanfs directly from Python instead of as a binary.

### Issue 4: LFTP Parsing Errors (GitHub #144, #106)

**Problem:** The LFTP status parser may fail with certain server responses.

**Investigation needed:** Review parser code at `src/python/lftp/`

---

## Development Environment Setup

### Prerequisites

1. **Docker Desktop** (Required)
   - macOS: Download from https://www.docker.com/products/docker-desktop
   - Includes Docker Compose

2. **Git** (Already configured)

### Quick Start (After Docker installed)

```bash
# Clone your fork (already done)
cd ~/projects/seed-sync/seedsync

# Build the Python test environment
make tests-python

# Run Python tests
make run-tests-python

# Build complete Docker image (once fixed)
make docker-image
```

### Local Python Development (Optional)

```bash
# Install Poetry
pip3 install poetry

# Navigate to Python source
cd src/python

# Install dependencies
poetry install

# Run tests
poetry run pytest tests/unittests -v
```

---

## Modernization Roadmap

### Phase 1: Fix Docker Build (Priority: CRITICAL)

**Goal:** Get a working Docker image

**Tasks:**
1. [ ] Create complete multi-stage Dockerfile
2. [ ] Update base images:
   - Ubuntu 16.04 → Ubuntu 22.04 (for PyInstaller build)
   - Python 3.8 → Python 3.11
   - Node 12 → Node 18 LTS
3. [ ] Fix entrypoint.sh permission handling
4. [ ] Test image locally
5. [ ] Verify web UI loads
6. [ ] Verify file sync works

### Phase 2: Dependency Updates (Priority: HIGH)

**Goal:** Update Python dependencies without breaking functionality

**Tasks:**
1. [ ] Update pyproject.toml Python requirement: `~3.8` → `^3.11`
2. [ ] Update Poetry and regenerate lock file
3. [ ] Run unit tests, fix any failures
4. [ ] Test integration with LFTP

### Phase 3: Fix Known Issues (Priority: MEDIUM)

**Tasks:**
1. [ ] Investigate LFTP parsing errors (#144, #106)
2. [ ] Address memory usage (#107)
3. [ ] Consider alternatives to scanfs binary

### Phase 4: Angular Modernization (Priority: LOW)

**Warning:** This is a significant undertaking.

**Options:**
- **Option A:** Update Angular 4 → Angular 17 (Major rewrite)
- **Option B:** Keep Angular 4, just update build tooling
- **Option C:** Replace with simpler frontend (Vue, React, or vanilla JS)

**Recommendation:** Defer until Phases 1-3 are complete.

---

## Key Files Reference

| File | Purpose |
|------|---------|
| `src/docker/build/docker-image/Dockerfile` | Docker image build |
| `src/docker/build/docker-image/entrypoint.sh` | Container startup script |
| `src/docker/build/deb/Dockerfile` | Multi-stage build (reference) |
| `src/python/pyproject.toml` | Python dependencies |
| `src/python/seedsync.py` | Main application entry |
| `src/angular/package.json` | Frontend dependencies |
| `Makefile` | Build orchestration |

---

## Testing Strategy

### Unit Tests
```bash
# Python tests (in Docker)
make run-tests-python

# Angular tests (in Docker)
make run-tests-angular
```

### Integration Testing
```bash
# End-to-end tests
make run-tests-e2e
```

### Manual Testing Checklist
- [ ] Container starts without errors
- [ ] Web UI accessible at http://localhost:8800
- [ ] Can configure remote server settings
- [ ] Can see remote file list
- [ ] Can queue file for download
- [ ] Download completes successfully
- [ ] Auto-queue triggers correctly

---

## Next Steps

1. **Install Docker Desktop** on your Mac
2. **Review the Dockerfile fix** (I'll prepare this)
3. **Test the fixed Docker image**
4. **Report any issues** for collaborative debugging

---

## Resources

- [Original Repository](https://github.com/ipsingh06/seedsync)
- [Your Fork](https://github.com/nitrobass24/seedsync)
- [Docker Documentation](https://docs.docker.com/)
- [LFTP Manual](https://lftp.yar.ru/lftp-man.html)
