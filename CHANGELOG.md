# Changelog

## [0.12.3] - 2026-02-21

### Fixed
- **SSH output decoding crash** — Fix `UnicodeDecodeError` crash when remote commands (e.g. scanfs) return output containing non-UTF-8 bytes (#76)

---

## [0.12.2] - 2026-02-20

### Fixed
- **Extraction failure handling** — When extraction fails, SeedSync now retries up to 3 times by re-downloading the file. After 3 failures, the file shows a red extracting icon with "Extract failed" text so the user knows intervention is needed. Extract, Delete Local, and Delete Remote actions are all available from this state. (#70, #71, #72, #73)
- **Persist cleanup during staging moves** — Fix persist cleanup incorrectly firing for files with in-flight staging moves, which caused state loss
- **Extraction timing with staging** — Fix extraction starting before the staging move completed
- **LFTP parser crash on long paths** — Fix crash when terminal line wrapping splits LFTP output mid-line (#69)
- **Directory download ETAs** — Fix wildly inaccurate ETAs for directory downloads by using LFTP's real-time transfer sizes and EMA smoothing (#68)
- **scanfs timeout crash** — Fix pexpect resource leak, add retry logic, and enable SSH keepalive (#62)
- **SSH crash on apostrophes in filenames** — Fix shell crash on filenames like "Don't Look Now" (#66)
- **LFTP status parser crash** — Fix crash from interleaved 'jobs -v' command echo in LFTP output (#66)
- **Error handling hardening** — Fix multiple error handling bugs found during code review (#63, #64)
- **Cross-device move crash** — Fix FileExistsError during staging-to-final moves across filesystems

---

## [0.12.1] - 2026-02-14

### Fixed
- **Progress bar glitch during downloads** — Fix race condition where the UI progress bar randomly dropped to 0% mid-download because active file sizes were wiped when the local scanner replaced its file dict (#57)
- **Download state loss after LFTP completion** — Fix download state being lost after LFTP job completion (#55)
- **LFTP pexpect timeout recovery** — Fix lftp pexpect timeout recovery to prevent buffer corruption (#54)

---

## [0.12.0] - 2026-02-13

### Added
- **Staging directory** — Downloads land on a fast staging disk (e.g. NVMe/SSD) first, then automatically move to the final destination after completion. (#36)
- **Dark mode** — Theme toggle with a 3-surface elevation system and semantic color tokens. (#37, #51)
- **Advanced LFTP settings** — Exposes tunable LFTP options in Settings — parallel connections, max total connections (0 = unlimited), and socket buffer size with human-readable suffixes (`8M`, `16M`). (#40, #44)
- **Remote server diagnostics** — Runs diagnostics against the remote seedbox on first connection, surfacing server environment info. (#41)
- **Graceful config upgrades** — New config keys are automatically backfilled with defaults and saved to disk — no manual edits needed after upgrading. (#45)

### Changed
- **Settings layout** — Moved File Discovery below Archive Extraction in the left column. (#48)

### Fixed
- Fix crash when a remote file is removed during sync (#49)
- Preserve DOWNLOADED state after remote file is auto-deleted (#50)
- Fix dashboard status sort: groups ordered logically, oldest-first within each group (#47)

---

## [0.11.3] - 2026-02-09

### Fixed
- **Config persistence hardened against data loss** - Config writes now use atomic file operations (temp file + fsync + rename) to prevent truncation if the process is killed mid-write. Missing config sections fall back to defaults instead of triggering a backup-and-reset cycle. A warning is now logged when config parse failure causes fallback to defaults. (#32)

---

## [0.11.2] - 2026-02-09

### Changed
- **Web access logging** - Moved all HTTP request access logs from INFO to DEBUG level to reduce log noise during normal operation

---

## [0.11.1] - 2026-02-08

### Fixed
- **Config file overwritten on container restart** - Config files from older versions (missing newer properties like `auto_delete_remote` or `net_limit_rate`) no longer cause parse errors that trigger a backup-and-overwrite cycle. Config loading is now resilient to missing keys (uses defaults) and unknown keys/sections (silently ignored), enabling smooth upgrades across versions.

---

## [0.11.0] - 2026-02-08

### Changed
- **Angular 4 → 21** - Complete frontend rewrite with modern Angular 21
  - Standalone components replacing NgModule architecture
  - New Angular control flow syntax (@if, @for, @switch)
  - `inject()` function replacing constructor dependency injection
  - Bootstrap 4 → 5.3 with JS bundle for dropdowns
  - Font Awesome 4 → 7 (Free)
  - RxJS 5 → 7 with modern pipe operators
  - Immutable.js removed — plain TypeScript interfaces
  - Node 12 → 22 for builds
  - `npm install` → `npm ci` for reproducible builds
- **Smaller transfer size** - 156 kB gzipped (down from ~300 kB)
- **Settings page** - Simplified layout with all sections always expanded

### Added
- **Unit tests** - 125 Vitest tests across 14 new spec files covering all models, pipes, and services

### Removed
- **Angular 4 code** - Old frontend code (`src/angular-old/`, `src/angular-v17/`) removed
- **Immutable.js** - Replaced with plain TypeScript interfaces
- **ngx-modialog** - Replaced with inline confirmation patterns
- **angular-webstorage-service** - Replaced with direct localStorage usage
- **css-element-queries** - Replaced with native ResizeObserver

---

## [0.10.6] - 2026-02-07

### Added
- **Auto-delete from remote after download** - New "Delete from remote after download" option in AutoQueue settings. When enabled, files are automatically deleted from the remote seedbox after successful download, preventing the remote server from filling up. Works correctly with auto-extract — extraction runs before deletion when both are enabled. (#25)

---

## [0.10.5] - 2026-02-07

### Fixed
- **Delete remote with tilde (~) path** - Fixed "Delete remote" command not working when the remote path uses `~`. Now properly converts tilde to `$HOME` for shell expansion, matching the fix previously applied to the remote scanner. (#27)
- **Remote shell auto-detection** - SeedSync now automatically detects the available shell on the remote server (`/bin/bash`, `/usr/bin/bash`, `/bin/sh`) instead of failing when `/bin/bash` doesn't exist. Uses SFTP fallback for detection when the login shell is broken. (#18)
- **SSH key auth no longer requires password** - The password field is now optional when SSH key authentication is enabled. Previously required a dummy value. (#21)
- **Config serialization of None values** - Fixed `None` values being written as the string "None" in config files, which caused issues with new optional fields.

### Added
- **Bandwidth/speed limit** - New "Bandwidth Limit" setting in the Connections section allows capping download speed. Supports values like `500K`, `2M`, or raw bytes/sec. Set to `0` or leave empty for unlimited. (#24)
- **SSH key auth documentation** - README and docker-compose now document how to mount SSH keys for password-less authentication.

### Changed
- **Shared remote path utilities** - Extracted tilde-aware path escaping into a shared utility module for reuse across scanner and delete operations.
- **Makefile test target** - Fixed `make test` to install all required Python dependencies.

---

## [0.10.4] - 2026-01-27

### Fixed
- **Remote paths with tilde (~)** - Fixed remote scanner to properly handle paths containing `~`. The tilde is now converted to `$HOME` for shell expansion, allowing users whose SSH and LFTP paths differ (e.g., LFTP locked to home directory). (#14)
- **LftpJobStatusParser crash on empty output** - Fixed parser crashing with "Missing queue header line 1" when lftp `jobs -v` returns empty or unexpected output. Now gracefully returns empty status instead of crashing. (#15)
- **ANSI escape codes in LFTP output** - Fixed parser failing on "First line is not a matching header" when LFTP output contains ANSI escape sequences like bracketed paste mode (`^[[?2004l`). These terminal control codes are now stripped before parsing. (#15)

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
