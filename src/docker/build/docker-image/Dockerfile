# SeedSync Docker Image - Complete Multi-Stage Build
# This Dockerfile builds all required components:
# 1. Angular frontend (web UI)
# 2. scanfs binary (file system scanner for remote server)
# 3. Python application

# ==============================================================================
# Stage 1: Build Angular Frontend
# ==============================================================================
FROM node:18-bullseye as angular-builder

# Install Angular CLI globally
WORKDIR /app

# Copy package files first for better caching
COPY src/angular/package*.json ./

# Install dependencies (use --legacy-peer-deps for older Angular compatibility)
RUN npm install --legacy-peer-deps

# Copy Angular source
COPY src/angular/ ./

# Build production bundle
# Note: Angular 4.x uses different build flags than modern Angular
RUN ./node_modules/.bin/ng build --prod --output-path /build/html || \
    ./node_modules/.bin/ng build --configuration production --output-path /build/html

# ==============================================================================
# Stage 2: Build scanfs binary with PyInstaller
# ==============================================================================
FROM python:3.11-slim-bullseye as scanfs-builder

# Install build dependencies
RUN apt-get update && apt-get install -y \
    binutils \
    && rm -rf /var/lib/apt/lists/*

# Install PyInstaller
RUN pip install --no-cache-dir pyinstaller

# Copy Python source for scanfs
COPY src/python/scan_fs.py /src/
COPY src/python/system/ /src/system/

WORKDIR /build

# Build scanfs as a single executable
RUN pyinstaller /src/scan_fs.py \
    --onefile \
    -p /src \
    --distpath /build/dist \
    --workpath /build/work \
    --specpath /build \
    --name scanfs

# ==============================================================================
# Stage 3: Final Runtime Image
# ==============================================================================
FROM python:3.11-slim-bullseye as seedsync_run

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    # LFTP for file transfers
    lftp \
    # SSH client for remote connections
    openssh-client \
    # Archive extraction tools
    p7zip \
    p7zip-full \
    bzip2 \
    unrar-free \
    # User management
    gosu \
    # Misc utilities
    curl \
    && rm -rf /var/lib/apt/lists/*

# Try to set up RAR codec symlink (may not exist in all versions)
RUN ln -sf /usr/lib/p7zip/Codecs/Rar.so /usr/lib/p7zip/Codecs/Rar29.so 2>/dev/null || true

# Set locale
ENV LC_ALL=C.UTF-8
ENV LANG=C.UTF-8

# Install Poetry for dependency management
RUN pip install --no-cache-dir poetry && \
    poetry config virtualenvs.create false

# Create app directory structure
RUN mkdir -p /app/python /app/html /config /downloads

# Copy and install Python dependencies first (for better caching)
COPY src/python/pyproject.toml /app/python/
WORKDIR /app/python

# Regenerate lock file and install dependencies (production only)
RUN poetry lock --no-interaction && \
    poetry install --only main --no-interaction --no-ansi

# Copy Python application source
COPY src/python/ /app/python/

# Copy built Angular frontend from Stage 1
COPY --from=angular-builder /build/html /app/html

# Copy scanfs binary from Stage 2
COPY --from=scanfs-builder /build/dist/scanfs /app/scanfs

# Also copy scanfs Python source as fallback
COPY src/python/scan_fs.py /app/python/
COPY src/python/system/ /app/python/system/

# Copy entrypoint script
COPY src/docker/build/docker-image/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

# Set permissions
RUN chmod +x /app/scanfs || true

# Default environment variables for user/group mapping
ENV PUID=1000
ENV PGID=1000

# Expose web UI port
EXPOSE 8800

# Volumes for configuration and downloads
VOLUME ["/config", "/downloads"]

# Use entrypoint for dynamic user setup
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]

# Run the application
CMD [ \
    "python", \
    "/app/python/seedsync.py", \
    "-c", "/config", \
    "--html", "/app/html", \
    "--scanfs", "/app/scanfs" \
]
