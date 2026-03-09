# SeedSync Docker Image - Debian Build

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
# Stage 2: Prepare Python runtime (install deps, strip unused stdlib)
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
# Stage 3: Download official 7-Zip binary (includes RAR codec)
# ==============================================================================
# The Debian/Alpine 7zip packages strip the proprietary RAR codec.
# The official 7zz binary from 7-zip.org includes full RAR support.
FROM debian:bookworm-slim AS 7zip-downloader

ARG TARGETARCH
RUN apt-get update && apt-get install -y --no-install-recommends wget xz-utils \
    && rm -rf /var/lib/apt/lists/* \
    && case "${TARGETARCH}" in \
         amd64) ARCH="x64" ;; \
         arm64) ARCH="arm64" ;; \
         *) echo "Unsupported arch: ${TARGETARCH}" && exit 1 ;; \
       esac \
    && wget -qO /tmp/7z.tar.xz "https://7-zip.org/a/7z2408-linux-${ARCH}.tar.xz" \
    && mkdir /tmp/7z && tar -xJf /tmp/7z.tar.xz -C /tmp/7z

# ==============================================================================
# Stage 4: Final Runtime Image
# ==============================================================================
FROM debian:bookworm-slim AS runtime

LABEL maintainer="nitrobass24" \
      description="SeedSync - Seedbox file synchronization tool"

# Copy stripped Python runtime from python-deps stage
COPY --from=python-deps /usr/local/ /usr/local/

# Copy official 7zz binary (with RAR codec support)
COPY --from=7zip-downloader /tmp/7z/7zz /usr/bin/7zz
RUN ln -sf /usr/bin/7zz /usr/bin/7z

# Install runtime deps in a single layer.
# lftp, openssh-client, ca-certificates are intentionally unpinned
# to receive security updates on each image rebuild.
RUN ldconfig \
    && apt-get update && apt-get install -y --no-install-recommends \
        lftp \
        openssh-client \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

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
  CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:{}/'.format(os.environ.get('WEB_PORT','8800')))" || exit 1

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["python", "/app/python/seedsync.py", "-c", "/config", "--html", "/app/html", "--scanfs", "/app/python/scan_fs.py"]
