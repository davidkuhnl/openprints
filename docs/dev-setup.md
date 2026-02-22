# OpenPrints - Development Setup

This guide helps you get a local OpenPrints development environment running so you can work on the full stack: local Nostr relay, indexer API, and Astro client.

OpenPrints is still early-stage, so some components may be minimal or stubbed at first. The goal is to make the dev loop smooth from day one.

## 1) Prerequisites

Install the following tools before starting:

- Git
- Docker + Docker Compose
- Python **3.11+**
- [uv](https://github.com/astral-sh/uv) (Python package manager; used for scripts and indexer)
- Node.js **20+**
- npm or pnpm

Check installed versions:

```bash
git --version
docker --version
docker compose version
python --version
uv --version
node --version
npm --version
# or
pnpm --version
```

## 2) Repository Layout (dev view)

Current target structure:

```text
openprints/
  README.md
  docs/
    dev-setup.md
    event-schema.md
    architecture.md
  infra/
    docker-compose.yml
    nostr-relay.config.toml
  apps/
    indexer/        # Python + FastAPI
    client/         # Astro + React
  packages/
    shared/         # optional shared helpers
```

This layout may evolve as the project grows, but this is the intended development shape.

## 3) Clone the repository

Clone via SSH:

```bash
git clone git@github.com:<your-org-or-user>/openprints.git
cd openprints
```

Or clone via HTTPS:

```bash
git clone https://github.com/<your-org-or-user>/openprints.git
cd openprints
```

## 4) Bootstrap (check prerequisites and in-repo setup)

From the repo root, run:

```bash
make setup
```

This is the primary setup entrypoint. It delegates to `scripts/setup.sh`, checks prerequisites (Git, Docker, Docker Compose, Python 3.11+, uv, Node 20+, npm/pnpm), and runs idempotent in-repo setup for available apps.
It also installs the repository pre-commit git hook (using local `pre-commit` if available, otherwise `uvx pre-commit`).

**TODO:** When the indexer and client apps are added, document any extra one-time install steps here (or ensure `./scripts/setup.sh` covers them and keep this section as a pointer to the script).

## 5) Start the dev stack (Relay + DB + Indexer)

The local infrastructure stack is defined in `infra/docker-compose.yml`.

Start services:

```bash
make relay-up
```

Stop services:

```bash
make relay-down
```

Expected services (names may vary by compose config):

- `nostr-relay`
- `db`
- `indexer`

If the indexer service is initially a placeholder, that is fine. At this stage, getting the stack up cleanly is the first goal.

## 6) Running the indexer locally (without Docker)

If you want faster iteration on backend code, run the indexer directly on your machine.

```bash
cd apps/indexer
python -m venv .venv
source .venv/bin/activate
# Windows (PowerShell): .venv\Scripts\Activate.ps1

pip install -r requirements.txt
```

Run the FastAPI app:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Quick API checks:

```bash
curl http://localhost:8000/health
# or
curl http://localhost:8000/designs
```

### OpenPrints CLI scaffold (uv)

Current CLI scaffold location:

- `apps/indexer/openprints_cli/`

Run it from repo root:

```bash
make cli
```

Current CLI commands:

```bash
make cli-build
make cli-keygen
make cli-sign
make cli-publish
make cli-subscribe
```

Payload handoff contract (`build` -> `sign` -> `publish`) is documented in `docs/cli-payload-contract.md`.

For dev signing, export a local signer key before `make cli-sign`:

```bash
export OPENPRINTS_DEV_NSEC="<your-local-dev-nsec>"
```

To generate a local dev keypair:

```bash
make cli-keygen
```

To generate and export in one step:

```bash
export "$(cd apps/indexer && uv run openprints-cli keygen --env)"
echo "$OPENPRINTS_DEV_NSEC" | cut -c1-5  # should print: nsec1
```

Run `make cli-sign` in the same terminal session where `OPENPRINTS_DEV_NSEC` is exported.

Chained workflow (target state, once sign/publish implementations are fully pipeline-safe):

```bash
make cli-build | make cli-sign | make cli-publish
```

Current note: the one-relay roundtrip is implemented (`build -> sign -> publish -> subscribe`). For scriptability and debugging, file handoff is still a good default.

Publish relay selection (single relay for now):

- `make cli-publish RELAY=ws://localhost:7447`
- Example with retries: `make cli-publish RELAY=ws://localhost:7447 PUBLISH_TIMEOUT=5 PUBLISH_RETRIES=2 PUBLISH_RETRY_BACKOFF_MS=300`
- If `RELAY` is not provided, CLI falls back to `OPENPRINTS_RELAY_URL`, then first entry in `OPENPRINTS_RELAY_URLS`, then default `ws://localhost:7447`.
- `publish` output is machine-readable JSON with `ok`, `errors`, and `relay_results`.
- Planned enhancement: publish fan-out to multiple relays in one command (instead of current single-relay behavior).
- Retries are for transport/timeouts only; relay `OK=false` is intentionally treated as a hard failure (no retry).

Subscribe relay selection (single relay for now):

- `make cli-subscribe RELAY=ws://localhost:7447`
- Example: `make cli-subscribe RELAY=ws://localhost:7447 SUBSCRIBE_KIND=33301 SUBSCRIBE_LIMIT=1 SUBSCRIBE_TIMEOUT=8`
- `subscribe` prints matching events as JSON lines to stdout and emits an execution summary to stderr.
- `EOSE` does not stop live mode: with `SUBSCRIBE_LIMIT=0`, subscription keeps waiting for new events until timeout/interrupt.
- Relay disconnect is treated as a graceful shutdown event (`status: disconnected`) in the summary output.
- Planned reconnect/backoff logic will be implemented at this disconnect hook.
- Planned enhancement: subscribe fan-out and deduplicated stream across multiple relays in one command.

Troubleshooting fallback (if entrypoint resolution is broken in your environment):

```bash
cd apps/indexer
uv run python -m openprints_cli
```

Note: the console script name is `openprints-cli` (hyphen), not `openprints_cli`.

Early indexer/client endpoints may remain minimal while reducer/indexing work is built out in Phase 2.

## 7) Running the Astro client

In a separate terminal:

```bash
cd apps/client
npm install
npm run dev
```

Or with pnpm:

```bash
cd apps/client
pnpm install
pnpm dev
```

Default Astro dev URL is usually:

```text
http://localhost:4321
```

At first, the UI may be a placeholder or very simple page while API integration is in progress.

## 8) Connecting to the local Nostr relay

Use a local relay WebSocket URL such as:

- `ws://localhost:<relay-port>` (host machine)
- `ws://nostr-relay:<relay-port>` (from another container in Docker network)

The indexer keeps a relay URL list and subscribes to those relays for relevant event kinds (for example, 33001/33002/9735 as the schema settles).

The client will eventually use signer flows (NIP-07 / Nostr Connect), but may begin with minimal relay awareness and API-first reads.

## 9) Typical dev workflow

Happy-path development loop:

1. Run `make setup` once (or after pulling changes that add app deps).
2. Start infra with `make relay-up`.
3. Run indexer either:
   - in Docker (via compose), or
   - locally in `apps/indexer` for rapid backend iteration.
4. Run Astro client in `apps/client`.
5. Edit code in:
   - `apps/indexer` (event ingestion, reducer logic, API)
   - `apps/client` (design list/detail UI and data fetching)
6. Verify behavior in browser and via API calls.

## 10) Environment variables

OpenPrints will use `.env` files for local configuration. Typical variables include:

- DB connection URL
- relay URL list
- storage base URL
- optional Blossom endpoint
- indexer Nostr secret key (development only)

Example `.env` (placeholder values only):

```env
# apps/indexer/.env (example)
OPENPRINTS_DB_URL=sqlite:///./openprints.db
OPENPRINTS_RELAY_URLS=ws://localhost:<relay-port>
OPENPRINTS_STORAGE_BASE_URL=http://localhost:<storage-port>
OPENPRINTS_BLOSSOM_URL=
OPENPRINTS_INDEXER_NOSTR_SECRET_KEY=<dev-only-placeholder>

# apps/client/.env (example)
PUBLIC_INDEXER_API_BASE_URL=http://localhost:8000
PUBLIC_DEFAULT_RELAY_URL=ws://localhost:<relay-port>
```

Never commit real secrets to git. Keep sensitive local values in untracked `.env` files.

## 11) Testing (planned)

Testing strategy will expand as features land:

- **Unit tests** for event parsing and reducer/state-transition logic.
- **Integration tests** that bring up relay + indexer and assert API outputs.
- **Basic UI tests** for key pages and flows in the Astro client.

## 12) Troubleshooting

### Verify the relay

Use make targets from repo root:

```bash
make relay-test-up
make relay-test-ws
make relay-check
```

See `scripts/README.md` for lower-level script usage and optional env vars (`RELAY_BASE_URL`, `RELAY_WS_URL`).

### Common local issues

- **Relay will not start**
  - Check `docker compose logs <relay-service-name>`.
  - Validate relay config syntax in `infra/nostr-relay.config.toml`.

- **Indexer cannot connect to relay**
  - Verify relay URLs and ports.
  - Confirm container networking (`localhost` vs service name inside Docker).

- **Client cannot reach API**
  - Verify indexer host/port.
  - Check client API base URL env var.
  - Confirm CORS settings on the indexer.

When in doubt, restart cleanly:

```bash
cd infra
docker compose down
docker compose up --build
```
