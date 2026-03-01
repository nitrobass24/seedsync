FROM python:3.12-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends lftp openssh-client \
    && rm -rf /var/lib/apt/lists/*
COPY src/python/requirements.txt /tmp/
RUN pip install --no-cache-dir -r /tmp/requirements.txt pytest parameterized testfixtures webtest \
    && rm /tmp/requirements.txt
RUN groupadd -r testuser && useradd -r -g testuser -d /app/python -s /sbin/nologin testuser \
    && mkdir -p /app/python && chown testuser:testuser /app/python
WORKDIR /app/python
ENV PYTHONPATH=/app/python
USER testuser
