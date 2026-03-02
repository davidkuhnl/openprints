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
git clone git@github.com:davidkuhnl/openprints.git
cd openprints
```

Or clone via HTTPS:

```bash
git clone https://github.com/davidkuhnl/openprints.git
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
uv sync --group dev
```

Run the OpenPrints HTTP API (FastAPI):

```bash
# From repo root: use indexer config and optional port
make cli-serve
# or with config and port
make cli-serve INDEX_CONFIG=apps/indexer/openprints.toml API_PORT=8080

# Or from apps/indexer with uv
uv run openprints-cli serve
# or run uvicorn directly (config from OPENPRINTS_CONFIG and cwd)
uv run uvicorn openprints.api:app --host 0.0.0.0 --port 8080
```

The API uses the same indexer config (and database path) as `openprints index`. Set `OPENPRINTS_API_PORT` (default 8080) or pass `--port` to change the bind port.

Quick API checks:

```bash
curl http://localhost:8080/health
curl http://localhost:8080/ready
curl http://localhost:8080/designs
```

Docs: Swagger UI at `/docs`, OpenAPI schema at `/openapi.json`.

### OpenPrints CLI scaffold (uv)

Current CLI scaffold location:

- `apps/indexer/openprints/` (package `openprints` with `openprints.cli`, `openprints.indexer`, `openprints.common`)

Run it from repo root:

```bash
make cli
```

Current CLI commands:

```bash
make cli-build-design
make cli-build-identity
make cli-keygen
make cli-sign
make cli-publish-design
make cli-publish-identity
make cli-subscribe
make cli-index
make cli-serve   # run HTTP API (designs, health, ready)
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
make cli-build-design | make cli-sign | make cli-publish-design
```

Current note: the one-relay roundtrip is implemented (`build -> sign -> publish -> subscribe`). For scriptability and debugging, file handoff is still a good default.

Publish relay selection (single relay for now):

- `make cli-publish-design RELAY=ws://localhost:7447`
- Example with retries: `make cli-publish-design RELAY=ws://localhost:7447 PUBLISH_TIMEOUT=5 PUBLISH_RETRIES=2 PUBLISH_RETRY_BACKOFF_MS=300`
- `make cli-publish-identity RELAY=ws://localhost:7447`
- Example with retries: `make cli-publish-identity RELAY=ws://localhost:7447 PUBLISH_TIMEOUT=5 PUBLISH_RETRIES=2 PUBLISH_RETRY_BACKOFF_MS=300`
- If `RELAY` is not provided, CLI falls back to `OPENPRINTS_RELAY_URLS` (comma-separated list), then default `ws://localhost:7447`.
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

Indexer pipeline (multi-relay, SQLite optional):

- `make cli-index` runs the in-process indexer (relay workers + shared queue + reducer). With a configured `database_path`, events are persisted to SQLite.
- Config file (optional): `make setup` creates `openprints.toml` from `.example` when missing; the file is not committed (edit locally as needed).
- Database: set `database_path = "openprints.db"` in config (or env `OPENPRINTS_INDEX_DATABASE_PATH`) to persist; omit or set to `"log"` for log-only. Wipe with `make cli-db-wipe` (requires `--force`; uses same config).
- Single relay via CLI override: `make cli-index INDEX_RELAY=ws://localhost:7447`
- Multiple relays: `make cli-index RELAYS=ws://localhost:7447,wss://relay.example`
- Runtime knobs:
  - `INDEX_CONFIG` (optional config path; defaults to `apps/indexer/openprints.toml`)
  - Design indexer: `DESIGN_KIND` (default `33301`), `DESIGN_QUEUE_MAXSIZE` (default `1000`), `DESIGN_TIMEOUT` (default `8.0`), `DESIGN_MAX_RETRIES` (default `12`, use `0` for infinite retry loop), `DESIGN_DURATION` in seconds (default `0`, run until interrupted). Env equivalents: `OPENPRINTS_DESIGN_KIND`, `OPENPRINTS_DESIGN_QUEUE_MAXSIZE`, `OPENPRINTS_DESIGN_TIMEOUT`, `OPENPRINTS_DESIGN_MAX_RETRIES`, `OPENPRINTS_DESIGN_DURATION`.
  - `log_level` in config (`CRITICAL|ERROR|WARNING|INFO|DEBUG`)
- Precedence for each setting: CLI flag/Make variable -> env var -> config file -> built-in default.
- Logging level precedence: `OPENPRINTS_LOG_LEVEL` env var overrides config `log_level`.

Health and readiness are served only by the API (`openprints serve`). See **Running the OpenPrints HTTP API** above for `GET /health` and `GET /ready`.

**Inspecting the indexer database**

When `database_path` is set, the indexer writes to two tables:

- **`designs`** — current state per design (one row per `pubkey` + `design_id`): `latest_event_id`, `name`, `format`, `sha256`, `url`, `content`, `tags_json`, `version_count`, timestamps.
- **`design_versions`** — append-only event history: one row per ingested event (`event_id` PK). `designs.latest_event_id` references `design_versions.event_id`.

Quick inspection from the repo root:

- `make cli-db-stats` — prints DB path, row counts for `designs` and `design_versions`, and the latest N designs (default 10). Use `INDEX_CONFIG` if your config lives elsewhere. Example: `make cli-db-stats` or `make cli-db-stats INDEX_CONFIG=openprints.toml`.

Direct SQL (from `apps/indexer` if your path is relative):

```bash
cd apps/indexer
sqlite3 openprints.db "SELECT COUNT(*) FROM designs; SELECT COUNT(*) FROM design_versions;"
sqlite3 openprints.db "SELECT pubkey, design_id, name, latest_published_at FROM designs ORDER BY latest_published_at DESC LIMIT 5;"
```

Full schema and reducer rules are in `docs/indexer-schema.md`.

**End-to-end test drive:** Run `make test-drive` (or `./scripts/test-drive.sh`) from the repo root. It exports a dev key, starts the relay, checks health, optionally wipes the indexer DB, then prompts you to start the indexer in another terminal and run DB stats. It publishes two designs and an update to the first, prompting you to check stats after each step. At the end it runs `make relay-down-wipe` and `make cli-db-wipe`.

Troubleshooting fallback (if entrypoint resolution is broken in your environment):

```bash
cd apps/indexer
uv run python -m openprints
```

Note: the console script is `openprints-cli`; the package is `openprints`.

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
PUBLIC_OPENPRINTS_API_URL=http://localhost:8080
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

## 13) Initial push to Cloudflare (client)

To get the Astro client live on [Cloudflare Pages](https://pages.cloudflare.com/) without connecting the repo to Cloudflare, use Wrangler to deploy the built site manually.

**One-time setup**

1. **Log in to Cloudflare** (uses `npx wrangler`; no need to add Wrangler to the app):

   ```bash
   npx wrangler login
   ```

   A browser window opens; sign in and approve so Wrangler can deploy to your account.

**Deploy**

2. **Build the site**:

   ```bash
   npm run build
   ```

   Output goes to `dist/`.

3. **Deploy to Pages**:

   ```bash
   npx wrangler pages deploy dist --project-name=openprints-client
   ```

   The first run creates a new Cloudflare Pages project named `openprints-client`. You get a URL like `https://openprints-client.pages.dev` for that deployment.

**Custom domain (openprints.dev)**

4. In the **Cloudflare Dashboard** go to **Workers & Pages** → **openprints-client** → **Custom domains**.
5. Click **Set up a custom domain** (or **Add custom domain**) and enter **openprints.dev**.
6. Cloudflare adds the DNS record; with the domain already on Cloudflare, SSL is automatic. After DNS propagates, `https://openprints.dev` serves the client.

To publish updates later, run `npm run build` and `npx wrangler pages deploy dist --project-name=openprints-client` again from `apps/client`.
