# Scripts

Small scripts for verifying and bootstrapping the local dev stack. Referenced from [docs/dev-setup.md](../docs/dev-setup.md).

## Bootstrap (prerequisites + in-repo setup)

Run once after cloning (and after pulling changes that add app dependencies):

```bash
./scripts/setup.sh
```

This checks for Git, Docker, Docker Compose, Python 3.11+, uv, Node 20+, and npm/pnpm. If anything is missing, it prints install hints. It also runs idempotent setup for `apps/indexer` (when it has `pyproject.toml` or `requirements.txt`) and `apps/client` (when it has `package.json`).

**TODO:** When the indexer and client apps are added, extend the script or docs with any extra one-time install steps.

## Relay checks

Default relay base URL: `http://localhost:7447` (HTTP) / `ws://localhost:7447` (WebSocket). Override with `RELAY_BASE_URL` / `RELAY_WS_URL` if your relay runs elsewhere.

### 1. HTTP health check (curl)

No extra dependencies. Run from repo root:

```bash
./scripts/test-relay-up.sh
```

Optional: `RELAY_BASE_URL=http://localhost:7447 ./scripts/test-relay-up.sh`

### 2. Nostr WebSocket check (Node)

Requires Node with native WebSocket support.

Then:

```bash
node scripts/test-relay-node.mjs
```

Optional: `RELAY_WS_URL=ws://localhost:7447 node scripts/test-relay-node.mjs`

### 3. Unified WebSocket wrapper (interactive: Python or Node)

Run from repo root:

```bash
./scripts/test-relay-ws.sh
```

This prompts for:

- `1` Python check via [uv](https://github.com/astral-sh/uv) and `websockets`
- `2` Node check via `scripts/test-relay-node.mjs`

Non-interactive options:

- `./scripts/test-relay-ws.sh --python`
- `./scripts/test-relay-ws.sh --node`

Optional: `RELAY_WS_URL=ws://localhost:7447 ./scripts/test-relay-ws.sh --python`
