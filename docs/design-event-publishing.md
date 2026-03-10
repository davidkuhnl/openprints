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