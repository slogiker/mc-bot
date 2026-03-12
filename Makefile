# mc-bot Makefile — shortcuts for testing & development

.PHONY: test test-verbose test-single build up down logs restart clean

# ──────────────────────────────────
# Automated Testing (Docker)
# ──────────────────────────────────

## Run all pytest tests inside Docker
test:
	docker compose -f docker-compose.test.yml up --build --abort-on-container-exit
	docker compose -f docker-compose.test.yml down --rmi local --volumes

## Verbose test output with full tracebacks
test-verbose:
	docker compose -f docker-compose.test.yml run --rm --build test-runner \
		python -m pytest tests/ -v --tb=long -s
	docker compose -f docker-compose.test.yml down --rmi local --volumes

## Run a single test file (usage: make test-single FILE=tests/test_config.py)
test-single:
	docker compose -f docker-compose.test.yml run --rm --build test-runner \
		python -m pytest $(FILE) -v --tb=short
	docker compose -f docker-compose.test.yml down --rmi local --volumes

# ──────────────────────────────────
# Production (Development)
# ──────────────────────────────────

## Build the production Docker image
build:
	docker compose build

## Start the bot in Docker (production)
up:
	docker compose up -d --build

## Stop the bot
down:
	docker compose down

## Restart the bot
restart:
	docker compose restart

## View live logs (Ctrl+C to stop)
logs:
	docker compose logs -f --tail=50

## Stop and remove ALL containers, images, and volumes (careful!)
clean:
	docker compose down --rmi local --volumes
	docker compose -f docker-compose.test.yml down --rmi local --volumes 2>/dev/null || true
