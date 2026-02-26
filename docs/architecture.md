# Architecture

This document describes the intended high-level architecture for OpenPrints.

## Core Components

- **Relay layer:** one or more Nostr relays as the event transport layer.
- **Indexer:** subscribes to relevant Nostr kinds, validates/reduces events, and stores query-friendly state.
- **API layer:** serves indexed data to the client.
- **Client:** Astro + React frontend for discovery, detail pages, and publishing flows.

## Indexer Design

The indexer is built around independent event-processing pipelines by kind:

- **Design listings** (parameterized replaceable, current version resolution)
- **Endorsements** (append-only aggregation)
- **Zap receipts** (high-volume append-only aggregation)

### Zap Pipeline Note

Zap receipts (`kind 9735`) can be much higher volume than design or endorsement events. For that reason, OpenPrints should keep zap handling logically separate from core design reduction:

- **Early stage:** run a single indexer process, but isolate zap handling as a separate internal worker/queue with backpressure.
- **Scale stage:** split zap ingestion into a standalone worker/service so zap bursts cannot starve design indexing.

This preserves correctness and responsiveness for design updates while still allowing full zap aggregation.
