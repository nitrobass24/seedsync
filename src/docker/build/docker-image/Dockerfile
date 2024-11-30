ARG STAGING_REGISTRY=localhost:5000
ARG STAGING_VERSION=latest

FROM python:3.8-slim as seedsync_run_python_env

# Install dependencies (kept unchanged)
RUN sed -i -e's/ main/ main contrib non-free/g' /etc/apt/sources.list && \
    apt-get update && \
    apt-get install -y \
        gcc \
        libssl-dev \
        lftp \
        openssh-client \
        p7zip \
        p7zip-full \
        p7zip-rar \
        bzip2 \
        curl \
        libnss-wrapper \
        libxml2-dev libxslt-dev libffi-dev \
    && apt-get clean
# Fix for patoolib
RUN ln -s /usr/lib/p7zip/Codecs/Rar.so /usr/lib/p7zip/Codecs/Rar29.so

# Install Poetry (kept unchanged)
RUN curl -s https://bootstrap.pypa.io/get-pip.py -o get-pip.py && \
    python get-pip.py --force-reinstall && \
    rm get-pip.py
RUN pip3 install poetry
RUN poetry config virtualenvs.create false

ENV LC_ALL=C.UTF-8
ENV LANG=C.UTF-8

# Python dependencies
RUN mkdir -p /app
COPY src/python/pyproject.toml /app/python/
COPY src/python/poetry.lock /app/python/
RUN cd /app/python && poetry install --no-dev

# Application setup (unchanged)
COPY src/python /app/python

# Add entrypoint script
COPY /src/docker/build/docker-image/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

# Default environment variables
ENV PUID=1000
ENV PGID=1000

# Use entrypoint script for dynamic user setup
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]

# App command
CMD [ \
    "python", \
    "/app/python/seedsync.py", \
    "-c", "/config", \
    "--html", "/app/html", \
    "--scanfs", "/app/scanfs" \
]

EXPOSE 8800
