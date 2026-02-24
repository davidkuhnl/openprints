# OpenPrints Development Roadmap

Phased plan for the OpenPrints PoC and beyond.

- [x] Phase 0 — Vision, Repo Setup, Plumbing, Docs
- [x] Phase 1 — Event Handling CLI
- [x] Phase 2 — Indexer Core (Relay Subscriptions + Reducer + DB)
- [x] Phase 3 — REST API
- [ ] WIP - Phase 4 — Client MVP (List + Detail Pages)
- [ ] Phase 5 — Design Publishing Flow
- [ ] Phase 6 — Endorsements ("I printed this")
- [ ] Phase 7 — Lightning Zaps
- [ ] Phase 8 — File Storage Support
- [ ] Phase 9 — Announcement Notes
- [ ] Phase 99 — Catchall (distant future)

---

## Development Roadmap

### [x] Phase 0 — Vision, Repo Setup, Plumbing, Docs

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

### [x] Phase 1 — Event Handling CLI

**Goal:** Prove end-to-end design event flow: build a CLI that constructs, signs, and publishes `kind 33301` design events to a relay, plus a subscriber that receives and prints them.

**Includes:**

- CLI under `apps/indexer/openprints/` (package `openprints` with `openprints.cli`, `openprints.indexer`, `openprints.common`). Run: `cd apps/indexer && uv run openprints-cli` or `make cli`; troubleshooting: `uv run python -m openprints`.
- Subcommands: `build`, `sign`, `publish`, `subscribe`, `hash`, plus `keygen`, `index`, `db`, `serve`.
- `build` emits a valid `33301` draft event (tags, content, `created_at`); inputs for `name`/`format`/`url`, file or SHA-256, auto-generated `d` id. File handoff and piping: `build | sign | publish` or `build --output draft.json` → `sign --input draft.json` → `publish --input signed.json`.
- Handoff contract in `docs/cli-payload-contract.md` (`artifact_version`, draft/signed states, validation error format). Validation errors centralized in `openprints.common.error_codes` and `openprints.common.errors`.
- Signing via dev `nsec` only (NIP-07 / Nostr Connect reserved for client later).
- `publish` sends signed events to a configured single relay and handles `OK` responses.
- `subscribe` connects to one relay, subscribes to `kind 33301`, prints events (live mode with `SUBSCRIBE_LIMIT=0`).
- Reusable hashing: `hash` subcommand and make targets. Quality: `ruff`, `pytest`, coverage gate, pre-commit, CI.
- Docs so a reviewer can run “publish one design, see it in the subscriber” (e.g. `docs/dev-setup.md`, test-drive).

**Done when:**

- One design event can be published to the local relay and observed by the subscriber; event shape matches the intended schema (e.g. `d` tag, content hash, metadata).

---

### [x] Phase 2 — Indexer Core (Relay Subscriptions + Reducer + DB)

**Goal:** Implement the Python indexer core: subscribe to relevant Nostr events from one or more relays, reduce them into a normalized model, and persist to SQLite.

**Includes:**

- Async relay workers (multi-relay, configurable list, backoff/retries) subscribing to kind `33301` (designs); kinds `33311`/`9735` reserved for later phases.
- Reducer: map raw events to internal design model; replaceable events (newest `created_at` wins per `pubkey` + `d`). Store interface with in-memory/log-only and SQLite implementations.
- SQLite schema: `designs`, `design_versions`; FK `designs.latest_event_id` → `design_versions.event_id`; events persisted to DB.
- `index` CLI and TOML config (`openprints.indexer.toml`). DB: `openprints db wipe --force`, `openprints db stats`; `make cli-db-wipe`, `make cli-db-stats`; inspection in `docs/dev-setup.md`.
- Health endpoints: `GET /health`, `GET /ready` on configurable port (see docs).
- End-to-end test drive: `make test-drive` / `scripts/test-drive.sh` (relay wipe, relay up, key, DB wipe option, indexer + stats, publish 2 designs + update, tear down).

**Done when:**

- Indexer runs against local relay; new design events from Phase 1 appear in the DB in reduced form; replaceable updates overwrite correctly.

---

### [x] Phase 3 — REST API

**Goal:** Expose the indexed data via a FastAPI REST API so the client and other tools can query designs by ID, list, and search.

**Includes:**

- FastAPI app at `openprints.api` (same package as indexer). Swagger UI at `/docs`, OpenAPI at `/openapi.json`; ReDoc off.
- Endpoints: `GET /health`, `GET /ready`; `GET /designs` (list with pagination and `q` for name search), `GET /designs/stats`, `GET /designs/{id}` (single design by API id).
- Design id: opaque base64url-encoded id (from list `items[].id`); store key remains `(pubkey, design_id)`; API encodes/decodes for stable URLs.
- Run: `openprints serve` or `uvicorn openprints.api:app --port 8080`; config via indexer TOML and `OPENPRINTS_API_PORT` (default 8080). See `docs/dev-setup.md`.

**Done when:**

- Client or `curl` can list designs, fetch one by ID, run a basic search, and hit stats; data matches what the indexer has stored.

---

### [~] Phase 4 — Client MVP (List + Detail Pages)

**Goal:** Ship an Astro-based web client that lists designs and shows a detail page, using the indexer's REST API, with SSR for speed and SEO.

**Includes:**

- Astro app in `apps/client` (React islands where useful). Landing/onboarding page in place (splash, intro, building blocks, recent-designs section); list and detail pages to be wired to the API.
- List page: fetch from `GET /designs`, display cards or table (title, creator, date, etc.). Env-configurable API base URL (e.g. `PUBLIC_OPENPRINTS_API_URL`). SSR so content is in the initial HTML.
- Detail page: route by opaque design id; fetch `GET /designs/{id}`; show full metadata, preview, and download link.
- Basic routing and layout; mobile-friendly. Empty/loading/error states handled.

**Done when:**

- A user can open the client, see a list of designs from the indexer, click through to a detail page, and see correct data without hand-editing URLs.

---

### [>] Phase 5 — Design Publishing Flow

**Goal:** Let users create and publish design *metadata* from the client: user supplies a URL (file already hosted elsewhere) and metadata → we build the event, sign (NIP-07 / Nostr Connect), and publish to relay(s). No file upload or storage in our stack yet.

**Includes:**

- "Create design" or "Publish" flow in the client: form for metadata (title, format, license, tags, etc.) and the design file **URL**. User is responsible for hosting the file (e.g. S3, Thingiverse, personal server); we do not accept uploads or provide storage in this phase.
- Optional: user can paste or supply a precomputed `sha256` for the file at that URL for integrity; otherwise we may omit or defer hash in the event.
- Build `kind 33301` event with correct tags and content; sign via NIP-07 or Nostr Connect; broadcast to configured relay(s).
- Feedback in UI: "Published" or link to relay/event; basic error handling (relay down, signer rejected).

**Done when:**

- A user can complete the flow in the browser (metadata + URL only); the new design event appears on the relay, is indexed, and shows up in the client list/detail.

---

### [ ] Phase 6 — Endorsements ("I printed this")

**Goal:** Support "I printed this" endorsements as `kind 33311` events (see `docs/event-schema.md`), and surface aggregated counts or ratings in the API and client.

**Includes:**

- Event schema: kind `33311` (parameterized replaceable per endorser+design). Required tags: `d` (e.g. `openprints:endorse:<design_event_id>`), `e` (design event id), `endorsed` (`"1"` or `"0"` to toggle). Optional: `rating`, `material`, `printer`, `content` (review).
- Indexer: subscribe to `33311`, reduce into endorsements table or embedded counts; version-level and design-level (user-deduped) aggregation.
- REST API: expose endorsement counts or ratings per design (e.g. in `GET /designs/{id}` or a small aggregate endpoint).
- Client: "I printed this" button or form; sign and publish `33311`; show endorsement count or rating on list/detail.

**Done when:**

- Users can endorse (or un-endorse) a design from the client; endorsements appear in the indexer and are visible (e.g. count or rating) on the design in the API and UI.

---

### [ ] Phase 7 — Lightning Zaps

**Goal:** Let users send sats to creators from the client. Design events (kind `33301`) already support an `lnurl` tag for the creator’s Lightning/zap target (see `docs/event-schema.md`). Use NIP-57 zap receipts (kind `9735`) for attribution; no central custody of funds.

**Includes:**

- Schema: `lnurl` on design events (recommended tag) for creator zap target; no new OpenPrints kind—zap receipts are standard NIP-57 `9735`. Indexer resolves `e` tag on receipts to attribute sats to a design.
- Indexer: subscribe to `9735`, ingest receipts that reference design events; expose "zapped" counts or total sats per design/creator (e.g. in `GET /designs/{id}` or a dedicated endpoint).
- Client: "Zap" button or flow that opens wallet/lnurl; display zapped count or total sats per design/creator where useful.
- Docs: how creators set up their Lightning/zap target and how it appears in OpenPrints.

**Done when:**

- A user can zap a creator from a design page; zaps are recorded and visible (e.g. count or total) where intended; no central custody of funds.

---

### [ ] Phase 8 — File Storage Support

**Goal:** Add optional file storage integration so creators can host design files via one or more providers—decentralized (e.g. Blossom) or centralized (e.g. S3/R2)—instead of only supplying an external URL.

**Includes:**

- Integrate with one or more storage backends: decentralized (e.g. Blossom) and/or centralized (e.g. S3, R2, minio). Upload blob, get URL and content hash; optional resolution from hash to URL in client or indexer.
- In the "create design" flow: option to upload to a configured store (or choose provider) vs. user-supplied URL; store resulting URL/hash in the design event and metadata.
- Indexer and API: surface storage-backed URLs where present; client resolves and downloads from the appropriate store.
- Docs: how to configure and use each supported storage option for local dev and production.

**Done when:**

- Creators can choose a supported storage provider for new designs; files are stored and retrievable; list/detail and API show correct links.

---

### [ ] Phase 9 — Announcement Notes

**Goal:** Have the indexer post `kind:1` announcement notes when new designs are indexed, from its own pubkey, so the ecosystem can discover new designs via the indexer's feed.

**Includes:**

- Indexer logic: after reducing a new/replaced design event, optionally create a short `kind:1` note (e.g. title, link to client, design id or relay event id)
- Sign and publish the note to configured relay(s) using the indexer's key (no user keys)
- Config flag or env to enable/disable announcements; rate limiting or batching if needed to avoid spam
- Clear attribution: note is from "OpenPrints indexer" (e.g. in content or profile) so users understand the source

**Done when:**

- New designs indexed by the indexer result in a `kind:1` note on the relay when enabled; notes are readable and correctly attributed

---

### [ ] Phase 99 — Catchall (distant future)

**Goal:** Longer-term initiatives that don’t fit a single phase. Scope and order TBD.

**Includes:**

- **OpenPrints relay:** Run a relay that carries OpenPrints-relevant events only (designs, endorsements, zaps, etc.) for availability and discovery.
- **User onboarding:** Actively reach out to established creators to migrate and monetize their designs on OpenPrints.
- **Nostr client integration:** Work with other clients (e.g. Primal) on interpreting OpenPrints kind events where it makes sense, so designs and endorsements can surface in generic Nostr feeds and UIs.
- **Curated lists and meta work:** Add support for curating lists of designs and other meta work (e.g. collections, featured picks, editorial).
- **Design file verification:** Verify the design file hash (e.g. sha256) and surface verification status in the client (e.g. "verified" / "mismatch").
- **Design file analysis and rendering:** Analyze and render the design file directly in the client, using data from the indexer and/or from Blossom uploads (e.g. 3D preview, mesh stats).
- **AI agent–facing client:** Add a client or API surface for AI agents (discovery, purchase, optional print workflows) with micropayments and similar machine-to-machine flows.
- **General client improvements:** Ongoing UX, performance, accessibility, and feature improvements to the web client.
- **Native client apps:** Android and iOS apps (e.g. native or cross-platform) for browsing, endorsing, and supporting designs on mobile.
- **SEO exposure:** Make designs discoverable via standard search engines and crawlers (e.g. structured data, sitemaps, crawlable list/detail pages).

---

## Refactor Backlog (Low-Context Tasks)

Small cleanup tasks intended to be safe, independent, and easy to pick up in short sessions.

- [ ] **Landing page hero:** Optimize responsive behavior so the logo + "penprints" heading only change at the `lg` (1024px) breakpoint; they currently still shrink/move between 1024px–1536px. See `apps/client/src/components/splash.astro` (TODO in file).
- [ ] **CLI/relay:** Multi-relay fan-out (publish/subscribe), reconnect/backoff hardening, dedupe across relays.
- [ ] Centralize CLI response-envelope builders (`ok`, `errors`, `relay_results`) to avoid repeated JSON key literals across commands.
- [ ] Add typed response models (`TypedDict` or dataclasses) for command outputs (`publish`, `subscribe`, `sign`, `build`).
- [ ] Keep protocol/wire-level literals inline (Nostr message fields), but document which keys are intentionally protocol constants.
- [ ] Extract shared JSON print helpers for success/error output formatting to reduce boilerplate.
- [ ] Add a consistency-sweep test to assert common output shape across CLI commands.
- [ ] Review command modules for tiny duplicate helpers and move stable shared logic into `openprints.common.utils/`.
- [ ] Clean up config value ingestions - config vs env vs args

Guideline: prefer refactors that preserve behavior and improve consistency/readability; avoid mixed feature work in the same PR.
