# Developer Guide

This guide covers development setup for SeedSync.

## Prerequisites

- **Docker Desktop** - Required for building and testing
- **Git** - For version control

That's it! All builds happen inside Docker containers.

## Quick Start

```bash
# Clone the repository
git clone https://github.com/nitrobass24/seedsync.git
cd seedsync

# Build the Docker image
make build

# Run the container
make run

# View logs
make logs

# Access web UI at http://localhost:8800
```

## Project Structure

```
seedsync/
├── src/
│   ├── python/           # Python backend (Bottle.py web framework)
│   │   ├── seedsync.py   # Main entry point
│   │   ├── controller/   # Sync logic
│   │   ├── lftp/         # LFTP integration
│   │   ├── web/          # REST API handlers
│   │   └── requirements.txt
│   ├── angular/          # Angular 4.x frontend
│   │   ├── src/app/      # Application components
│   │   └── package.json
│   └── docker/
│       └── build/docker-image/
│           ├── Dockerfile
│           └── entrypoint.sh
├── docker-compose.dev.yml
├── Makefile
└── README.md
```

## Make Commands

| Command | Description |
|---------|-------------|
| `make build` | Build Docker image |
| `make build-fresh` | Build without cache |
| `make run` | Start container |
| `make stop` | Stop container |
| `make logs` | View container logs |
| `make shell` | Shell into running container |
| `make test` | Run Python unit tests |
| `make size` | Show image size |
| `make clean` | Remove containers and images |

## Development Workflow

### Making Changes

1. **Python backend changes**: Edit files in `src/python/`
2. **Frontend changes**: Edit files in `src/angular/`
3. **Rebuild**: Run `make build`
4. **Test**: Run `make run` and check http://localhost:8800

### Running Tests

```bash
# Run Python unit tests
make test

# Or run tests manually in container
docker run --rm -v $(pwd)/src/python:/app -w /app \
  python:3.12-slim-bookworm \
  sh -c "pip install pytest && pytest tests/unittests -v"
```

### Live-server SSH tests

A few suites — `tests/unittests/test_lftp/test_lftp.py`,
`tests/unittests/test_ssh/test_sshcp.py`, and the
`tests/integration/test_controller` / `tests/integration/test_lftp` suites —
drive a real lftp/SSH transfer against a `seedsynctest` SSH account on
`localhost`. They are **skipped by default**, including under `make test` and in
CI (neither provisions that account), so the fully-mocked lftp/ssh/scanner tests
in the same packages still run.

To run the live suites, set up the `seedsynctest` account (an SSH user on
`localhost` with password `seedsyncpass` and key-based login enabled), then opt
in with the `SEEDSYNC_LIVE_SSH_TESTS` environment variable. Run from the
`src/python` directory (the same working directory and `PYTHONPATH` CI uses):

```bash
cd src/python
SEEDSYNC_LIVE_SSH_TESTS=1 PYTHONPATH=. pytest tests/unittests/test_ssh/test_sshcp.py -v
```

### Debugging

```bash
# View live logs
make logs

# Shell into running container
make shell

# Check container status
docker ps

# Inspect container
docker inspect seedsync-dev
```

## Docker Image Details

### Multi-Stage Build

The Dockerfile uses three stages:

1. **angular-builder**: Builds the Angular frontend with Node 12
2. **scanfs-builder**: Builds the scanfs binary with PyInstaller
3. **runtime**: Final slim Python 3.12 image with all components

### Image Size

Target: ~240MB (optimized from original 439MB)

Key optimizations:
- Using `python:3.12-slim-bookworm` base
- pip instead of Poetry
- Minimal runtime dependencies
- No documentation tools in runtime

## Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│                  Docker Container                    │
│                                                     │
│  ┌─────────────┐    ┌─────────────┐               │
│  │   Bottle    │◄───│   Angular   │               │
│  │  (REST API) │    │  (Web UI)   │               │
│  └──────┬──────┘    └─────────────┘               │
│         │                                          │
│  ┌──────▼──────┐    ┌─────────────┐               │
│  │ Controller  │───►│    LFTP     │──► Remote     │
│  │ (Sync Logic)│    │  (Transfer) │    Server     │
│  └─────────────┘    └─────────────┘               │
│                                                     │
│  Volumes: /config, /downloads                       │
└─────────────────────────────────────────────────────┘
```

## Release Process

Releases are automated via GitHub Actions.

### Creating a Release

1. Update version in `src/angular/package.json`
2. Update `CHANGELOG.md`
3. Commit changes
4. Tag the commit:
   ```bash
   git tag v0.9.1
   git push origin v0.9.1
   ```
5. GitHub Actions will automatically:
   - Build and test the image
   - Push to GitHub Container Registry
   - Create a GitHub Release

### Manual Docker Push

If needed, you can manually push:

```bash
# Build
docker build -t ghcr.io/nitrobass24/seedsync:latest \
  -f src/docker/build/docker-image/Dockerfile .

# Login to GHCR
echo $GITHUB_TOKEN | docker login ghcr.io -u USERNAME --password-stdin

# Push
docker push ghcr.io/nitrobass24/seedsync:latest
```

## Troubleshooting

### Build Fails

```bash
# Clean and rebuild
make clean
make build-fresh
```

### Container Won't Start

```bash
# Check logs
docker logs seedsync-dev

# Common issues:
# - Port 8800 already in use
# - Volume permission issues (check PUID/PGID)
```

### Permission Issues

Ensure PUID/PGID match your user:

```bash
id  # Shows your UID and GID
```

Update `docker-compose.dev.yml` with your values.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests: `make test`
5. Submit a pull request

## Tech Stack

| Component | Technology | Version |
|-----------|------------|---------|
| Backend | Python + Bottle | 3.12 |
| Frontend | Angular | 4.x |
| Transfer | LFTP | Latest |
| Container | Docker | 20+ |
| CI/CD | GitHub Actions | - |
