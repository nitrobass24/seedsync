# SeedSync - Claude Code Instructions

## Project Overview

SeedSync is a Docker-based tool that syncs files from a remote seedbox to a local machine using LFTP.

- **Frontend**: Angular 4 (Bootstrap 4)
- **Backend**: Python 3.12 with Bottle
- **Container**: Multi-arch Docker image (amd64, arm64)
- **Registry**: ghcr.io/nitrobass24/seedsync

## Repository Structure

```
src/
├── angular/          # Angular 4 frontend (current)
├── python/           # Python backend
├── docker/           # Docker build files
└── e2e/              # End-to-end tests
website/              # Docusaurus documentation site
```

## Branches

- **master** - Stable release branch
- **angular-17-upgrade** - Angular 17 migration work (in progress)

## Release Process

When merging a PR or completing significant work, follow this release process:

### 1. Update CHANGELOG.md

Add a new version entry at the top with:
- Version number following semver (major.minor.patch)
- Date in YYYY-MM-DD format
- Sections: Changed, Added, Fixed, Removed, Security (as applicable)

Example:
```markdown
## [0.10.0] - 2026-01-27

### Changed
- **Feature name** - Description of change

### Fixed
- **Bug name** - Description of fix
```

### 2. Update MODERNIZATION_PLAN.md

If the change relates to modernization tasks:
- Update task status (🔄 IN PROGRESS → ✅)
- Update version references
- Update architecture diagram if needed

### 3. Update package.json Version

Update the version in `src/angular/package.json` to match the release version. This is displayed on the About page.

### 4. Create Release

```bash
# Commit all changes
git add CHANGELOG.md MODERNIZATION_PLAN.md src/angular/package.json
git commit -m "Release vX.Y.Z - Brief description"
git push origin master

# Create and push tag
git tag vX.Y.Z
git push origin vX.Y.Z
```

The CI workflow will automatically:
- Build multi-arch Docker images
- Push to ghcr.io
- Create GitHub release with auto-generated notes

### 5. Update GitHub Release Notes

After CI creates the release, update the release notes with detailed changelog:

```bash
gh release edit vX.Y.Z --repo nitrobass24/seedsync --notes "$(cat <<'EOF'
## What's Changed

### Fixed
- **Bug name** - Description of fix (#issue)

### Changed
- **Feature name** - Description of change

### Added
- **New feature** - Description

**Full Changelog**: https://github.com/nitrobass24/seedsync/compare/vPREV...vX.Y.Z
EOF
)"
```

Format should match CHANGELOG.md entries with:
- Section headers: Fixed, Changed, Added, Removed, Security
- Bold feature/bug names
- Issue references where applicable

### 6. Verify Release

- Check GitHub Actions completed successfully
- Verify image is available: `docker pull ghcr.io/nitrobass24/seedsync:X.Y.Z`
- Verify GitHub release notes are formatted correctly

## Version Numbering

- **Major** (X.0.0): Breaking changes, major rewrites
- **Minor** (0.X.0): New features, significant improvements (e.g., Angular upgrade)
- **Patch** (0.0.X): Bug fixes, minor updates

## Key Files

| File | Purpose |
|------|---------|
| `CHANGELOG.md` | Release history and notes |
| `MODERNIZATION_PLAN.md` | Project modernization status |
| `src/docker/build/docker-image/Dockerfile` | Multi-stage Docker build |
| `.github/workflows/ci.yml` | CI/CD pipeline |
| `.github/workflows/docs-pages.yml` | Documentation deployment |
| `website/` | Documentation site (Docusaurus) |

## CI/CD Workflows

### CI (`ci.yml`)

| Trigger | Build & Test | Publish Image | Create Release |
|---------|--------------|---------------|----------------|
| PR to master | ✅ | ❌ | ❌ |
| Push to master | ✅ | ❌ | ❌ |
| Push tag (v*.*.*) | ✅ | ✅ | ✅ |

- **Build & Test**: Builds Docker image and verifies container starts
- **Publish Image**: Pushes multi-arch image to ghcr.io (only on release tags)
- **Create Release**: Creates GitHub release with auto-generated notes (only on release tags)

### Docs (`docs-pages.yml`)

- Triggers only when `website/` directory changes
- Builds and deploys Docusaurus site to GitHub Pages

## Common Tasks

### Building Locally
```bash
make build    # Build Docker image
make run      # Run container
make logs     # View logs
make stop     # Stop container
```

### Testing
```bash
# CI runs on PR to master
# Tests include: Docker build, container startup, web UI accessibility
```

## GitHub Repository

- **Repo**: github.com/nitrobass24/seedsync
- **Docs**: nitrobass24.github.io/seedsync
- **Issues**: Use for bug reports and feature requests
