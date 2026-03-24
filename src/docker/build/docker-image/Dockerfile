# SeedSync Docker Image

# ==============================================================================
# Stage 1: Build Angular Frontend
# ==============================================================================
FROM node:22-alpine AS angular-builder

WORKDIR /app
COPY src/angular/package*.json ./
RUN --mount=type=cache,target=/root/.npm npm ci
COPY src/angular/ ./
RUN npx ng build --configuration=production --output-path /build

# ==============================================================================
# Stage 2: Prepare Python runtime (install deps)
# ==============================================================================
FROM python:3.12-alpine AS python-deps

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY src/python/pyproject.toml src/python/uv.lock /tmp/
RUN uv pip install --system --no-cache --strict \
        -r /tmp/pyproject.toml \
    && rm -f /usr/local/bin/uv \
    && pip uninstall -y pip setuptools \
    && rm -rf /root/.cache /tmp/pyproject.toml /tmp/uv.lock \
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
        /usr/local/lib/python3.12/lib-dynload/_codecs_iso*.so \
        /usr/local/lib/python3.12/lib-dynload/_curses*.so \
        /usr/local/lib/python3.12/lib-dynload/_sqlite3*.so \
        /usr/local/lib/python3.12/lib-dynload/_lzma*.so \
        /usr/local/lib/python3.12/lib-dynload/_bz2*.so \
        /usr/local/lib/python3.12/lib-dynload/_crypt*.so \
        /usr/local/lib/python3.12/lib-dynload/_dbm*.so \
        /usr/local/lib/python3.12/lib-dynload/_gdbm*.so \
        /usr/local/lib/python3.12/lib-dynload/audioop*.so \
        /usr/local/lib/python3.12/lib-dynload/ossaudiodev*.so \
        /usr/local/lib/python3.12/lib-dynload/nis*.so \
        /usr/local/lib/python3.12/lib-dynload/readline*.so \
        /usr/local/lib/python3.12/lib-dynload/_ctypes_test*.so \
    && find /usr/local/lib/python3.12 -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

# ==============================================================================
# Stage 3: Final Runtime Image
# ==============================================================================
FROM alpine:3.21 AS runtime

LABEL maintainer="nitrobass24" \
      description="SeedSync - Seedbox file synchronization tool"

# Copy stripped Python runtime from python-deps stage
COPY --from=python-deps /usr/local/ /usr/local/

# Copy pre-built 7zz binary with RAR codec support (ghcr.io/nitrobass24/docker-7zip)
COPY --from=ghcr.io/nitrobass24/docker-7zip:alpine /7zz /usr/bin/7zz
RUN ln -sf /usr/bin/7zz /usr/bin/7z

# Install runtime dependencies.
# setpriv (from util-linux) is used by entrypoint to drop privileges.
# lftp, openssh-client, ca-certificates are intentionally
# unpinned to receive security updates on each image rebuild.
RUN apk add --no-cache \
        lftp \
        openssh-client \
        ca-certificates \
        setpriv \
        libstdc++

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

# Copy and set up entrypoint
COPY src/docker/build/docker-image/entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/entrypoint.sh

# Runtime configuration
ENV PUID=1000 \
    PGID=1000 \
    UMASK=""

EXPOSE 8800
VOLUME ["/config", "/downloads", "/staging"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD wget -q --spider http://127.0.0.1:${WEB_PORT:-8800}/ || exit 1

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["python", "/app/python/seedsync.py", "-c", "/config", "--html", "/app/html", "--scanfs", "/app/python/scan_fs.py"]
