# SeedSync Makefile - Docker Only
# Simplified build system for containerized deployment

.PHONY: all build build-fresh run run-backend stop logs clean test test-image size shell help

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

# Run the SeedSync backend locally (no Docker)
# Requires: Python 3.12+, pip install -r src/python/requirements.txt
# Build frontend first: cd src/angular && npx ng build
CONFIG_DIR ?= dev-config
DOWNLOAD_DIR ?= dev-download
HTML_DIR ?= src/angular/dist/seedsync/browser
run-backend:
	@mkdir -p $(CONFIG_DIR) $(DOWNLOAD_DIR)
	@if [ ! -d "$(HTML_DIR)" ]; then \
		echo "Frontend not built. Run: cd src/angular && npm run build"; \
		exit 1; \
	fi
	PYTHONPATH=src/python python src/python/seedsync.py \
		-c $(CONFIG_DIR) \
		--html $(HTML_DIR) \
		--scanfs src/python/scan_fs.py

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

# Build cached test image (first run only)
test-image:
	docker build -t seedsync-test -f src/docker/build/test-image/Dockerfile .

# Run Python tests (in container with runtime dependencies)
test:
	$(MAKE) test-image
	docker run --rm -v $(PWD)/src/python:/app/python seedsync-test \
		pytest tests/unittests -v --tb=short

# Show image size
size:
	@docker images seedsync-seedsync --format "Image size: {{.Size}}"

# Shell into running container
shell:
	docker exec -it seedsync-dev /bin/sh

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
	@echo "  run-backend - Run backend locally (no Docker; needs Angular built)"
	@echo "  stop        - Stop container"
	@echo "  logs        - View container logs"
	@echo "  clean       - Remove containers and images"
	@echo "  test        - Run Python unit tests (in Docker)"
	@echo "  test-image  - Build cached test image"
	@echo "  size        - Show image size"
	@echo "  shell       - Open shell in running container"
