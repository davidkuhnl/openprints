# Architecture

This document describes the intended high-level architecture for OpenPrints.

## Core Components

- **Relay layer:** one or more Nostr relays as the event transport layer.
- **Indexing app:** runs multiple independent pipelines that subscribe to relevant Nostr kinds, validate/reduce events, and store query-friendly state.
- **API layer:** serves indexed data (designs, identities, etc.) to the client.
- **Client:** Astro + React frontend for discovery, detail pages, identity-aware UI, and publishing flows.

## Indexer Design

The indexing app is composed of **parallel pipelines** that share the same database and relay set:

- **Design indexer (current implementation):**
  - Subscribes to `kind 33301` design events.
  - Validates and reduces versions into:
    - an append-only `design_versions` history, and
    - a `designs` table with the latest view per design (one row per `(pubkey, design_id)`).
  - Treats each event’s `pubkey` as an identity, seeding entries in the `identities` table.

- **Identity indexer (new pipeline):**
  - Periodically scans the `identities` table for pubkeys with missing or stale metadata.
  - Batches those pubkeys into short-lived `REQ` subscriptions for `kind 0` metadata events across configured relays.
  - Parses profile fields (`name`, `display_name`, `about`, `picture`, `banner`, `website`, `nip05`, `lud06`, `lud16`, …) and updates the `identities` table.
  - Applies retry/backoff on failed lookups and refreshes stale fetched profiles over time.
  - The client always reads from `identities` and falls back to truncated `npub` when metadata is absent.

- **Endorsements pipeline (planned):**
  - Append-only aggregation of endorsement events into a query-friendly table keyed by design and endorser.

- **Zap receipts pipeline (planned):**
  - High-volume append-only aggregation of `kind 9735` events, summarized into zap statistics per design and identity.

### Zap Pipeline Note

Zap receipts (`kind 9735`) can be much higher volume than design or endorsement events. For that reason, OpenPrints should keep zap handling logically separate from core design and identity reduction:

- **Early stage:** run a single indexing app process that hosts all pipelines (design, identity, endorsements, zaps), but keep zap handling as an internal worker/queue with its own backpressure.
- **Scale stage:** split zap ingestion into a standalone worker/service so zap bursts cannot starve design or identity indexing.

This preserves correctness and responsiveness for design updates and identity resolution while still allowing full zap aggregation.