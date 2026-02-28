# Identities in OpenPrints
This doc describes how identities are handled in OpenPrints. First, this is Nostr, so the only truly required identifier is `pubkey`; everything else is optional.

## Note on `pubkey` & `npub`
- The `pubkey` is the real 64-hex public key used in nostr event signatures and relay queries.
- The `npub` is just a bech32-encoded, human-friendly version of the same pubkey.
- `npub` → decode → `pubkey` (hex), and `pubkey` → encode → `npub`.
- Internally we always use `pubkey`; in the UI we usually display `npub` (truncated).
- In this doc, we refer to identity as `npub` if it comes from the user and as `pubkey` if it comes from the events. But ultimately, they both represent the same identity, just in different formats.
- We can always derive `npub` from `pubkey` on demand, so storing `npub` alongside `pubkey` is not required. In fact, we prefer that to avoid duplicate data and race conditions.

## Sources of Identities in OpenPrints
There are two pipelines through which we can get unknown identities in OpenPrints.

1) User Onboarding - although not implemented yet, this is an obvious source of identity in OpenPrints. New user comes in via the client, they either paste their `npub`, or we generate a fresh keypair for them.

2) OpenPrints defines the kind 33301 for designs, but we do not assume we are the only source of these events. Anyone can publish one. In these events, `pubkey` is the identifier of the author of the design.

## Full Identity in OpenPrints - kind 0 nostr event
For the best UX, we obviously do not want to show truncated `npub`-s all over the client. Ideally we'd have a bit more info to be able to display a nice user profile.

We can get that info from the **kind 0 event** (if it was ever broadcasted for that given pubkey). Kind 0 event introduced in [NIP-01](https://github.com/nostr-protocol/nips/blob/master/01.md) contains user profile metadata.

Per NIP-01, kind 0 events are "replaceable", so only the newest kind 0 event for a given `pubkey` matters.

Kind 0 events, as all events in Nostr, can evolve and get more fields over time, but currently we can get at least
- name
- display_name
- about
- picture
- banner
- website
- nip05 verified name
- lud06      # LNURL-pay
- lud16      # Lightning address (e.g. alice@zbd.gg)
Again, assuming these were ever published for that given pubkey. Some identities will never publish a kind 0 event, so their metadata may legitimately remain empty forever.

## Identity Metadata Handling in OpenPrints
We store the identity metadata in a table called `identities`. This table has `pubkey` as the primary key, a few mandatory internal status fields, and a full host of nullable identity metadata fields.

Whenever the client needs a user identity, the identity is fetched from this table. If the metadata is not available, we fall back to using the truncated `npub` constructed from the `pubkey`.

On the backend, if the DesignIndexer polling the 33301 kinds (design events) encounters an unknown `pubkey` it inserts it into the `identities` table with no metadata. We'll do the same insert down the road when we implement user onboarding in the client.

Finally, we'll introduce a new logical component (initially part of the main indexer but can be split out later) - the IdentityIndexer. This component will periodically scan the `identities` table and it will do the following:
- poll the configured relays for kind 0 events for the unknown `pubkey`-s in the `identities` table and update the metadata
- poll the configured relays for kind 0 events for ALL `pubkey`-s whose metadata hasn't been updated recently enough, so that stale metadata is periodically refreshed and the system converges toward eventual consistency
- use reasonable retry and backoff for `pubkey`-s that never return metadata, to avoid hammering relays unnecessarily


## Uncategorized Notes
- We will not store any history of the user identity metadata. OpenPrints does not aim to be a user profile hub, it merely needs the user profile data for better UX in the client
- Once the client app is mature enough, we will most likely allow the user (especially the ones that came to the Nostr ecosystem through us) to fill in their profile metadata and we will broadcast the 0 kind event on their behalf to the configured relays.
- Future versions of OpenPrints may choose to validate `nip05` values, but this is not required for the current implementation.


## Identity Implementation Notes
- these notes are here just for managing context while I am implementing the pipeline and will be removed after.

High-level implementation plan for spinning up the identity pipeline:

1. Reorganize the current indexer into a **DesignIndexer**:
   - Extract the existing `IndexerCoordinator` logic into a `DesignIndexer` class that:
     - spins up `RelayWorker`s for kind `33301`
     - owns the reducer/queue
     - exposes basic stats (processed/reduced/duplicates).
   - Keep behavior identical for now; this should be a pure refactor.

2. Introduce an **IndexerApp** (or similar “app coordinator”) on top:
   - `IndexerApp` holds:
     - one `DesignIndexer`
     - (later) one `IdentityIndexer`
   - It owns the shared `stop_event` and orchestrates starting/stopping both pipelines.
   - Wire the existing CLI (`run_index`) to construct `DesignIndexer` + `IndexerApp` instead of directly using the old coordinator.

3. Add **identity seeding** to the design pipeline (log-only first):
   - Extend `IndexStore` with a no-op/log-only `ensure_identity_pending(pubkey, first_seen_at)` method.
   - In `ReducerWorker.reduce_one`, after validating `pubkey`, call:
     - `await self._store.ensure_identity_pending(pubkey, envelope.received_at)`
   - With `LogOnlyIndexStore`, this should just log the call so you can confirm pubkeys are being “seen” correctly.

4. Add the **`identities` table** and real DB support:
   - Extend `SQLiteIndexStore` to:
     - create an `identities` table with:
       - `pubkey` (PK, TEXT)
       - `status` (`pending | fetched | failed`)
       - `pubkey_first_seen_at`, `pubkey_last_seen_at`
       - profile fields: `name`, `display_name`, `about`, `picture`, `banner`, `website`, `nip05`, `lud06`, `lud16`, `profile_raw_json`
       - `profile_fetched_at`, `fetch_last_attempt_at`, `retry_count`
     - implement `ensure_identity_pending` to upsert:
       - new row → `status='pending'`, timestamps set
       - existing row → update `last_seen_at`.
   - Switch the CLI to use `SQLiteIndexStore` by default in dev so identities actually persist.

5. Implement the **IdentityIndexer** pipeline (log-only first):
   - Create an `IdentityIndexer` class with:
     - `__init__(store, relays, batch_size, stale_after_s, ...)`
     - `run(stop_event)` loop that:
       - periodically asks the store for pubkeys needing refresh (e.g. `status='pending'` or stale `profile_fetched_at`)
       - for now, just logs which pubkeys it *would* fetch metadata for, without talking to relays yet.
   - Integrate `IdentityIndexer` into `IndexerApp` so the CLI runs both:
     - `DesignIndexer.run(stop_event)`
     - `IdentityIndexer.run(stop_event)` (only when using a real DB store).

6. Wire up **real kind-0 fetching** in IdentityIndexer:
   - Implement a `fetch_kind0_for_pubkeys(pubkeys, relays)` helper that:
     - opens short-lived WebSocket connections to the configured relays
     - sends a `REQ` with `kinds:[0]` and `authors:[pubkey1, pubkey2, ...]`
     - listens for responses until EOSE/timeout
     - parses `event["content"]` JSON into metadata dicts keyed by `pubkey`.
   - In `IdentityIndexer.run`, replace the log-only part with:
     - call `fetch_kind0_for_pubkeys` for each batch
     - call `store.update_identity_profile(pubkey, metadata)` for all returned profiles
     - update `status`, `profile_fetched_at`, `last_attempt_at`, and `retry_count` as appropriate.

7. Add **staleness + backoff** logic:
   - In the store, expose a way to select:
     - `status='pending'` identities, and
     - `status='fetched'` identities whose `profile_fetched_at` is older than a configured threshold.
   - In `IdentityIndexer`, respect:
     - `last_attempt_at` + `retry_count` to avoid hammering relays for pubkeys that never return a kind-0.
   - This gives you both:
     - initial metadata resolution, and
     - periodic refresh of existing profiles.

8. Hook up the **client to `identities`**:
   - Ensure the API layer exposes identity info for pubkeys (or npubs) by reading from the `identities` table.
   - In the client:
     - show full profile data if present (name, picture, etc.).
     - fall back to truncated `npub` derived from `pubkey` when metadata is missing.

9. Iterate and clean up:
   - Remove log-only branches once the pipeline is stable.
   - Trim these implementation notes from the doc, keeping only the conceptual parts (identity model, data flow, and constraints).
