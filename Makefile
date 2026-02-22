.PHONY: help setup setup-fast lint test check relay-up relay-down relay-logs relay-test-up relay-test-ws relay-check cli cli-build cli-publish cli-subscribe cli-hash cli-hash-stdin

INDEXER_DIR := apps/indexer
INFRA_DIR := infra
FILE ?= tests/fixtures/stub_design.stl

help:
	@echo "Available targets:"
	@echo "  make setup          - run full bootstrap (prereqs, app deps, git hooks)"
	@echo "  make setup-fast     - sync indexer dev dependencies with uv"
	@echo "  make lint           - run ruff format check + ruff lint (indexer)"
	@echo "  make test           - run pytest with coverage gate (indexer)"
	@echo "  make check          - run lint and test"
	@echo "  make relay-up       - start local relay stack in background"
	@echo "  make relay-down     - stop local relay stack"
	@echo "  make relay-logs     - follow local relay logs"
	@echo "  make relay-test-up  - run HTTP relay health check"
	@echo "  make relay-test-ws  - run interactive relay websocket check"
	@echo "  make relay-check    - run relay HTTP + websocket checks"
	@echo "  make cli            - run openprints-cli scaffold"
	@echo "  make cli-build      - run openprints-cli build"
	@echo "  make cli-publish    - run openprints-cli publish (stdin)"
	@echo "  make cli-subscribe  - run openprints-cli subscribe"
	@echo "  make cli-hash       - run openprints-cli hash --file \$$FILE"
	@echo "  make cli-hash-stdin - run openprints-cli hash for piped stdin"

setup:
	@./scripts/setup.sh

setup-fast:
	@cd $(INDEXER_DIR) && uv sync --group dev

lint:
	@cd $(INDEXER_DIR) && uv run ruff format --check .
	@cd $(INDEXER_DIR) && uv run ruff check .

test:
	@cd $(INDEXER_DIR) && uv run pytest --cov=openprints_cli --cov-branch --cov-report=term-missing --cov-fail-under=85

check: lint test

relay-up:
	@cd $(INFRA_DIR) && docker compose up -d

relay-down:
	@cd $(INFRA_DIR) && docker compose down

relay-logs:
	@cd $(INFRA_DIR) && docker compose logs -f

relay-test-up:
	@./scripts/test-relay-up.sh

relay-test-ws:
	@./scripts/test-relay-ws.sh

relay-check: relay-test-up relay-test-ws

cli:
	@cd $(INDEXER_DIR) && uv run openprints-cli

cli-build:
	@cd $(INDEXER_DIR) && uv run openprints-cli build

cli-publish:
	@cd $(INDEXER_DIR) && uv run openprints-cli publish

cli-subscribe:
	@cd $(INDEXER_DIR) && uv run openprints-cli subscribe

cli-hash:
	@cd $(INDEXER_DIR) && uv run openprints-cli hash --file "$(FILE)"

cli-hash-stdin:
	@cd $(INDEXER_DIR) && uv run openprints-cli hash --file -
