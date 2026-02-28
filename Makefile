# SeedSync Makefile - Docker Only
# Simplified build system for containerized deployment

.PHONY: build run stop logs clean test

# Default target
all: build

# Build the Docker image
build:
	docker compose -f docker-compose.dev.yml build

# Build without cache
build-fresh:
	docker compose -f docker-compose.dev.yml build --no-cache

# Run the container
run:
	docker compose -f docker-compose.dev.yml up -d

# Stop the container
stop:
	docker compose -f docker-compose.dev.yml down

# View logs
logs:
	docker compose -f docker-compose.dev.yml logs -f

# Clean up
clean:
	docker compose -f docker-compose.dev.yml down -v --rmi local
	rm -rf build/

# Run Python tests (in container with runtime dependencies)
test:
	docker run --rm -v $(PWD)/src/python:/app/python -w /app/python \
		-e PYTHONPATH=/app/python \
		python:3.12-slim-bookworm \
		sh -c "apt-get update -qq && apt-get install -y -qq --no-install-recommends lftp openssh-client >/dev/null 2>&1 && \
		pip install -q -r requirements.txt pytest parameterized testfixtures webtest && \
		pytest tests/unittests -v --tb=short"

# Show image size
size:
	@docker images seedsync-seedsync --format "Image size: {{.Size}}"

# Shell into running container
shell:
	docker exec -it seedsync-dev /bin/bash

# Help
help:
	@echo "SeedSync Docker Build System"
	@echo ""
	@echo "Usage: make [target]"
	@echo ""
	@echo "Targets:"
	@echo "  build       - Build Docker image"
	@echo "  build-fresh - Build Docker image without cache"
	@echo "  run         - Start container"
	@echo "  stop        - Stop container"
	@echo "  logs        - View container logs"
	@echo "  clean       - Remove containers and images"
	@echo "  test        - Run Python unit tests"
	@echo "  size        - Show image size"
	@echo "  shell       - Open shell in running container"
