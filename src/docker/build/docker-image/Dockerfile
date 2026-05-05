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
# Stage 2: Prepare Python runtime (install deps, strip stdlib)
# ==============================================================================
# Pin to the same Alpine minor as the runtime stage (FROM alpine:3.23
# below) so Python + C extensions in site-packages are compiled against
# the same musl ABI they'll run on. The floating "python:3.13-alpine"
# tag could otherwise resolve to a newer Alpine and silently introduce
# a musl mismatch when /usr/local is copied into the runtime stage.
FROM python:3.13-alpine3.23 AS python-deps

COPY src/python/pyproject.toml src/python/uv.lock /tmp/
# `uv pip install -r pyproject.toml` re-resolves dependencies on every build
# and ignores uv.lock — transitive versions can drift between identical
# rebuilds. Export the lockfile to a frozen requirements list first so we
# install the exact versions in uv.lock.
WORKDIR /tmp
RUN --mount=from=ghcr.io/astral-sh/uv:0.11,source=/uv,target=/tmp/uv \
    /tmp/uv export --frozen --no-dev --no-emit-project -o /tmp/requirements.txt \
    && /tmp/uv pip install --system --no-cache --strict \
        -r /tmp/requirements.txt \
    && rm -rf /usr/local/lib/python3.13/site-packages/pip* \
              /usr/local/lib/python3.13/site-packages/setuptools* \
              /usr/local/bin/pip* \
              /usr/local/bin/wheel* \
    && rm -rf /root/.cache /tmp/pyproject.toml /tmp/uv.lock /tmp/requirements.txt \
    && rm -rf \
        /usr/local/lib/python3.13/ensurepip \
        /usr/local/lib/python3.13/idlelib \
        /usr/local/lib/python3.13/turtle.py \
        /usr/local/lib/python3.13/turtledemo \
        /usr/local/lib/python3.13/tkinter \
        /usr/local/lib/python3.13/test \
        /usr/local/lib/python3.13/unittest \
        /usr/local/lib/python3.13/pydoc.py \
        /usr/local/lib/python3.13/pydoc_data \
        /usr/local/lib/python3.13/doctest.py \
        /usr/local/lib/python3.13/lib-dynload/_test*.so \
        /usr/local/lib/python3.13/lib-dynload/_codecs_jp*.so \
        /usr/local/lib/python3.13/lib-dynload/_codecs_kr*.so \
        /usr/local/lib/python3.13/lib-dynload/_codecs_hk*.so \
        /usr/local/lib/python3.13/lib-dynload/_codecs_cn*.so \
        /usr/local/lib/python3.13/lib-dynload/_codecs_tw*.so \
        /usr/local/lib/python3.13/lib-dynload/_codecs_iso*.so \
        /usr/local/lib/python3.13/lib-dynload/_curses*.so \
        /usr/local/lib/python3.13/lib-dynload/_sqlite3*.so \
        /usr/local/lib/python3.13/lib-dynload/_lzma*.so \
        /usr/local/lib/python3.13/lib-dynload/_bz2*.so \
        /usr/local/lib/python3.13/lib-dynload/_dbm*.so \
        /usr/local/lib/python3.13/lib-dynload/_gdbm*.so \
        /usr/local/lib/python3.13/lib-dynload/readline*.so \
        /usr/local/lib/python3.13/lib-dynload/_ctypes_test*.so \
        /usr/local/lib/python3.13/lib-dynload/xx*.so \
        /usr/local/lib/python3.13/lib-dynload/_tkinter*.so \
        /usr/local/lib/python3.13/lib-dynload/_xxtestfuzz*.so \
        /usr/local/lib/python3.13/lib-dynload/_lsprof*.so \
        /usr/local/lib/python3.13/lib-dynload/_interp*.so \
        /usr/local/lib/python3.13/_pyrepl \
        /usr/local/lib/python3.13/_pydecimal.py \
        /usr/local/lib/python3.13/venv \
        /usr/local/lib/python3.13/config-3.13-* \
        /usr/local/include \
    && find /usr/local/lib/python3.13/encodings -name '*.py' \
        ! -name '__init__.py' ! -name 'aliases.py' \
        ! -name 'ascii.py' ! -name 'latin_1.py' \
        ! -name 'utf_8.py' ! -name 'utf_8_sig.py' \
        ! -name 'utf_16*.py' ! -name 'utf_32*.py' \
        ! -name 'unicode_escape.py' ! -name 'raw_unicode_escape.py' \
        ! -name 'charmap.py' ! -name 'idna.py' \
        -delete \
    && find /usr/local/lib/python3.13 -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

# ==============================================================================
# Stage 3: Final Runtime Image
# ==============================================================================
FROM alpine:3.23 AS runtime

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
        libstdc++ \
    && rm -rf /sbin/apk /etc/apk /usr/share/apk /lib/apk /var/cache/apk \
              /lib/libapk.so* /usr/lib/libapk.so* /usr/bin/scanelf \
              /usr/bin/ssh-keyscan /usr/bin/ssh-add /usr/bin/ssh-agent \
              /usr/bin/ssh-pkcs11-helper /usr/bin/ssh-copy-id \
              /usr/bin/findssl.sh /usr/bin/c_rehash \
              /usr/bin/iconv /usr/bin/getconf /usr/bin/ssl_client \
              /etc/ssh/moduli

ENV LC_ALL=C.UTF-8 \
    LANG=C.UTF-8 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Create directory structure
RUN mkdir -p /app/python /app/html /config /downloads /staging

# Copy application source (remove dev config files not needed at runtime)
COPY src/python/ /app/python/
RUN rm -f /app/python/pyproject.toml /app/python/uv.lock

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
