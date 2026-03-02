# Indexer Schema Draft

This document is a working draft for the OpenPrints indexer data model (Phase 2+).
It is intentionally iterative and may change as we validate behavior against real relay traffic.

## Core Identity Model

A design entity is identified by:

- `pubkey` (event author)
- `design_id` (from `d` tag, currently `openprints:<uuid>`)

Natural key for a design: `(pubkey, design_id)`.

### Why this key

- Matches Nostr parameterized-replaceable semantics.
- Supports "newest `created_at` wins" per design entity.
- Allows a design to evolve over time while keeping stable identity.

## Event vs Materialized State

Use exactly two logical layers (no third "current view" table):

1. Materialized current design state (latest winning row per `(pubkey, design_id)`)
2. Append-only event history (all observed valid events)

This gives us auditability + fast API reads.

## Proposed Tables (Draft)

## `designs` (materialized latest)

Purpose: one row per current winner for `(pubkey, design_id)`.

Candidate columns:

- `pubkey` TEXT NOT NULL
- `design_id` TEXT NOT NULL
- `latest_event_id` TEXT NOT NULL
- `latest_published_at` INTEGER NOT NULL
- `first_published_at` INTEGER NOT NULL (immutable after first insert)
- `first_seen_at` INTEGER NOT NULL (indexer ingest timestamp, immutable)
- `updated_at` INTEGER NOT NULL (indexer ingest timestamp, mutable)
- `version_count` INTEGER NOT NULL DEFAULT 1
- `name` TEXT
- `format` TEXT
- `sha256` TEXT
- `url` TEXT
- `content` TEXT
- `tags_json` TEXT NOT NULL DEFAULT '{}' (materialized optional/current tags)
- PRIMARY KEY `(pubkey, design_id)`
- FOREIGN KEY `latest_event_id` -> `design_versions(event_id)`

Suggested indexes:

- `idx_designs_latest_published_at` on `(latest_published_at DESC)`
- `idx_designs_first_published_at` on `(first_published_at DESC)`
- `idx_designs_name` on `(name)`

## `design_versions` (append-only)

Purpose: store every accepted design listing event revision.

Candidate columns:

- `event_id` TEXT PRIMARY KEY
- `pubkey` TEXT NOT NULL
- `kind` INTEGER NOT NULL
- `created_at` INTEGER NOT NULL
- `design_id` TEXT NOT NULL
- `name` TEXT
- `format` TEXT
- `sha256` TEXT
- `url` TEXT
- `content` TEXT
- `raw_event_json` TEXT NOT NULL
- `received_at` INTEGER NOT NULL

Suggested indexes:

- `idx_design_events_pubkey_design_id_created_at` on `(pubkey, design_id, created_at DESC)`
- `idx_design_events_received_at` on `(received_at DESC)`

## Forward Compatibility: Endorsements and Zaps (Important)

This section defines the compatibility contract we are preserving now while focusing only on designs.

### Canonical mapping guarantee

`design_versions` is the canonical mapping from:

- `event_id` -> `(pubkey, design_id)`

This is guaranteed by storing, in `design_versions`:

- `event_id` as PRIMARY KEY
- `pubkey` as NOT NULL
- `design_id` as NOT NULL

Implication: any future table that references a design by event id can resolve target identity
by joining to `design_events` on `event_id`.

### What this enables later

For future endorsement/zap ingestion, we can support both common Nostr reference styles:

- `e` references (target event id)
- `a` references (parameterized address, e.g. `kind:pubkey:d`)

Planned resolver behavior:

1. Parse raw references from incoming interaction event.
2. Try immediate resolution:
   - `e` via `design_versions.event_id`
   - `a` via parsed `(pubkey, design_id)`
3. Store both:
   - raw references as received
   - resolved target identity when known
4. Mark unresolved references and backfill later when target design appears.

### Non-negotiable rule for schema evolution

Do not remove `pubkey` or `design_id` from `design_versions`, and do not make `event_id`
non-unique. Those fields are the long-term bridge that links interactions (endorsements/zaps)
back to the canonical design identity.

### Optional future interaction table shape (example only)

Potential columns for a future `design_interactions` table:

- `interaction_event_id` (PK)
- `kind` (endorsement/zap kind)
- `actor_pubkey`
- `target_event_id` (raw `e` reference, nullable)
- `target_a` (raw `a` reference, nullable)
- `target_pubkey` (resolved, nullable)
- `target_design_id` (resolved, nullable)
- `resolution_status` (`resolved` or `unresolved`)
- `created_at`
- `received_at`

This keeps ingestion robust under out-of-order relay delivery while preserving full provenance.

## Reducer Rules (Initial Draft)

For each incoming valid kind `33301` event:

1. Parse required tags (`d`, `name`, `format`, `sha256`, `url`).
2. Insert event into `design_events` if unseen (`event_id` PK).
3. Compare with `designs` row for `(pubkey, design_id)`:
   - If no current row:
     - insert into `designs`
     - set `first_published_at = created_at` (immutable)
     - set `latest_published_at = created_at`
     - set `version_count = 1`
   - If current row exists:
   - increment `version_count` only when a new unique `event_id` is inserted
   - if incoming `created_at` is newer: replace current pointer/data and update `latest_published_at`
   - if incoming `created_at` is older: keep existing current pointer/data
   - tie-breaker (same `created_at`): deterministic policy required (see Open Questions)
   - Never mutate `first_published_at` after initial insert.

## Open Questions

- Tie-breaker when `created_at` is equal for same `(pubkey, design_id)`:
  - lexical `event_id`?
  - first-seen wins?
- Do we normalize/store tags in a separate table now, or defer until API search requirements force it?
- Should `design_id` be stored with prefix (`openprints:`) or canonicalized without prefix?
- Do we store only validated events, or store invalid events in a quarantine table for diagnostics?
- How should we represent designs that are deleted or marked as corrupt (e.g. tombstone events, soft-delete flags, or a separate state table)?
- Do we want a uniqueness constraint on `(pubkey, design_id, created_at)` in `design_versions`, or only on `event_id`?

## Migration Strategy

- Start with SQLite-compatible schema and SQL.
- Keep DDL and queries portable to Postgres.
- Avoid SQLite-specific conveniences that are hard to port.
- Use explicit migrations from the start so schema evolution is auditable.

## Indexer Runtime Architecture (Implementation Plan)

This section defines the ingestion pipeline design for Phase 2 so we can build it incrementally.

## Core pipeline

1. One subscriber task per relay websocket URL.
2. Subscribers produce validated raw event envelopes into a shared ingestion queue.
3. One reducer worker consumes queue items in order of arrival and performs DB writes.
4. Reducer applies replaceable semantics and updates `design_versions` + `designs` transactionally.

Design goal: keep concurrency simple at first, with correctness and observability prioritized over throughput.

## Building blocks

### `RelayWorker` (per relay)

Responsibilities:

- connect / reconnect with backoff+jitter
- send subscribe request
- receive relay frames (`EVENT`, `EOSE`, `NOTICE`)
- attach source metadata (`relay`, `received_at`)
- enqueue candidate events for reducer

Notes:

- one worker per relay keeps failure isolation simple
- disconnects should not crash the process; workers should recover

### `IngestQueue` (shared, bounded)

Responsibilities:

- single handoff channel from subscribers to reducer
- backpressure boundary between network I/O and DB writes

Policy (initial):

- bounded queue
- **block producers when full** (no silent drops)
- emit queue-depth and blocked-producer metrics/logs

Rationale: start with lossless behavior and explicit pressure signals.

### `ReducerWorker` (single consumer initially)

Responsibilities:

- parse/normalize required tags
- idempotency checks by `event_id`
- update `design_events` and `designs` in one transaction
- maintain `version_count`, immutable `first_published_at`, and latest pointers

Reducer invariants:

- `design_events.event_id` is unique
- `designs.first_published_at` never changes after first insert
- `designs.version_count` increments only for newly inserted event ids
- same `(pubkey, design_id)` conflict resolution follows deterministic tie-break rule

### `Store/Repository` layer

Responsibilities:

- encapsulate SQL statements and transactions
- provide clear reducer operations (insert version, upsert current, fetch current)
- keep SQL dialect portable (SQLite now, Postgres later)

## Queue topology roadmap

### Phase 2 initial topology

- one shared bounded queue
- one reducer

This is the simplest correct model and easiest to reason about.

### Optional topology if burst pressure appears

- add one small bounded queue per relay
- forward to shared bounded queue

Benefits:

- isolates noisy relays
- smooths short bursts
- gives per-relay queue metrics

Still keep all queues bounded.

## Backpressure and drop policy

Initial policy:

- do not drop events intentionally
- when queue is full, producer waits (`await put`)

If sustained pressure appears later:

- optimize reducer/DB path first
- then consider partitioned reducers by design key
- only introduce selective drop strategy with explicit metrics and replay/backfill story

## Ordering, idempotency, and duplicates

- events can arrive out of order across relays
- same event can be seen on multiple relays
- reducer must be idempotent
- `event_id` PK handles duplicate replays
- replaceable winner selection uses `(pubkey, design_id, created_at, tie-breaker)`

Current implementation note (2026-03-02):

- The in-process reducer (`ReducerWorker`) keeps an in-memory `seen_event_ids` set and
  `(pubkey, design_id) -> DesignCurrentRow` map and uses those for duplicate detection and
  `version_count` / winner selection.
- This is sufficient for a single long-lived process, but it is **not restart- or replay-safe**:
  re-ingesting historical events after a restart can currently reapply versions and distort
  counts unless additional guards are added.
- A future iteration should push these invariants down into the SQLite layer (driving
  `design_versions` + `designs` purely from stored rows) so that a cold start over the same
  `design_versions` history always recomputes the identical materialized state.

## Logging and metrics (minimum)

Track at least:

- queue depth (current/max)
- reducer throughput (events/sec)
- duplicate rate (`event_id` already seen)
- per-relay reconnect count
- per-relay receive errors/timeouts
- reducer DB error count

Logs should be structured and sent to stderr; event output contracts remain unaffected.

## Graceful shutdown contract

1. stop accepting new relay messages
2. allow in-flight receive handlers to finish
3. drain queue into reducer
4. commit remaining DB transactions
5. cleanly exit

No partial writes across `design_events` and `designs`.

## Incremental implementation milestones

1. single relay worker + shared bounded queue + single reducer + DB transaction path
2. multi-relay workers on same queue
3. reconnect/backoff hardening + queue metrics
4. tie-breaker finalization + deterministic tests
5. optional per-relay buffering if needed

## Next Iteration Checklist

- Finalize tie-breaker policy.
- Write initial migration for `design_versions` and `designs`.
- Add reducer tests for replaceable semantics:
  - newer wins
  - older ignored
  - same-timestamp deterministic behavior
- Add reducer tests for `version_count` and immutable `first_published_at`.
