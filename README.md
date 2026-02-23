# OpenPrints

**OpenPrints** is an open-source, decentralized platform for discovering, publishing, and monetizing **3D-printable designs** using the **Nostr protocol** and **Lightning zaps**.  
The goal is to create a censorship-resistant, creator-owned ecosystem for 3D models, where designs are portable, events are verifiable, and monetization is peer-to-peer.

This document defines the project intent, long-term architecture, and initial development roadmap.

---

## Table of Contents

- [Overview](#overview)
- [Goals](#goals)
- [Architecture](#architecture)
  - [Core Components](#core-components)
  - [Event Flow](#event-flow)
- [Nostr Event Schema](#nostr-event-schema)
  - [Design Listing — kind 33001](#design-listing--kind-33001)
  - [Endorsement — kind-33002](#endorsement--kind-33002)
  - [Zap Receipts — kind-9735](#zap-receipts--kind-9735)
- [Technology Choices](#technology-choices)
- [Repository Structure](#repository-structure)
- [Development Roadmap](#development-roadmap)
- [Refactor Backlog (Low-Context Tasks)](#refactor-backlog-low-context-tasks)
- [Local Development Setup](#local-development-setup)
- [Domains & Branding](#domains--branding)
- [License](#license)

---

# Overview

**OpenPrints** re-imagines a 3D design marketplace as an open protocol layer:

- Creators publish designs as **Nostr events**  
- Ownership is tied to their **Nostr keypair**  
- Metadata describes the design (file hash, material, printer, license…)  
- Files are hosted on **simple storage** (R2/S3/minio) or **Blossom**  
- Monetization happens through **Lightning zaps** directly to the creator  
- A community-run **indexer** aggregates the public Nostr data  
- A lightweight **UI client** lets users explore, rate, and support creators  

There is no central authority, no lock-in, no platform control — just a protocol-driven ecosystem for sharing 3D-printable models.

---

# Goals

### ✔ Open, permissionless publishing of 3D-printable designs  
### ✔ Portable ownership via Nostr keys  
### ✔ Direct creator monetization via Lightning  
### ✔ Open-source indexer for search, ranking, and aggregation  
### ✔ Thin, fast UI built on modern web tools  
### ✔ Optional decentralized blob storage (Blossom)  
### ✔ Community-driven, censorship-resistant design  

---

# Architecture

## Core Components

### **1. OpenPrints Client (Astro + React Islands)**
- Browse designs (SSR for SEO + speed)
- View details and previews
- Publish new designs (NIP-07 signing)
- Endorse prints (“I printed this”)
- Send Lightning zaps to creators

### **2. OpenPrints Indexer (Python + FastAPI)**
- Connects to multiple Nostr relays
- Subscribes to design/endorsement/zap events
- Reduces and stores events into SQLite/Postgres
- Exposes REST API for filtering & search

### **3. Storage**
- MVP: traditional object storage (R2/S3/minio)
- Later: optional Blossom blob server uploads for decentralized hosting

### **4. Dev Relay**
- Repo includes a dockerized Nostr relay for local development

---

## Event Flow

1. User fills "Create Design" form in UI  
2. Client uploads file → computes sha256 → gets URL  
3. Client constructs a `33001` Nostr event  
4. NIP-07 signs event  
5. Event is broadcast to relays  
6. Indexer receives event from relays, reduces it into DB  
7. UI fetches design info from indexer’s REST API  
8. Optional: indexer posts a `kind:1` announcement note

---

# Nostr Event Schema

## **Design Listing — kind 33001**
Parameterized replaceable: newest `created_at` wins per (`pubkey`, `d` tag).

**Required tags:**
```
["d", "<design_id>"]
["name", "Phone Stand"]
["format", "stl|3mf"]
["sha256", "<sha256-hash>"]
["url", "https://.../file.stl"]
```

**Recommended tags:**

```
["category", "holder"]
["material", "PLA,PETG"]
["printer", "Prusa MK4"]
["license", "CC-BY-4.0"]
["preview", "https://.../preview.png"]
["lnurl", "lnurlp://creator-address"]
["m", "<mime-type>"]
```


---

## **Endorsement — kind 33002**
Append-only “I printed this” events.

```
["e", "<design-event-id>"]
["rating", "1..5"]
["material", "PETG"]
["printer", "Prusa MK4"]
```

Content may contain a short review.

---

## **Zap Receipts — kind 9735**
Optional indexing for:
- total sats per design  
- trending designs  
- recent activity feed  

---

# Technology Choices

### **Backend (Indexer)**
- Python 3.11+
- FastAPI
- asyncio + WebSockets
- SQLAlchemy / SQLite (dev) / Postgres (prod)
- `python-nostr` or raw websocket handling

### **Frontend (Client)**
- Astro (SSR)
- React islands for interactive flows
- Tailwind optional

### **Storage**
- MVP: simple HTTP/S3/R2 storage
- Optional: Blossom blob servers (NIP-B7 support later)

### **Infrastructure**
- Docker Compose development environment
- Included local Nostr relay

---

# Repository Structure
```
openprints/
  README.md
  docs/
    event-schema.md
    architecture.md
    dev-setup.md
  infra/
    docker-compose.yml
    nostr-relay.config.toml
  apps/
    indexer/     # Python + FastAPI + asyncio + DB
    client/      # Astro + React islands
  packages/
    shared/      # optional shared helpers/types
```


---

# Development Roadmap

Legend: `[x]` done, `[~]` current, `[>]` next, `[ ]` upcoming, `[!]` blocked

Current Phase: **Phase 3 - REST API**

Next Phase: **Phase 4 - Client MVP (List + Detail Pages)**

### [x] Phase 0 — Repo + Docs Setup

**Goal:** Establish the repository layout, core documentation, and a minimal local dev environment so contributors can clone, read, and run the relay without building app code yet.

**Includes:**

- Monorepo structure: `apps/indexer/`, `apps/client/`, `packages/shared/`, `infra/`, `docs/`
- Key docs: `README.md`, `docs/dev-setup.md`, `docs/architecture.md`, `docs/event-schema.md`
- Docker Compose skeleton with a local Nostr relay (e.g. `nostr-rs-relay`) and config
- Scaffolded app directories with `TODO.md` stubs; no full indexer or client implementation yet
- Bootstrap script (e.g. `scripts/setup.sh`) for prerequisites and optional in-repo setup

**Done when:**

- New contributor can clone, run `./scripts/setup.sh`, start the relay with `docker compose up`, and follow dev-setup without hitting missing pieces
- Roadmap and phase list are accurate (e.g. ProgressWatchdog check passes)

---

### [x] Phase 1 — Event Publishing Test Harness

**Goal:** Prove end-to-end design event flow: build a CLI or small tool that constructs, signs, and publishes `kind 33301` design events to a relay, plus a subscriber script that receives and prints them.

**Includes:**

- Script or CLI to build a valid `33301` event (tags, content, `created_at`)
- CLI and indexer live under `apps/indexer/openprints/` (package `openprints` with `openprints.cli`, `openprints.indexer`, `openprints.common`). Primary run: `cd apps/indexer && uv run openprints-cli`, or `make cli`; troubleshooting: `uv run python -m openprints`.
- CLI flow supports file handoff and piping (`build | sign | publish`, or `build --output draft.json` -> `sign --input draft.json` -> `publish --input signed.json`)
- Build/publish handoff contract is defined in `docs/cli-payload-contract.md` (`artifact_version`, draft/signed states, and validation error format)
- Build/publish validation errors are centralized in `openprints.common.error_codes` and `openprints.common.errors`.
- Signing via NIP-07 (browser extension) or Nostr Connect / nsec
- Publish to configurable relay(s); optional: publish from indexer/client env
- Subscriber script (e.g. Python or Node) that connects to the relay, subscribes to `kind 33301`, and logs or prints received events
- Documentation or inline comments so a reviewer can run “publish one design, see it in the subscriber” locally

**Current progress in this phase:**

- [x] CLI scaffolding is in place (`build`, `sign`, `publish`, `subscribe` subcommands)
- [x] Payload contract and validation are implemented and documented
- [x] `build` now emits a real draft event (inputs for `name`/`format`/`url`, file or SHA-256, and auto-generated `d` id)
- [x] Reusable hashing utilities and CLI hash helpers are in place (`hash` subcommand + make targets)
- [x] Automated quality checks are wired (`ruff`, `pytest`, coverage gate, pre-commit, CI)
- [x] `sign` performs dev `nsec` signing (`draft` -> `signed`)
- [x] `publish` sends signed events to a configured single relay and handles `OK` responses
- [x] `subscribe` receives events from a configured single relay (live mode supported with `SUBSCRIBE_LIMIT=0`)
- [>] Next milestone: multi-relay fan-out (publish/subscribe), reconnect/backoff hardening, and dedupe across relays

**Done when:**

- One design event can be published to the local relay and observed by the subscriber; event shape matches the intended schema (e.g. `d` tag, content hash, metadata)

---

### [x] Phase 2 — Indexer Core (Relay Subscriptions + Reducer + DB)

**Goal:** Implement the Python indexer core: subscribe to relevant Nostr events from one or more relays, reduce them into a normalized model, and persist to SQLite.

**Includes:**

- Async Nostr client (e.g. `nostr-sdk` or custom) subscribing to kinds `33301`, and later `33311`/`9735` as needed
- Reducer logic: map raw events to internal design/endorsement/zap models; handle replaceable events (newest `created_at` wins per `pubkey` + `d`)
- SQLite schema for designs (and any supporting tables)
- Configurable relay list and basic error/backoff handling
- Optional: minimal health or metrics endpoint for “indexer is running”

**Current progress in this phase:**

- [x] Async relay workers (multi-relay, configurable list, backoff/retries)
- [x] Reducer (design versions + current row, replaceable by `created_at` per `pubkey` + `d`)
- [x] Store interface and in-memory/log-only implementation
- [x] `index` CLI and TOML config
- [x] SQLite schema and persistent store (`designs`, `design_versions`); FK `designs.latest_event_id` → `design_versions.event_id`; events persisted to DB
- [x] `openprints db wipe --force` and `openprints db stats`; `make cli-db-wipe`, `make cli-db-stats`; DB inspection documented in `docs/dev-setup.md`
- [x] End-to-end test drive (`make test-drive` / `scripts/test-drive.sh`): relay wipe, relay up, key, DB wipe option, indexer + stats, publish 2 designs + update, tear down
- [x] Optional: minimal health endpoint (`GET /health`, `GET /ready` on configurable port; see docs/dev-setup.md)

**Done when:**

- Indexer runs against local relay; new design events from Phase 1 appear in the DB in reduced form; replaceable updates overwrite correctly

---

### [x] Phase 3 — REST API

**Goal:** Expose the indexed data via a FastAPI REST API so the client and other tools can query designs by ID, list, and search.

**Includes:**

- FastAPI app at `openprints.api` (same package as indexer); Swagger UI at `/docs`, OpenAPI at `/openapi.json`; ReDoc off
- Endpoints: `GET /health`, `GET /ready`, `GET /designs` (list with pagination and `q` for name search), `GET /designs/{id}` (single design by API id)
- Design id: `GET /designs/{id}` uses an opaque base64url-encoded id (from list `items[].id`). The store key remains `(pubkey, design_id)`; the API encodes/decodes for stable URLs
- Run: `openprints serve` or `uvicorn openprints.api:app --port 8080`; config via indexer TOML and `OPENPRINTS_API_PORT` (default 8080). See `docs/dev-setup.md`

**Done when:**

- Client or `curl` can list designs, fetch one by ID, and run a basic search; data matches what the indexer has stored

---

### [>] Phase 4 — Client MVP (List + Detail Pages)

**Goal:** Ship an Astro-based web client that lists designs and shows a detail page, using the indexer’s REST API, with SSR for speed and SEO.

**Includes:**

- Astro app with React islands where useful (e.g. interactive filters or components)
- List page: fetch designs from API, display cards or table with title, creator, date, etc.
- Detail page: fetch single design by ID, show full metadata and any available preview/links
- Data fetching from indexer API (env-configurable base URL); SSR so content is in the initial HTML
- Basic routing and layout; mobile-friendly where feasible

**Done when:**

- A user can open the client, see a list of designs from the local indexer, click through to a detail page, and see correct data without hand-editing URLs

---

### [ ] Phase 5 — Design Publishing Flow

**Goal:** Let users create and publish new designs from the client: upload file → compute hash → build `33001` event → sign (NIP-07 / Nostr Connect) → publish to relay(s).

**Includes:**

- “Create design” or “Publish” flow in the client: form for metadata (title, description, tags, license, etc.) and file upload
- File upload to configured storage (e.g. S3/R2/minio); compute and store `sha256` (or agreed hash)
- Build `kind 33001` event with correct tags and content; optional content hash in event
- Signing via NIP-07 or Nostr Connect; then broadcast to configured relay(s)
- Feedback in UI: “Published” or link to relay/event; basic error handling (relay down, signer rejected)

**Done when:**

- A user can complete the flow in the browser; the new design appears on the relay, is indexed by the indexer, and shows up in the client list/detail

---

### [ ] Phase 6 — Endorsements ("I printed this")

**Goal:** Support “I printed this” endorsements as `kind 33002` events, and surface aggregated ratings or counts in the API and client.

**Includes:**

- Event schema and reducer support for `33002`: link to design (e.g. `e` or `a` tag), optional rating/comment
- Indexer: subscribe to `33002`, reduce into endorsements table or embedded counts; optional aggregation (e.g. average rating per design)
- REST API: expose endorsement counts or ratings per design (e.g. in `GET /designs/{id}` or a small aggregate endpoint)
- Client: “I printed this” button or form; sign and publish `33002`; show endorsement count or rating on list/detail

**Done when:**

- Users can endorse a design from the client; endorsements appear in the indexer and are visible (e.g. count or rating) on the design in the API and UI

---

### [ ] Phase 7 — Lightning Zaps

**Goal:** Integrate Lightning zaps so users can send sats to creators; use `lnurl` (and later zap receipts) in the protocol and UI.

**Includes:**

- Schema and tags: `lnurl` (or equivalent) for creator Lightning address / zap target; later support for zap receipt events (`kind 9735`) if needed
- Indexer: ingest zap receipts for attribution and “zapped” counts per design or creator
- Client: “Zap” button or flow that opens wallet or lnurl flow; optional display of “zapped” or total sats per design/creator
- Documentation for how creators set up their Lightning/zap target and how it appears in OpenPrints

**Done when:**

- A user can zap a creator from a design page; zaps are recorded and visible (e.g. count or total) where intended; no central custody of funds

---

### [ ] Phase 8 — Blossom Support

**Goal:** Add optional decentralized file storage via Blossom so creators can host design files without relying only on S3/R2.

**Includes:**

- Blossom (NIP-96 or current spec) integration: upload blob, get URL/content hash; optional resolution from hash to URL in client or indexer
- Toggle or option in the “create design” flow: “Use Blossom” vs existing storage; store blob URL/hash in design event and metadata
- Indexer and API: surface Blossom-backed URLs where present; client can resolve and download from Blossom when chosen
- Docs: how to run or use a Blossom server for local dev and production

**Done when:**

- Creators can choose Blossom for new designs; files are stored and retrievable via Blossom; list/detail and API show correct links

---

### [ ] Phase 9 — Announcement Notes

**Goal:** Have the indexer post `kind:1` announcement notes when new designs are indexed, from its own pubkey, so the ecosystem can discover new designs via the indexer’s feed.

**Includes:**

- Indexer logic: after reducing a new/replaced design event, optionally create a short `kind:1` note (e.g. title, link to client, design id or relay event id)
- Sign and publish the note to configured relay(s) using the indexer’s key (no user keys)
- Config flag or env to enable/disable announcements; rate limiting or batching if needed to avoid spam
- Clear attribution: note is from “OpenPrints indexer” (e.g. in content or profile) so users understand the source

**Done when:**

- New designs indexed by the indexer result in a `kind:1` note on the relay when enabled; notes are readable and correctly attributed

---

### [ ] Phase 10 — Public Release + OpenSats Grant Application

**Goal:** Prepare for public launch and funding: clean repo, deploy to production domain, and submit an OpenSats grant application.

**Includes:**

- Repo cleanup: README, LICENSE, contributing guide, security/contact info; remove or document any placeholder/TODO that’s no longer accurate
- Deploy indexer and client to production (e.g. `openprints.dev`); HTTPS, env config, and basic ops docs
- Optional: public relay list, status page, or short “About” for the project
- OpenSats grant application: narrative, milestones, budget; align with phased deliverables (e.g. Phases 0–7 as “MVP”, 8–9 as enhancements)
- Tag or release v1.0 (or similar) when ready for “public release”

**Done when:**

- Site is live at `openprints.dev` (or agreed domain); repo is presentable to contributors and funders; OpenSats application submitted (or ready to submit) with clear scope and milestones

---

## Refactor Backlog (Low-Context Tasks)

Small cleanup tasks intended to be safe, independent, and easy to pick up in short sessions.

- [ ] Centralize CLI response-envelope builders (`ok`, `errors`, `relay_results`) to avoid repeated JSON key literals across commands.
- [ ] Add typed response models (`TypedDict` or dataclasses) for command outputs (`publish`, `subscribe`, `sign`, `build`).
- [ ] Keep protocol/wire-level literals inline (Nostr message fields), but document which keys are intentionally protocol constants.
- [ ] Extract shared JSON print helpers for success/error output formatting to reduce boilerplate.
- [ ] Add a consistency-sweep test to assert common output shape across CLI commands.
- [ ] Review command modules for tiny duplicate helpers and move stable shared logic into `openprints.common.utils/`.
- [ ] Clean up config value ingestions - config vs env vs args

Guideline: prefer refactors that preserve behavior and improve consistency/readability; avoid mixed feature work in the same PR.

---

# Local Development Setup

This repository includes a complete local environment:
```
docker compose up
```

Services include:

- Local Nostr relay  
- Indexer (Python)  
- Database (SQLite or Postgres)  
- Astro client (dev mode)  

Detailed instructions live in `docs/dev-setup.md`.

---

## Quality Checks (Indexer)

Recommended shortcuts (from repo root):

```bash
make setup
make lint
make test
make check
```

`make setup` runs the full bootstrap (`scripts/setup.sh`): prerequisite checks, app dependency sync, and pre-commit hook installation.

Additional shortcuts:

```bash
make relay-up
make relay-down
make relay-test-up
make relay-test-ws
make relay-check
make cli
make cli-build
make cli-keygen
make cli-sign
make cli-publish
make cli-subscribe
make cli-index
make cli-db-stats
make cli-db-wipe
make cli-hash
cat apps/indexer/tests/fixtures/stub_design.stl | make cli-hash-stdin
```

`make cli-build` accepts optional overrides via `NAME=... FORMAT=... URL=... FILE=... SHA256=... CONTENT=... DESIGN_ID=...`.
`make cli-keygen` generates a local dev keypair (`nsec`/`npub`) for testing flows.
`make cli-sign` uses the dev signer and expects `OPENPRINTS_DEV_NSEC` in your environment.
`make cli-publish` targets `RELAY=...` (default `ws://localhost:7447`) and also supports env fallback (`OPENPRINTS_RELAY_URL` or `OPENPRINTS_RELAY_URLS`).
`make cli-publish` now returns machine-readable JSON (`ok`, `errors`, `relay_results`).
Example with timeout/retry knobs: `make cli-publish RELAY=ws://localhost:7447 PUBLISH_TIMEOUT=5 PUBLISH_RETRIES=2 PUBLISH_RETRY_BACKOFF_MS=300`.
Retries are intended for transport/timeouts only; relay `OK=false` intentionally hard-fails without retry.
`make cli-subscribe` supports `RELAY`, `SUBSCRIBE_KIND`, `SUBSCRIBE_LIMIT`, `SUBSCRIBE_TIMEOUT` and currently subscribes to one relay.
Subscriber internal logs are level-gated and written to stderr. To enable them, set `OPENPRINTS_LOG_LEVEL` (`INFO` or `DEBUG`); optional formatting via `OPENPRINTS_LOG_FORMAT=text|json`.
Example: `OPENPRINTS_LOG_LEVEL=INFO OPENPRINTS_LOG_FORMAT=json make cli-subscribe`.
`EOSE` marks backlog completion only; with `SUBSCRIBE_LIMIT=0`, subscribe keeps waiting for new events until timeout/interrupt.
Relay disconnect is treated as a graceful summary event (`status: disconnected`); reconnect/backoff is the next planned improvement.
Multi-relay subscribe fan-out (with dedupe) is planned.
`make cli-index` runs the indexer pipeline scaffold (relay workers + shared queue + reducer).
Config file: `make setup` creates `apps/indexer/openprints.indexer.toml` from the example when missing (file is not committed).
CLI override examples: `make cli-index INDEX_RELAY=ws://localhost:7447` or `make cli-index RELAYS=ws://localhost:7447,wss://relay.example INDEX_DURATION=20`.
Additional knobs: `INDEX_CONFIG`, `INDEX_KIND`, `INDEX_QUEUE_MAXSIZE`, `INDEX_TIMEOUT`, `INDEX_MAX_RETRIES`, `INDEX_DURATION`.
Setting precedence: CLI/Make overrides -> env vars -> config file -> built-in defaults.
`log_level` can be set in `openprints.indexer.toml`; `OPENPRINTS_LOG_LEVEL` env var still takes precedence.
With `database_path` set in config, the indexer persists to SQLite. `make cli-db-stats` prints DB path, row counts, and latest designs; `make cli-db-wipe` wipes the DB (requires `--force`; use `INDEX_CONFIG` for config path). See `docs/dev-setup.md` for inspecting the database.
Multi-relay publish fan-out is planned (current behavior is single relay per invocation).
One-step export example: `export "$(cd apps/indexer && uv run openprints-cli keygen --env)"`.

Target list/help (source of truth):

```bash
make help
```

Raw equivalents are intentionally kept out of the main README to keep this guide concise. Power-user details can be inferred from `Makefile` targets.

Pre-commit hook config lives at `.pre-commit-config.yaml`.

CI runs these checks in `.github/workflows/ci.yml` on pull requests and pushes to `main`.

To require CI before merge, enable branch protection/rulesets in GitHub and mark the CI status check as required.

---

# Domains & Branding

- Primary domain: **openprints.dev**  
- Secondary domain: **openprints.app**  
- Repository name: **openprints**  
- Open-source, community-first identity  
- No central ownership or lock-in  

---

# License

**TBD** — likely MIT, BSD, or Apache 2.0.  
OpenPrints will be fully open-source.
