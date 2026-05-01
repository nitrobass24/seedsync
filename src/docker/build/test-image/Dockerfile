FROM python:3.13-alpine

RUN apk add --no-cache lftp openssh-client

COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /usr/local/bin/uv

COPY src/python/pyproject.toml src/python/uv.lock /tmp/
RUN uv pip install --system --no-cache --strict \
        -r /tmp/pyproject.toml --group test \
    && rm -f /usr/local/bin/uv \
    && rm /tmp/pyproject.toml /tmp/uv.lock

RUN addgroup -S testuser && adduser -S -G testuser -h /app/python -s /sbin/nologin testuser \
    && mkdir -p /app/python && chown testuser:testuser /app/python

WORKDIR /app/python
ENV PYTHONPATH=/app/python
USER testuser
