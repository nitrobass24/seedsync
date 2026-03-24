FROM python:3.12-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends lftp openssh-client \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY src/python/pyproject.toml src/python/uv.lock /tmp/
RUN uv pip install --system --no-cache --strict \
        -r /tmp/pyproject.toml --group test \
    && rm -f /usr/local/bin/uv \
    && rm /tmp/pyproject.toml /tmp/uv.lock
RUN groupadd -r testuser && useradd -r -g testuser -d /app/python -s /sbin/nologin testuser \
    && mkdir -p /app/python && chown testuser:testuser /app/python
WORKDIR /app/python
ENV PYTHONPATH=/app/python
USER testuser
