# Changelog

## [0.15.0] - 2026-04-08

### Added

- **Virtual scrolling for large file lists** — Improves performance when browsing directories with many files (#335)
- **Size sorting in file list** — New sort option to order files by size (#334)
- **Log level dropdown** — Replaced debug toggle with a full log level selector (trace/debug/info/warning/error) (#332)

### Fixed

- **Bulk delete crash** — Fixed unbounded process spawning that caused crashes during bulk delete; scoped concurrency cap to delete operations and added move retry on failure (#338, #341)
- **Infinite busy-loop in command process throttling** — Fixed CPU spin in the controller process throttle logic

### Changed

- **Dependency updates** — Angular group bump (9 packages), hono 4.12.7→4.12.12, @hono/node-server bump, jsdom 29.0.1→29.0.2, vitest 4.1.2→4.1.3, lodash 4.17.23→4.18.1, all deps to latest compatible versions (#326, #333, #336, #337, #343, #344, #345)
- **Documentation** — Moved recommended hard-link workflow from FAQ to a dedicated Usage section with getting-started link on the homepage; fixed hyphenation of "hard-linked" (#340)

## [0.14.4] - 2026-03-30

### Changed

- **Pyright strict mode** — Upgraded Pyright type checking from basic to strict mode across the entire Python codebase; added type stubs for bottle, pexpect, and tblib (#291, #316)

### Fixed

- **Extraction-move validation race** — Extraction completion no longer spawns a staging move while validation is still running; the move is deferred to the validation completion path (#316)
- **Directory size preservation in exclude filter** — `_filter_children` now preserves scanner-reported directory sizes instead of recomputing from filtered children, preventing `remote_size` divergence (#316)

### Security

- **Website dependency bumps** — Fixed 4 vulnerabilities in website transitive dependencies: brace-expansion, path-to-regexp, picomatch, minimatch (#324)
- **Pygments 2.20.0** — Bumped pygments to fix ReDoS vulnerability GHSA-5239-wwwm-4pmq (#325)

## [0.14.3] - 2026-03-25

### Added

- **Configurable remote Python path** — New "Remote Python Path" setting lets users specify a custom Python binary on the remote server (e.g. `~/python3/bin/python3`), solving issues on seedboxes where `python3` is not on the default PATH (#314, #315)
- **Startup config validation** — SeedSync now validates required LFTP config fields on startup and shows clear error messages when `remote_address`, `remote_username`, `remote_path`, or `local_path` are missing (#310, #313)

### Fixed

- **scan_fs.py Python 3.5 compatibility** — Remote scanner script now works on servers with Python 3.5+ by using `typing.List`/`Optional` instead of modern type syntax (#314, #315)
- **Sshcp.copy() user@host format** — Fixed `scp` command construction to use the shared `_remote_address()` helper, matching the pattern used by `shell()` (#312)
- **Pre-existing code quality bugs** — Fixed extraction retry counter, NotImplementedError base class, and process cleanup issues found during Ruff review (#289, #312)

### Changed

- **uv for Python dependencies** — Replaced pip + requirements.txt with uv and PEP 621 dependency groups; pinned uv versions in CI and Docker (#286, #311)

## [0.14.2] - 2026-03-23

### Added

- **Playwright E2E test suite** — Replaced legacy Protractor tests with Playwright; 55 tests covering all pages, navigation, themes, and settings (#250)
- **Pyright type checking enforced in CI** — Completed Pyright phases 3 & 4, fixing 166 type errors to reach 0 errors in basic mode; Pyright check is now required in CI (#249)

### Fixed

- **ModelFile nullable size fields** — `local_size` and `remote_size` are now correctly typed as `number | null` to match the Python backend JSON contract

### Security

- **Reject control characters in filenames** — Decoded filenames containing control characters are now rejected to prevent corrupted file entries and queue command injection (#300)
- **Redact sensitive credentials from API** — SSH password and key passphrase are no longer exposed in API responses; set handler rejects the redacted sentinel value (#257)

### Changed

- **Angular dependency updates** — Bumped Angular group to latest, jsdom to 29.0.1 (#307, #308)
- **CI: actions/setup-python v6** — Bumped setup-python action from v5 to v6 (#306)

### Removed

- **Legacy Docker E2E infrastructure** — Cleaned up Protractor Docker Compose files, test images, and fixture data

## [0.14.1] - 2026-03-18

### Fixed

- **Parser crash on long filenames** — Chunk progress lines that wrap across PTY boundaries no longer crash the controller; unrecognized lines inside a job context are skipped with a warning (#290, #293)
- **False download completion on parser error** — Parser failures no longer trigger false "download completed" signals that left files stuck in staging at partial progress (#296)
- **Progress tracking with .lftp temp naming** — ActiveScanner now recognizes `.lftp`-suffixed temp files in staging, fixing 0% progress display for single-file downloads when temp naming is enabled (#298)

### Changed

- **PEP 621 pyproject.toml** — Consolidated Python dependencies from Poetry format to PEP 621 with proper dependency groups (runtime, test, dev); removed dead dependencies (#287)
- **Ruff linting and formatting** — Added Ruff as Python linter/formatter with CI enforcement; applied auto-fixes across 99 files (#288)
- **Pyright type checking** — Added Pyright in basic mode with CI reporting; fixed 91 type errors across 26 modules (#292, #295)
- **Python unit tests in CI** — Python tests now run in CI alongside Angular tests (#287)
- **Angular dependency updates** — Bumped Angular group to 21.2.4, vitest to 4.1.0, jsdom to 29.0.0 (#282, #283, #284)

## [0.14.0] - 2026-03-14

### Added

- **Inline transfer verification** — LFTP's `xfer:verify` checksums files during download, catching corruption in real-time; enabled by default (#242)
- **Post-download integrity checking** — Optional validation step that compares local and remote checksums via SSH after download, with per-file Validate button and Validated/Corrupt status indicators (#125, #276)
- **File list pair label column** — File list shows which path pair each file belongs to (#156)
- **Accessibility** — All file action buttons converted to native `<button>` elements (#241)
- **Comprehensive test coverage** — 287 unit tests across Angular (Vitest) and Python (pytest) (#225)

### Changed

- **Alpine-only Docker image** — Removed Debian variant; all images are now Alpine-based (~45 MB), multi-arch (amd64/arm64) (#231, #244)
- **Multiprocessing fork to spawn** — Fixes Python 3.12 deprecation warnings (#228)
- **Verbose logging in web UI** — Verbose LFTP logging setting is now exposed in the Settings page under Logging (#266)
- **CI deduplication** — Eliminated redundant amd64 Docker build; publish triggers now build, test, and push in a single job (#274)

### Fixed

- **Stopped download delete stuck** — Deleting local files for a stopped download no longer leaves the UI spinner and ActiveScanner polling forever (#271, #272, #273)
- **File descriptor leak on restart** — Multiprocessing Event/Queue references are now released in `close_queues()` to prevent FD exhaustion across restarts (#265)
- **Model rebuild log noise** — Temporary model objects used during diff computation no longer emit "Adding file" log messages on every controller loop iteration (#267)

## [0.13.5] - 2026-03-13

### Fixed

- **Exclude patterns use wrong LFTP flag** — Changed `--exclude` (regex) to `--exclude-glob` (glob) so patterns like `*.nfo` work correctly instead of being silently misinterpreted as regex (#271)

### Changed

- **LFTP queue command logging** — Log LFTP queue commands at INFO level (previously DEBUG) for easier troubleshooting without enabling verbose mode
- **CI workflow_dispatch support** — Allow manual Docker image publishing via GitHub Actions workflow_dispatch trigger

## [0.13.4] - 2026-03-12

### Fixed

- **Exclude patterns not passed to LFTP** — Exclude patterns were only filtering the UI display model but were never passed to LFTP's `mirror` command, causing all files to be downloaded regardless of configured exclusions (#259)
- **Parser crash on Unraid PTY line-wrap fragments** — Unraid's Docker PTY handling wraps long LFTP progress lines, producing tail fragments like `/s eta:25m [Receiving data]` that crashed the parser and stopped the container (#260)
- **Parser error threshold too aggressive** — Bumped consecutive status error threshold from 2 to 10 so persistent parse issues don't crash the app within seconds
- **PTY width override on Unraid** — Set `COLUMNS=10000` in pexpect spawn environment as belt-and-suspenders alongside `setwinsize` to prevent Unraid from overriding PTY dimensions

## [0.13.3] - 2026-03-12

### Fixed

- **lftp parser crash on orphan progress lines** — Parser no longer crashes when lftp emits bare progress lines like `3.0K/s eta:3m [Receiving data]` outside a job context, which caused the Docker container to stop (#253)

## [0.13.2] - 2026-03-10

### Fixed

- **Recursive exclude filtering** — Exclude patterns now filter through nested children, not just top-level files (#158, #217)
- **Persist key separator** — Replace colon separator with non-printable unit separator (`\x1f`) to avoid conflicts with filenames containing colons; includes backward-compatible migration of existing persist data (#221)
- **Default-pair filenames with colons** — Fix `_sync_persist_to_all_builders` incorrectly excluding filenames like `Show 01:02.mkv` from default pair contexts (#221)
- **Python version check placement** — Move version guard above project imports so the friendly error message displays on older Python versions (#224)
- **Angular memory leaks** — Fix 6 leaked subscriptions in header and sidebar components (#220)

### Added

- **LZIP archive detection** — `is_archive()` now recognizes LZIP format with 5-byte magic signature (#218)
- **Plain gzip/bzip2 extraction** — Support extraction of standalone `.gz` and `.bz2` files (not just `.tar.gz`/`.tar.bz2`) (#219)
- **Webhook graceful shutdown** — `WebhookNotifier.shutdown()` drains in-flight webhook threads with a configurable timeout, preventing lost notifications on exit (#222)
- **67 new tests** — Unit tests for extraction, exclude patterns, webhook drain, persist migration, file-list component, bulk-action-bar component, and path pairs CRUD handler (#219, #226, #227)

### Changed

- **Angular subscription cleanup** — Migrate 6 components from manual `Subscription[]`/`ngOnDestroy` to `takeUntilDestroyed` pattern (#220)
- **Shared form template** — Extract duplicated path-pairs form fields into `ng-template` with `*ngTemplateOutlet` (#223)
- **Defensive copy for path pairs** — `PathPairsConfig.get_pair()` returns deep copies to prevent external mutation of internal state (#221)
- **Dependency cleanup** — Move `timeout-decorator` from runtime to test-only; remove unused localization strings (#224)
- **Angular dependency updates** — Bump Angular group dependencies (#213)

## [0.13.1] - 2026-03-09

### Fixed

- **RAR archive extraction** — Use source-built 7-Zip 26.00 with RAR codec support; distro packages strip the proprietary RAR codec (#204, #210, #212)
- **Extract/move pipeline stall** — Fix `pending_completion` never clearing for files in EXTRACTED or EXTRACT_FAILED state when staging is enabled (#208)
- **Auto-delete with path pairs** — Fix auto-queue commands missing `pair_id` for path pair configurations (#205)
- **Pre-extraction false negatives** — Remove redundant archive verification that rejected valid archives (#207)

### Changed

- **Pre-built 7-Zip Docker image** — Extract 7zz binary from `ghcr.io/nitrobass24/docker-7zip` instead of compiling from source during CI (#212)

### Security

- **CodeQL alerts resolved** — Fix code scanning alerts identified by GitHub CodeQL (#197)

## [0.13.0] - 2026-03-06

### Added

- **Multiple path pairs** — Configure multiple remote/local directory pairs, each with independent LFTP and scanner instances. Replaces the single remote/local path with a flexible pair-based model (#122, #149, #155, #161)
- **Path pairs settings UI** — Full CRUD interface for managing path pairs in Settings, with per-pair enable/disable and auto-queue toggles (#160, #162, #163)
- **Exclude patterns** — Filter out unwanted remote files using glob patterns (e.g. `*.nfo`, `Sample/`), configurable per path pair (#26, #146)
- **Multi-select and bulk operations** — Select multiple files and apply queue/stop/delete actions in bulk (#123)
- **Webhook notifications** — HTTP POST notifications on file download/extract events (#128)
- **Historical log query** — `/server/logs` endpoint with search, filter, and level controls; accessible from the UI (#124)
- **Structured JSON logging** — Optional JSON log format for log aggregation tools (#127)
- **Alpine Docker image** — Lightweight Alpine variant alongside the Debian image, published as `*-alpine` tags (#164)
- **Docker HEALTHCHECK** — Built-in health check for container orchestrators with `WEB_PORT` env var support (#164, #180)

### Changed

- **Python scanfs replaces PyInstaller binary** — Remote scanner is now a plain Python script, eliminating glibc compatibility issues with seedbox servers (#80, #148)
- **JSON serialization for scanfs** — Scanner uses JSON instead of legacy serialization for safer, more debuggable output (#129)
- **Consolidated extraction to 7z** — All archive extraction (zip, rar, 7z, tar, gz, bz2, xz) now uses the single `7z` binary, removing the `unrar` dependency and reducing image size (#178)
- **Dual-image CI pipeline** — CI builds and tests both Debian and Alpine variants on every push, with parallel arm64 builds on develop (#164, #175, #176)
- **Startup log improvements** — Path pairs dumped at startup for debugging; model logs show short pair ID instead of full GUID (#165)

### Fixed

- **Per-pair extraction pipeline** — Extraction now uses the correct path pair's filesystem paths instead of always using the first pair (#167, #173)
- **Per-pair staging subdirectories** — Each path pair gets its own staging subdirectory, preventing filename collisions (#168, #173)
- **Unique pair name enforcement** — Duplicate pair names are now rejected on create/update (#169, #172)
- **Graceful pause when all pairs disabled** — Controller idles cleanly and the UI shows an informational banner instead of falling back to legacy behavior (#170, #174)
- **Spurious staging moves on restart** — Files already moved to their final location are no longer re-queued for move on container restart (#177, #179)
- **Healthcheck IPv6 resolution** — Healthcheck uses `127.0.0.1` explicitly instead of `localhost`, which resolved to IPv6 `::1` on Alpine (#180)

### Removed

- **paste WSGI server** — Replaced with Bottle's built-in multithreaded server (#140)
- **patool dependency** — Archive extraction consolidated to 7z (#141, #145, #178)
- **unrar dependency** — Removed in favor of 7z which handles all RAR formats (#178)

---

## [0.12.10] - 2026-03-04

### Added

- **API key authentication** — Optional API key protects all `/server/*` endpoints. Set via Settings > Web > API Key. SSE stream accepts key as query parameter; config GET is exempt for frontend bootstrapping (#130)
- **Security response headers** — Content-Security-Policy, X-Content-Type-Options, X-Frame-Options, Referrer-Policy on all responses (#130)
- **CSRF protection** — Origin/Referer validation on state-changing requests with loopback exemption (#130)
- **Rate limiting** — Per-IP sliding window (120 requests/60s) on all endpoints except SSE stream (#130)
- **Config file backup** — Automatic backup before each config save, keeps last 10 with ISO timestamps (#130)
- **Scanner home directory fallback** — Automatically retries scanner installation to `~/` when `/tmp` is restricted on the remote server (#114)
- **Server Script Path documentation** — README troubleshooting, configuration docs, and FAQ entries for common scanner installation issues (#114, #115)

### Fixed

- **CSP blocks inline scripts** — Moved inline theme detection to external `theme-init.js` and disabled Beasties critical CSS inlining to comply with `script-src 'self'` (#134)
- **Settings page not loading** — Eagerly initialize ConfigService and AutoQueueService in APP_INITIALIZER to ensure config loads on first connection (#136)
- **SSE API key state mismatch** — Clear SSE stream API key at all config-reset paths (disconnect, parse failure, fetch failure) to prevent stale auth (#136)
- **SFTP permission preservation overrides umask** — Disabled lftp `sftp:set-permissions` so local umask applies to downloaded files (#115)
- **Scanner path traversal in delete endpoints** — Validate filenames and check path containment before local/remote delete operations (#130)
- **Zip-slip archive extraction** — Pre-validate zip/tar members for symlinks and path traversal; post-extraction check for rar/7z formats (#130)
- **Remote scanner shell-quoting** — Properly escape remote paths in md5sum and execution commands (#114)

### Security

- Path traversal protection on all controller command endpoints (queue, stop, extract, delete) (#130)
- Constant-time API key comparison with `secrets.compare_digest` (#130)
- Null byte rejection in filename validation (#130)

---

## [0.12.9] - 2026-03-02

### Changed

- **UMASK diagnostic logging** — Log the applied umask and previous value at startup to help diagnose permission issues (#109)

---

## [0.12.8] - 2026-03-02

### Fixed

- **Staging path crash on Unraid** — Container failed to start with `PermissionError: /staging` when staging was enabled but `/staging` was not a writable volume mount. The `/staging` directory is now created and chowned at container startup, declared as a Docker VOLUME, and exposed in the Unraid template as an optional advanced path (#109)
- **Entrypoint permission errors hidden** — `chown` failures for `/downloads` and `/staging` were silently swallowed. Errors now surface on stderr. A writability check (run as the app user) verifies `/downloads` on every startup and `/staging` when it is externally mounted, exiting with a clear error message instead of crashing deep in the application

---

## [0.12.7] - 2026-03-02

### Fixed

- **UMASK not applied to downloaded files** — Shell umask was not reliably inherited by lftp through the setpriv exec chain. Now applied directly via `os.umask()` in Python at startup, ensuring correct file permissions for all downloaded files (#109)

---

## [0.12.6] - 2026-02-28

### Added

- **Unraid installation docs** — Added Unraid Community Applications install instructions to README and Docusaurus docs site (#79)

### Changed

- **Docker build optimization** — Added `.dockerignore`, reduced build context, shared build artifacts between CI jobs
- **CI improvements** — Test caching, always-rebuild test image, non-root test user
- **Poll interval tuning** — Reduced unnecessary polling in logger and web app

---

## [0.12.5] - 2026-02-28

### Fixed

- **Delete Remote directory hang** — Fixed infinite spinner when deleting a remote directory (#92)
- **SSH password exposed in debug logs** — Mask `remote_password` in debug config dump output (#97)

### Added

- **UMASK environment variable** — Control downloaded file permissions via `UMASK` env var (e.g. `002` for 775/664)
- **Angular unit tests in CI** — 132 Vitest unit tests now run on every CI build (#93)

### Changed

- **Parallel multi-arch Docker builds** — amd64 and arm64 images now build in parallel and merge into a single multi-arch manifest, reducing total release build time (#93)
- **Skip Angular build on arm64** — Build Angular natively and inject into arm64 Docker build via `build-contexts`, cutting arm64 CI from ~4min to ~1min
- **Angular packages** — Bumped from 21.1.x to 21.2.0

### Security

- **Dependabot alerts** — Dismissed 4 dev-only alerts; remaining 5 are unfixable Docusaurus transitive deps (#96)

---

## [0.12.4] - 2026-02-28

### Fixed

- **RAR5 extraction failure** — Replace `unrar-free` (RAR1-3 only) with RARLAB's full `unrar` (v6.21) which supports all RAR formats including RAR5. Modern archives use RAR5, causing silent extraction failures and a download-extract-fail-delete loop (#84)
- **Incomplete directory stuck in DOWNLOADED** — Fix persist authority overriding children BFS check when extra local files inflate `local_size >= remote_size`, preventing re-download of missing remote children (#83)
- **LFTP chunk parser crash** — Fix crash on rangeless `\chunk` lines (e.g. `\chunk 5077`) emitted by LFTP during parallel downloads
- **Zombie app after controller crash** — Fix main loop swallowing controller exceptions, causing the app to run indefinitely without functioning instead of cleanly exiting for Docker restart
- **Extract retry loop not stopping** — Fix retry counter being reset on every re-download cycle, preventing files from reaching EXTRACT_FAILED state after 3 attempts
- **Delete Local fails for staged files** — Check staging path before local_path in DELETE_LOCAL so files still in staging can be deleted
- **Late-binding closure in DELETE_LOCAL** — Bind `delete_path` as default argument so each callback captures the correct path when multiple deletes are batched
- **Manual extract silently failing** — Extract dispatch errors (e.g. "no archives found") were silently swallowed, leaving the file in DOWNLOADED state with no UI feedback. Now reported as failures so the file reaches EXTRACT_FAILED state
- **Extract fails after staging move** — When staging is enabled and files are moved to the final local path before extraction runs, ExtractDispatch only checked the staging path. Now falls back to local_path so archives are found in either location

---

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
