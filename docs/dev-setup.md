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
./scripts/setup.sh
```

This checks that Git, Docker, Docker Compose, Python 3.11+, uv, Node 20+, and npm or pnpm are available. If something is missing, it prints install hints. It also runs idempotent setup for any apps that are present (e.g. `uv sync` in `apps/indexer`, `npm install` / `pnpm install` in `apps/client`).

**TODO:** When the indexer and client apps are added, document any extra one-time install steps here (or ensure `./scripts/setup.sh` covers them and keep this section as a pointer to the script).

## 5) Start the dev stack (Relay + DB + Indexer)

The local infrastructure stack is defined in `infra/docker-compose.yml`.

Start services:

```bash
cd infra
docker compose up --build
```

Stop services:

```bash
docker compose down
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

Early endpoints may return stub data; that is expected while the reducer/indexing flow is still being built out.

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

1. Run `./scripts/setup.sh` once (or after pulling changes that add app deps).
2. Start infra from `infra/` with `docker compose up` (or `docker compose up -d` to run in the background).
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

Use the scripts in `scripts/` to confirm the relay is up and speaking Nostr:

1. **HTTP health check** (no extra deps): `./scripts/test-relay-up.sh`
2. **Nostr WebSocket (recommended)**: `./scripts/test-relay-ws.sh` (interactive; choose Python via [uv](https://github.com/astral-sh/uv) or Node)
3. **Nostr WebSocket (Node direct)**: `node scripts/test-relay-node.mjs` (requires Node WebSocket support)

See `scripts/README.md` for details and optional env vars (`RELAY_BASE_URL`, `RELAY_WS_URL`).

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
