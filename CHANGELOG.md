# Changelog

## [0.10.4] - 2026-01-27

### Fixed
- **Remote paths with tilde (~)** - Fixed remote scanner to properly handle paths containing `~`. The tilde is now converted to `$HOME` for shell expansion, allowing users whose SSH and LFTP paths differ (e.g., LFTP locked to home directory). (#14)

---

## [0.10.3] - 2026-01-27

### Fixed
- **Restart button** - Fixed server restart functionality that was broken due to Bottle framework's custom `__setattr__` blocking attribute updates. Now uses `threading.Event` for thread-safe signaling.
- **Settings persistence** - Settings are now properly saved before restart
- **Restart notification** - "Restart the app to apply new settings" notification now clears immediately when restart button is clicked

### Changed
- **About page** - Updated GitHub repository link to nitrobass24/seedsync and copyright information

---

## [0.10.2] - 2026-01-27

### Fixed
- **scanfs architecture mismatch** - Force AMD64 build for scanfs binary since it runs on remote seedbox servers, not locally. Fixes "cannot execute binary file: Exec format error" on ARM-based local machines.

---

## [0.10.1] - 2026-01-27

### Reverted
- **Angular 17 rollback** - Reverted to Angular 4 due to runtime issues. Angular 17 code preserved in `src/angular-v17/` for future work.

### Changed
- **Dockerfile** - Reverted to Node 12 for Angular 4 compatibility

---

## [0.10.0] - 2026-01-27

### Changed
- **Angular 4 → 17** - Complete frontend rewrite with modern Angular
  - Standalone components (no NgModules)
  - Bootstrap 4 → 5.3 (removes jQuery dependency)
  - RxJS 5 → 7 with pipe operators
  - Immutable.js removed (native TypeScript)
  - ngx-modialog → Angular CDK Dialog
  - Node 12 → Node 20 for builds
- **Smaller JS bundles** - ~150-200KB reduction from removed dependencies
- **scanfs builder** - Now uses Debian Bullseye (glibc 2.31) as Buster repos are EOL

### Added
- `src/angular-v4/` - Original Angular 4 code preserved for rollback if needed

### Fixed
- **Dockerfile compatibility** - Fixed Python/Debian version combinations for multi-stage build

---

## [0.9.4] - 2026-01-26

### Fixed
- **Docker entrypoint UID/GID handling** - Fixed container crash when PGID matches an existing group ID in the container (e.g., Synology with GID 101). Now checks for existing UID/GID by ID instead of name, allowing reuse of pre-existing system groups. (#4)
- **scanfs glibc compatibility** - Fixed "Failed to load Python shared library" error on older seedbox servers by building scanfs on Debian Buster (glibc 2.28) instead of Bookworm (glibc 2.36). Now supports Linux systems from 2018+. (#5)

### Changed
- **Improved entrypoint logging** - Now shows whether existing users/groups are being reused for easier debugging of permission issues

---

## [0.9.3] - 2026-01-26

### Security
- **Updated requests** to >=2.32.0 (fixes credential leak, session verification issues)
- **Updated urllib3** to >=2.2.0 (fixes redirect bombs, decompression vulnerabilities)
- **Updated certifi** to >=2024.7.4 (removes revoked root certificates)
- **Updated pyinstaller** to >=6.0 (fixes privilege escalation in build)

### Removed
- **poetry.lock** - Removed unused lock file that was triggering 30 Dependabot alerts
- **mkdocs/mkdocs-material** - Removed documentation tools from pyproject.toml (not needed at runtime)

### Changed
- Cleaned up `pyproject.toml` with explicit version constraints

---

## [0.9.2] - 2026-01-26

### Fixed
- **Python 3.12 regex warnings** - Converted all regex patterns to raw strings across:
  - `lftp/job_status_parser.py` - LFTP output parsing patterns
  - `system/scanner.py` - File size parsing patterns
  - `controller/extract/dispatch.py` - RAR file extension pattern

### Changed
- **CI workflow** - Updated `softprops/action-gh-release` to v2 with `make_latest: true`

---

## [0.9.1] - 2025-01-25

### Changed
- **Docker-only deployment** - Removed Debian package support, simplified to Docker-only
- **Image size reduced 45%** - From 439MB to 240MB
- **Python 3.12** - Updated from Python 3.11 to 3.12
- **Replaced Poetry with pip** - Faster builds, smaller image
- **Replaced node-sass with sass** - Pure JS, no native compilation needed
- **Fixed Python 3.12 regex warnings** - Updated to raw strings

### Removed
- Debian packaging (`src/debian/`)
- Legacy build files (`src/docker/build/deb/`, `src/docker/stage/`)
- mkdocs/mkdocs-material from runtime (documentation tools not needed)

### Added
- `requirements.txt` - Minimal runtime dependencies
- Simplified `Makefile` with Docker-focused commands

---

## [0.9.0] - 2025-01-25

### Fixed
- **Docker image now works** - Complete rewrite of Dockerfile to properly build all components
- **Angular frontend included** - Web UI was missing from previous Docker builds
- **scanfs binary included** - File system scanner now properly built and included
- **PUID/PGID permissions** - Improved entrypoint script for proper user/group handling
- **Python 3.11 support** - Updated from Python 3.8 (EOL) to Python 3.11
- **TypeScript build errors** - Fixed type conflicts in Angular build

### Changed
- **Dockerfile**: Complete multi-stage build that includes:
  - Stage 1: Angular frontend build (Node 12)
  - Stage 2: scanfs binary build (PyInstaller)
  - Stage 3: Python runtime with all components
- **pyproject.toml**: Updated Python version constraint from `~3.8` to `^3.8` (allows 3.8-3.12)
- **package.json**: Updated node-sass version for build compatibility
- **tsconfig.json**: Added `skipLibCheck` to resolve type definition conflicts
- **entrypoint.sh**: Enhanced permission handling for mounted volumes

### Added
- **docker-compose.dev.yml**: Development compose file for easy local testing
- **MODERNIZATION_PLAN.md**: Documentation of codebase architecture and future roadmap

### Technical Notes
- Base image: `python:3.12-slim-bookworm`
- Node version for Angular build: 12.22 (required for Angular 4.x compatibility)
- Uses pip for Python dependency management (faster, smaller)
- Multi-architecture support preserved (amd64, arm64, arm/v7)

### Known Issues
- Angular 4.x is outdated but functional; upgrade to modern Angular would require significant work
- Some seedbox providers may have issues with the scanfs binary due to `/tmp` mount restrictions (see GitHub issues #97, #136)

---

## Previous Releases

See the original repository for earlier changelog entries:
https://github.com/ipsingh06/seedsync/releases
