# SeedSync Makefile - Docker Only
# Simplified build system for containerized deployment

.PHONY: all build build-fresh run stop logs clean test test-image test-e2e-docker size shell help

all: build

build: ## Build the Docker image
	docker compose -f docker-compose.dev.yml build

build-fresh: ## Build without cache
	docker compose -f docker-compose.dev.yml build --no-cache

run: ## Run the container
	docker compose -f docker-compose.dev.yml up -d

stop: ## Stop the container
	docker compose -f docker-compose.dev.yml down

logs: ## View logs
	docker compose -f docker-compose.dev.yml logs -f

clean: ## Clean up
	docker compose -f docker-compose.dev.yml down -v --rmi local
	rm -rf build/

test-image: ## Build cached test image (first run only)
	docker build -t seedsync-test -f src/docker/build/test-image/Dockerfile .

test: ## Run Python tests (in container with runtime dependencies)
	$(MAKE) test-image
	docker run --rm -v $(PWD)/src/python:/app/python seedsync-test \
		pytest tests/unittests -v --tb=short

test-e2e-docker: ## Run Playwright E2E tests in a throwaway Docker container
	@docker rm -f seedsync-e2e-test 2>/dev/null || true
	docker run -d --name seedsync-e2e-test -p 8801:8800 -e SEEDSYNC_DISABLE_RATE_LIMIT=1 ghcr.io/nitrobass24/seedsync:latest
	@echo "Waiting for container to start..."
	@for i in $$(seq 1 30); do \
		curl -sf http://localhost:8801/ > /dev/null 2>&1 && break; \
		sleep 1; \
	done
	cd src/e2e-playwright && BASE_URL=http://localhost:8801 npx playwright test; \
		exit_code=$$?; \
		docker rm -f seedsync-e2e-test; \
		exit $$exit_code

size: ## Show image size
	@docker images seedsync-seedsync --format "Image size: {{.Size}}"

shell: ## Shell into running container
	docker exec -it seedsync-dev /bin/sh

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*## ' $(MAKEFILE_LIST) | awk -F ':.*## ' '{printf "  %-16s %s\n", $$1, $$2}'
