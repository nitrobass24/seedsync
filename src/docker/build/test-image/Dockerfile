FROM python:3.13-alpine

RUN apk add --no-cache lftp openssh-client

COPY src/python/pyproject.toml src/python/uv.lock /tmp/
RUN --mount=from=ghcr.io/astral-sh/uv:0.11,source=/uv,target=/tmp/uv \
    /tmp/uv pip install --system --no-cache --strict \
        -r /tmp/pyproject.toml --group test \
    && rm /tmp/pyproject.toml /tmp/uv.lock

RUN addgroup -S testuser && adduser -S -G testuser -h /app/python -s /sbin/nologin testuser \
    && mkdir -p /app/python && chown testuser:testuser /app/python

WORKDIR /app/python
ENV PYTHONPATH=/app/python
USER testuser
