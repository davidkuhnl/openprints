.PHONY: help setup setup-fast lint test check relay-up relay-down relay-logs relay-test-up relay-test-ws relay-check cli cli-build cli-sign cli-publish cli-subscribe cli-index cli-hash cli-hash-stdin cli-keygen

INDEXER_DIR := apps/indexer
INFRA_DIR := infra
FILE ?= tests/fixtures/stub_design.stl
SHA256 ?=
NAME ?= Stub Design
FORMAT ?= stl
URL ?= https://example.invalid/stub.stl
CONTENT ?= Built via make cli-build
DESIGN_ID ?=
RELAY ?= ws://localhost:7447
PUBLISH_TIMEOUT ?= 8.0
PUBLISH_RETRIES ?= 0
PUBLISH_RETRY_BACKOFF_MS ?= 400
SUBSCRIBE_KIND ?= 33301
SUBSCRIBE_LIMIT ?= 1
SUBSCRIBE_TIMEOUT ?= 8.0
RELAYS ?=
INDEX_RELAY ?=
INDEX_CONFIG ?=
INDEX_KIND ?=
INDEX_QUEUE_MAXSIZE ?=
INDEX_TIMEOUT ?=
INDEX_MAX_RETRIES ?=
INDEX_DURATION ?=

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
	@echo "  make cli-build      - run openprints-cli build using NAME/FORMAT/URL and FILE or SHA256 vars"
	@echo "  make cli-sign       - run openprints-cli sign (stdin, requires OPENPRINTS_DEV_NSEC)"
	@echo "  make cli-publish    - run openprints-cli publish to RELAY=\$$RELAY with timeout/retry vars"
	@echo "  make cli-subscribe  - run openprints-cli subscribe on RELAY=\$$RELAY"
	@echo "  make cli-index      - run openprints-cli index pipeline stub (INDEX_CONFIG/INDEX_RELAY/RELAYS)"
	@echo "  make cli-hash       - run openprints-cli hash --file \$$FILE"
	@echo "  make cli-hash-stdin - run openprints-cli hash for piped stdin"
	@echo "  make cli-keygen     - generate a local dev nsec/npub keypair"

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
	@cd $(INDEXER_DIR) && EXTRA_DESIGN_ID="" ; HASH_ARG="--file \"$(FILE)\"" ; if [ -n "$(DESIGN_ID)" ]; then EXTRA_DESIGN_ID="--design-id \"$(DESIGN_ID)\""; fi ; if [ -n "$(SHA256)" ]; then HASH_ARG="--sha256 \"$(SHA256)\""; fi ; eval "uv run openprints-cli build --name \"$(NAME)\" --format \"$(FORMAT)\" --url \"$(URL)\" --content \"$(CONTENT)\" $$HASH_ARG $$EXTRA_DESIGN_ID"

cli-sign:
	@cd $(INDEXER_DIR) && uv run openprints-cli sign

cli-publish:
	@cd $(INDEXER_DIR) && uv run openprints-cli publish --relay "$(RELAY)" --timeout "$(PUBLISH_TIMEOUT)" --retries "$(PUBLISH_RETRIES)" --retry-backoff-ms "$(PUBLISH_RETRY_BACKOFF_MS)"

cli-subscribe:
	@cd $(INDEXER_DIR) && uv run openprints-cli subscribe --relay "$(RELAY)" --kind "$(SUBSCRIBE_KIND)" --limit "$(SUBSCRIBE_LIMIT)" --timeout "$(SUBSCRIBE_TIMEOUT)"

cli-index:
	@cd $(INDEXER_DIR) && CMD="uv run openprints-cli index" ; if [ -n "$(INDEX_CONFIG)" ]; then CMD="$$CMD --config \"$(INDEX_CONFIG)\""; fi ; if [ -n "$(RELAYS)" ]; then IFS=','; for relay in $(RELAYS); do CMD="$$CMD --relay $$relay"; done; elif [ -n "$(INDEX_RELAY)" ]; then CMD="$$CMD --relay \"$(INDEX_RELAY)\""; fi ; if [ -n "$(INDEX_KIND)" ]; then CMD="$$CMD --kind \"$(INDEX_KIND)\""; fi ; if [ -n "$(INDEX_QUEUE_MAXSIZE)" ]; then CMD="$$CMD --queue-maxsize \"$(INDEX_QUEUE_MAXSIZE)\""; fi ; if [ -n "$(INDEX_TIMEOUT)" ]; then CMD="$$CMD --timeout \"$(INDEX_TIMEOUT)\""; fi ; if [ -n "$(INDEX_MAX_RETRIES)" ]; then CMD="$$CMD --max-retries \"$(INDEX_MAX_RETRIES)\""; fi ; if [ -n "$(INDEX_DURATION)" ]; then CMD="$$CMD --duration \"$(INDEX_DURATION)\""; fi ; eval "$$CMD"

cli-hash:
	@cd $(INDEXER_DIR) && uv run openprints-cli hash --file "$(FILE)"

cli-hash-stdin:
	@cd $(INDEXER_DIR) && uv run openprints-cli hash --file -

cli-keygen:
	@cd $(INDEXER_DIR) && uv run openprints-cli keygen
