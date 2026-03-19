# Event Publishing in OpenPrints

This doc describes how design event `33301` publishing is handled in OpenPrints. We discuss the entire pipeline:
- the user putting together the design metadata in the client
- the raw design event being serialized and signed in the client
- the signed design event being sent to the indexer via the API
- the indexer verifying the signed event
- the indexer broadcasting the event to the configured relays (relay list from indexer config / env)
- the indexer seeing the event on the relays and indexing it in our DB
- the event being visible in the client

The client generates the design id `d` (e.g. `openprints:<uuid>`) when creating a new design so the design has a stable identity and can be updated later. The event must satisfy the required tags and validation rules in `docs/event-schema.md`; the indexer enforces them on verify.

## V1 Goals
- simple straightforward process - no clever UX
- signing in the client only - no delegations
- we only support existing identities - not creating new ones
- we only support external uploads - not allowing the user to upload the design file or pictures

## Verification (indexer)
When the indexer receives a signed event from the client it verifies:
- Nostr signature: `id`, `pubkey`, and `sig` are valid for the event payload
- Kind is `33301`
- Required tags and content rules from `docs/event-schema.md` (e.g. `d`, `name`, `format`, `sha256`, `url`; name length and character rules). No alteration of the event — only accept or reject.

## API contract
- Client sends the signed Nostr event (full JSON) in the request body (e.g. `POST /designs/publish` or similar; exact path TBD).
- Responses: e.g. 202 accepted (event accepted and will be broadcast), 400 invalid event (verification failed), 502 relay error (broadcast failed). Exact codes and body shape TBD in implementation.

## Later Considerations
- when the event is verified by the indexer - pre-index it and show it in the UI (maybe as unverified) to avoid UX lag
- allow the user to delegate signing to the indexer / or just the client so they don't have to re-sign everything
- implement the whole "new identity" pipeline so that even a non-nostr user can publish immediately
    - also implement the indexer shortcut so that the new identity does not have to first go through the relays
- allow importing directly from other platforms - extract description, picture links, files
- allow multiple design files
- support uploads to blossom
- support publishing new versions of existing designs
- support deleting and restoring designs


## Implementation Phases
This section will be removed once the pipeline is in a mature state

High level implementation plan for the design event publishing pipeline:

1) New design wizard in the UI
    - detect signer `window.nostr`. If not present, block any further steps and prompt the user to install extension
    - if signer is present, get pubkey and attempt to fetch identity; if not indexed yet, continue (it will be indexed later)
    - generate stable design id `d` (e.g. `openprints:<uuid>`) when the wizard starts
    - user fills required metadata (name, format, url, optional description, optional tags)
    - allow `sha256` to be optional in V1 since we do not handle files
    - validate fields locally according to `docs/event-schema.md`

2) Serialize the design event in the UI before signing
    - construct unsigned Nostr event `{kind:33301, created_at, pubkey, tags, content}`
    - include deterministic tags (`d`, `name`, `format`, `url`, optional `sha256`, etc.)
    - include optional lineage tag `previous_version_event_id`
      - `null`/omitted for initial version
      - set to the direct predecessor event id for updates
    - ensure tag ordering and formatting match `docs/event-schema.md`
    - preview the serialized event (optional debug view)

3) Signing in the UI
    - call `window.nostr.signEvent(event)`
    - attach `id` and `sig` to the event
    - if signing fails, abort publish and show error

4) Send signed event to indexer API
    - POST full signed event JSON to `/designs/publish`
    - indexer returns `202 Accepted` if verification passes

5) Indexer verification
    - verify signature (`id`, `pubkey`, `sig`)
    - enforce event kind `33301`
    - validate required tags and schema rules
    - reject invalid events without modifying them

6) Broadcast
    - indexer publishes the event to configured relays
    - broadcast failures do not invalidate the publish request

7) Indexing
    - indexer eventually sees the event from relays or local publish
    - event is inserted into DB and becomes visible in the client

8) Idempotency
    - duplicate submission of the same `event.id` is treated as idempotent
    - indexer may rebroadcast but will not create duplicate records

See also: `docs/event-schema.md` (design event shape and required tags), `docs/identities.md` (existing-identity assumption).

## Phase: Updating Existing Designs (Scope + Plan)

Goal: if the signer `pubkey` owns a design, they can publish a new kind `33301` event with the same `d` tag, and OpenPrints treats it as a new version of the same design.

### What already works today
- The protocol model is already correct: schema and reducer use NIP-33 semantics (`(pubkey, kind, d)` identity, newest `created_at` wins).
- Client already sends signed kind `33301` events to `POST /designs/publish`.
- Indexer already stores full history in `design_versions` and current materialized state in `designs`.
- API already exposes `version_count` per design item (`GET /designs`, `GET /designs/{id}`).

### Gaps to close for "edit existing design"
- The client only supports "new design" publish flow (`/app/designs/new`), always generating a fresh `d`.
- There is no owner-aware edit affordance in list/detail/profile UIs.
- There is no API endpoint for per-design version history (events behind `version_count` are not exposed).
- Version UX is shallow today (count only; no timeline, no diff view, no rollback/re-publish path).
- There is no explicit product rule for "significant vs cosmetic" updates.

### Ownership model (who is allowed to edit)
- Source of truth should remain Nostr signature semantics:
  - An update is valid only if signer produces a valid event where `event.pubkey` matches the design owner pubkey and `d` is unchanged.
  - Practically this means only the private key owner can publish authoritative updates for that design identity.
- Client-side ownership check for UX:
  1. resolve current authoritative signer pubkey from `identity-store`,
  2. fetch design via `GET /designs/{id}`,
  3. show edit controls only when `signerPubkey === design.pubkey`.
- Server-side enforcement:
  - no extra auth needed beyond event signature validation already in place;
  - optional defense-in-depth check in publish route: if event references existing `(pubkey, d)` then only that same pubkey can update (which is already implied by signature + tuple semantics, but good to log explicitly).

### Where edit actions should live
- Design detail page (`/app/designs/{id}`): primary "Edit design" CTA for owners.
- Design list cards: lightweight "Edit" shortcut for owner-owned rows when signer is known.
- Profile pages (`/app/profile`, `/app/identity/{id}`):
  - in "Latest designs", show owner-only edit affordance per card;
  - keep "Publish design" CTA as create-new path.
- Non-owners should never see edit CTAs (instead show read-only "View history" once added).

### New form vs reusing publish form
Recommendation: reuse the existing publish form component with explicit mode.

- Add form mode contract:
  - `mode: "create" | "edit"`
  - `initialValues` (for edit preload from current design)
  - `lockedDesignId` (the existing `d` value; never regenerated in edit mode)
- In edit mode:
  - prefill current values from selected design,
  - keep `d` hidden and immutable,
  - adjust copy (`Publish update` instead of `Publish`),
  - keep same signing + publish pipeline.
- Keep a separate route for clarity and share component:
  - e.g. `/app/designs/{id}/edit` rendering the same form component in edit mode.

This avoids duplicate validation logic and preserves one canonical event builder.

### API and indexer scope needed next
1) Version history API (required for real version UX)
- Add endpoint: `GET /designs/{id}/versions?limit=&offset=`
- Return ordered versions (newest first), including:
  - `event_id`, `created_at`, `name`, `format`, `sha256`, `url`, `content`, `tags_json`
  - optional derived `change_summary` fields (see below).

2) Store/indexer read path
- Add `list_design_versions(pubkey, design_id, limit, offset)` in store.
- Add serializer for version items.
- Keep write path unchanged for first iteration (already stores versions).

3) Determinism and replay safety (important follow-up)
- Current reducer keeps in-memory duplicate/current tracking; docs already note this is not restart/replay-safe for exact `version_count` invariants.
- Before "best in class" version UX, harden reducer/state derivation so replays cannot skew counts or latest pointers.

### Version UX: beyond count
Recommended baseline:
- On design detail:
  - show `Version N` badge and `Updated X ago`,
  - add "Version history" panel with timeline entries,
  - each entry shows timestamp, short event id, and detected changed fields.
- History entry actions:
  - "View this version" (read-only snapshot)
  - "Copy event JSON" (open-source transparency)
  - owner-only "Reuse as draft" (load that version into edit form and publish a new replacement event).
- Diff hints:
  - show field-level changes vs previous version (name/url/sha256/format/content/tags).

### Significant vs cosmetic changes (version counting policy)
Recommendation:
- Canonical count (`version_count`) must remain raw protocol version count (every accepted unique event).
- Add a separate derived classification for UX:
  - `change_type: "major" | "minor" | "cosmetic"` (computed, not protocol-critical) or optional explicit tag later.
- First pass heuristic:
  - `major`: file identity changed (`url`, `sha256`, `format`, maybe license),
  - `minor`: metadata/tag changes with meaningful user impact,
  - `cosmetic`: whitespace/description polish only.
- UI can show both:
  - "12 total updates (3 major)" to avoid penalizing healthy maintenance.

### Open-source and product quality considerations
- Auditability first: always expose raw signed event payload and immutable history.
- Attribution clarity: every version must clearly show author identity and timestamp.
- Anti-confusion UX: make it explicit that only owner key can update canonical design; others can publish forks/new designs.
- Fork support (follow-up): provide "Fork design" flow that creates a new `d` under the current user.
- Moderation realities: open networks allow noisy updates; plan rate-limit and relay/result diagnostics in UI.
- Accessibility and integrity:
  - keep HTTPS+hash checks visible;
  - highlight hash changes prominently in history.

### Implementation plan (suggested phases)
1) Owner detection + edit entry points
- Add signer-vs-design-owner comparison in client.
- Add owner-only edit CTAs on detail + list/profile cards.

2) Shared create/edit form mode
- Reuse current publish form with `create/edit` mode and prefill support.
- Add `/app/designs/{id}/edit` route.
- Ensure edit mode keeps original `d`.

3) Version history API + UI
- Add backend read endpoint for versions.
- Add design detail "Version history" timeline and per-version snapshot view.

4) Change classification and richer version UX
- Add derived diff + `change_type`.
- Show major/minor/cosmetic indicators and filtered history views.

5) Hardening and trustworthiness
- Address reducer replay/version-count robustness in store-backed logic.
- Add tests for edit/update flows, ownership gating, and version ordering/tie-break behavior.

### Decisions to confirm before implementation
- Route shape: `/app/designs/{id}/edit` preferred?
- Should non-owners see "Fork design" immediately or later phase?
- Do we classify change type heuristically only, or also allow optional explicit author tag?
- Do we allow editing from any historical version ("reuse as draft") in V1 of this phase, or only from latest?

## Version view and routing strategy

We will implement version-aware design pages in two steps.

### Step 1 — Canonical version view

Refactor the current design page into a canonical version view.

This view represents a single version of a design (not “a design with history”).

Clarifications:
- The current `/design/:designId` page is effectively the latest version.
- We should redesign it so it can represent any version, not just the latest.

What belongs in the canonical version view:
- Core design content
  - title
  - images
  - description
- File/download section
- Metadata relevant to that version
- A lightweight version history navigator (not full snapshots)
- An optional “advanced” / collapsible section for technical transparency
  - raw snapshot data
  - signed event JSON
  - hashes / technical fields

UI rules:
- The main UI should be human-readable.
- Raw/system-heavy data should be secondary and collapsible.
- The page should not behave like a debug inspector.

### Step 2 — Routing and version resolution

Introduce two routes:
- `/design/:designId`
  - resolves to the latest version
  - canonical/shareable page
- `/design/:designId/version/:versionId`
  - resolves to a specific historical version

Implementation detail:
- Both routes should use the same underlying view/component.
- The only difference is the data source and a small amount of context UI.
- Version records should explicitly model lineage using nullable `previous_version_event_id`.
  - Initial version: `previous_version_event_id = null`.
  - Subsequent updates: `previous_version_event_id = <event id of previous version>`.

Expected UI differences for the historical view:
- Show a banner/indicator:
  - `Viewing version X from {timestamp}`
- Provide a CTA:
  - `Back to latest version`
- Potentially disable or adjust actions that only make sense for the latest version

### Design principles

- Separate identity (design) from state (version).
- Treat the main page as “latest version of this design”.
- Treat version pages as “snapshots in time”.
- Keep version history lightweight and navigational.
- Move full snapshot + raw event data out of the main flow.

### Outcome

Expected result:
- Clean, product-focused design page.
- Clear mental model for users:
  - `design = identity`
  - `versions = evolution over time`
- Scalable structure for future features (diffs, comparisons, etc.).

## Delete support TODOs

- [ ] Add design delete support as a first-class flow (owner-only).
- [ ] On delete, hide/disable the design across UI surfaces, including all version pages (`/design/:designId` and `/design/:designId/version/:versionId`).
- [ ] Publish a Nostr delete event to configured relays for the design/version events being removed.
- [ ] If the design files are hosted on Blossom servers, issue deletion requests for those files as part of the delete flow.
- [ ] Add clear user messaging: because of Nostr replication, we cannot guarantee full deletion of the historical trail from all relays/clients.
- [ ] Add a post-delete "download safety" check:
  - list every download URL ever referenced by any version,
  - verify whether each file is still reachable,
  - show a clear status (`still available` / `unreachable`) so users can confirm practical takedown.

## Forks and historical base-version TODOs

- [ ] Immediate rule: only allow editing from the current/latest version to avoid ambiguous branching semantics in V1.
- [ ] Enforce this in both UI and API behavior:
  - edit entry points should always preload from latest,
  - historical version views should not expose "Edit this version" yet.
- [ ] Add chain-consistency validation for lineage:
  - if `previous_version_event_id` is present, ensure it belongs to the same `(pubkey, kind=33301, d)` as the event being published (i.e. it is a true predecessor for the same design identity).
  - if the predecessor event is not yet indexed, validate in a best-effort way without rejecting the publish.
- [ ] Add clear UX copy on historical version pages:
  - `Editing is only available from the latest version for now.`
- [ ] Future feature: introduce fork as a first-class concept, allowing users to fork from any historical version.
- [ ] Fork behavior should create a new design identity (`new d`) while preserving attribution to source design + source version.
- [ ] Add dedicated "Fork this version" action on version pages once this lands.
- [ ] Include fork lineage in UI and API:
  - show `forked from {designId}@{versionId}`,
  - support filtering/browsing related forks.

## Indexer background URL health-check TODOs

- [ ] Add a periodic background job in the indexer to validate that referenced URLs are still live.
- [ ] Scope to both:
  - design file/download URLs,
  - image/media URLs used in design metadata.
- [ ] Persist health status per URL (last checked at, HTTP/status result, consecutive failures, first seen down timestamp).
- [ ] Define failure thresholds and retry policy to avoid noisy transient alerts.
- [ ] On confirmed failures, notify admins with enough context to act:
  - design id, version/event id, URL, failure reason, and first observed downtime.
- [ ] Notify design authors when their file/image URLs appear to be down, with guidance to publish an updated version.
- [ ] Surface URL health in product UI (at minimum owner/admin visibility) so issues are visible without relying only on external alerts.

## Indexer relay presence / completeness TODOs

- [ ] Track relay presence for every accepted/indexed design event (kind `33301` and any related delete events):
  - store `event_id`,
  - store the set of `relay_url`s we have seen it on,
  - store `first_seen_at` / `last_seen_at` per relay (or an aggregated equivalent).
- [ ] Define “expected relays” as the configured relay list for the indexer (from indexer config / env).
- [ ] Periodically (or on-demand after indexing) check for completeness:
  - if an event is missing from one or more configured relays, mark it as incomplete.
- [ ] Offer recovery actions to the creator/owner:
  - surface which relays are missing,
  - prompt the creator to republish the event to those relays.
- [ ] Optional automation:
  - if policy allows, the indexer can attempt to publish/rebroadcast to missing relays automatically after a configurable grace period.
- [ ] Make sure delete semantics are included:
  - completeness checks should also apply to delete events so clients can converge on the same visible state.