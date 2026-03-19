# SeedSync Makefile - Docker Only
# Simplified build system for containerized deployment

.PHONY: all build build-fresh run stop logs clean test test-image test-e2e test-e2e-headed test-e2e-report size shell help

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

# Build cached test image (first run only)
test-image:
	docker build -t seedsync-test -f src/docker/build/test-image/Dockerfile .

# Run Python tests (in container with runtime dependencies)
test:
	$(MAKE) test-image
	docker run --rm -v $(PWD)/src/python:/app/python seedsync-test \
		pytest tests/unittests -v --tb=short

# Run Playwright E2E tests (headless, requires running container on port 8800)
test-e2e:
	cd src/e2e-playwright && npx playwright test

# Run Playwright E2E tests (headed, for debugging)
test-e2e-headed:
	cd src/e2e-playwright && npx playwright test --headed

# Show Playwright HTML report
test-e2e-report:
	cd src/e2e-playwright && npx playwright show-report

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
	@echo "  stop        - Stop container"
	@echo "  logs        - View container logs"
	@echo "  clean       - Remove containers and images"
	@echo "  test        - Run Python unit tests (in Docker)"
	@echo "  test-image  - Build cached test image"
	@echo "  test-e2e    - Run Playwright E2E tests (headless)"
	@echo "  test-e2e-headed - Run E2E tests with browser visible"
	@echo "  test-e2e-report - Show Playwright HTML report"
	@echo "  size        - Show image size"
	@echo "  shell       - Open shell in running container"
