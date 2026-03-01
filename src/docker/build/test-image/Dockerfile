FROM python:3.12-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends lftp openssh-client \
    && rm -rf /var/lib/apt/lists/*
COPY src/python/requirements.txt /tmp/
RUN pip install --no-cache-dir -r /tmp/requirements.txt pytest parameterized testfixtures webtest \
    && rm /tmp/requirements.txt
WORKDIR /app/python
ENV PYTHONPATH=/app/python
