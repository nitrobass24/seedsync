# SeedSync Docker Image - Alpine Build

# ==============================================================================
# Stage 1: Build Angular Frontend
# ==============================================================================
FROM node:22-alpine AS angular-builder

WORKDIR /app
COPY src/angular/package*.json ./
RUN npm ci
COPY src/angular/ ./
RUN npx ng build --configuration=production --output-path /build

# ==============================================================================
# Stage 2: Prepare Python runtime (install deps)
# ==============================================================================
FROM python:3.12-alpine AS python-deps

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
# Stage 3: Build unrar from source (not packaged in Alpine)
# ==============================================================================
FROM alpine:3.21 AS unrar-builder

RUN apk add --no-cache build-base curl \
    && curl -fsSL https://www.rarlab.com/rar/unrarsrc-7.1.6.tar.gz | tar xz \
    && cd unrar \
    && make -f makefile -j$(nproc) \
    && install -m 755 unrar /usr/local/bin/unrar

# ==============================================================================
# Stage 4: Final Runtime Image
# ==============================================================================
FROM alpine:3.21 AS runtime

LABEL maintainer="nitrobass24" \
      description="SeedSync - Seedbox file synchronization tool"

# Copy stripped Python runtime from python-deps stage
COPY --from=python-deps /usr/local/ /usr/local/

# Copy unrar binary from builder
COPY --from=unrar-builder /usr/local/bin/unrar /usr/local/bin/unrar

# Install runtime dependencies.
# shadow provides useradd/groupadd/usermod for entrypoint user management.
# util-linux provides setpriv for dropping privileges.
# lftp, openssh-client, 7zip, ca-certificates are intentionally
# unpinned to receive security updates on each image rebuild.
RUN apk add --no-cache \
        lftp \
        openssh-client \
        7zip \
        ca-certificates \
        shadow \
        util-linux \
        libstdc++ \
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

# Copy and set up entrypoint
COPY src/docker/build/docker-image/entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/entrypoint.sh

# Runtime configuration
ENV PUID=1000 \
    PGID=1000 \
    UMASK=""

EXPOSE 8800
VOLUME ["/config", "/downloads", "/staging"]

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["python", "/app/python/seedsync.py", "-c", "/config", "--html", "/app/html", "--scanfs", "/app/python/scan_fs.py"]
