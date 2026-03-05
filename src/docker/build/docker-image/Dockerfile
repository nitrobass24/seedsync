# SeedSync Docker Image - Optimized Build

# Force AMD64 for scanfs - it runs on remote seedbox servers, not locally
ARG SCANFS_PLATFORM=linux/amd64

# ==============================================================================
# Stage 1: Build Angular Frontend
# ==============================================================================
FROM node:22-bookworm-slim AS angular-builder

WORKDIR /app
COPY src/angular/package*.json ./
RUN npm ci
COPY src/angular/ ./
RUN npx ng build --configuration=production --output-path /build

# ==============================================================================
# Stage 2: Build scanfs binary with PyInstaller
# Use Debian Bullseye for glibc compatibility on remote seedboxes
# Bullseye has glibc 2.31, supporting Linux systems from 2021+
# IMPORTANT: Force AMD64 platform - scanfs runs on remote server, not locally
# ==============================================================================
FROM --platform=$SCANFS_PLATFORM python:3.12-slim-bullseye AS scanfs-builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    binutils \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir pyinstaller tblib

COPY src/python/scan_fs.py /src/
COPY src/python/system/ /src/system/
COPY src/python/common/ /src/common/

WORKDIR /build
RUN pyinstaller /src/scan_fs.py \
    --onefile \
    -p /src \
    --distpath /build/dist \
    --workpath /build/work \
    --specpath /build \
    --name scanfs \
    && strip /build/dist/scanfs 2>/dev/null || true

# ==============================================================================
# Stage 3: Prepare Python runtime (install deps, strip unused stdlib)
# ==============================================================================
FROM python:3.12-slim-bookworm AS python-deps

COPY src/python/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt \
    && pip uninstall -y pip setuptools \
    && rm -rf /root/.cache/pip /tmp/requirements.txt \
    && rm -rf \
        /usr/local/lib/python3.12/ensurepip \
        /usr/local/lib/python3.12/idlelib \
        /usr/local/lib/python3.12/turtle.py \
        /usr/local/lib/python3.12/turtledemo \
        /usr/local/lib/python3.12/tkinter \
        /usr/local/lib/python3.12/test \
        /usr/local/lib/python3.12/unittest \
        /usr/local/lib/python3.12/pydoc.py \
        /usr/local/lib/python3.12/pydoc_data \
        /usr/local/lib/python3.12/doctest.py \
        /usr/local/lib/python3.12/lib2to3 \
        /usr/local/lib/python3.12/distutils \
        /usr/local/lib/python3.12/lib-dynload/_test*.so \
        /usr/local/lib/python3.12/lib-dynload/_codecs_jp*.so \
        /usr/local/lib/python3.12/lib-dynload/_codecs_kr*.so \
        /usr/local/lib/python3.12/lib-dynload/_codecs_hk*.so \
        /usr/local/lib/python3.12/lib-dynload/_codecs_cn*.so \
        /usr/local/lib/python3.12/lib-dynload/_codecs_tw*.so \
        /usr/local/lib/python3.12/lib-dynload/_codecs_iso*.so

# ==============================================================================
# Stage 4: Final Runtime Image
# ==============================================================================
FROM debian:bookworm-slim AS runtime

LABEL maintainer="nitrobass24" \
      description="SeedSync - Seedbox file synchronization tool"

# Copy stripped Python runtime from python-deps stage
COPY --from=python-deps /usr/local/ /usr/local/
RUN ldconfig

# Enable non-free repo for full unrar (unrar-free only supports RAR1-3)
RUN sed -i 's/Components: main/Components: main non-free/' /etc/apt/sources.list.d/debian.sources

# Install runtime dependencies in a single layer
RUN apt-get update && apt-get install -y --no-install-recommends \
    lftp \
    openssh-client \
    7zip \
    unrar=1:6.2.6-1+deb12u1 \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean \
    && ln -sf /usr/bin/7zz /usr/bin/7z

ENV LC_ALL=C.UTF-8 \
    LANG=C.UTF-8 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Create directory structure
RUN mkdir -p /app/python /app/html /config /downloads /staging

# Copy application source
COPY src/python/ /app/python/

# Copy built artifacts from previous stages
COPY --from=angular-builder /build/browser /app/html
COPY --from=scanfs-builder /build/dist/scanfs /app/scanfs

# Copy and set up entrypoint
COPY src/docker/build/docker-image/entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/entrypoint.sh /app/scanfs

# Runtime configuration
ENV PUID=1000 \
    PGID=1000 \
    UMASK=""

EXPOSE 8800
VOLUME ["/config", "/downloads", "/staging"]

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["python", "/app/python/seedsync.py", "-c", "/config", "--html", "/app/html", "--scanfs", "/app/scanfs"]
