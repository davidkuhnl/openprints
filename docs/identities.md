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

### TODO: On-demand kind 0 fetch endpoint for onboarding
- Add an API endpoint that accepts a `pubkey` and performs an on-demand relay poll for that identity's latest kind `0` event.
- Intended use: when `/app/profile` resolves signer pubkey but `GET /identity/{id}` returns 404 (unknown identity in OpenPrints), the client should call this endpoint to bootstrap metadata immediately instead of waiting for periodic indexer refresh.
- Suggested behavior:
  - fan out to configured relays with short timeout + bounded retries,
  - if kind `0` is found, upsert `identities` and return the normalized identity payload,
  - if not found, return a non-error "not found on relays" result so client can stay in onboarding UX.


## Uncategorized Notes
- We will not store any history of the user identity metadata. OpenPrints does not aim to be a user profile hub, it merely needs the user profile data for better UX in the client
- Once the client app is mature enough, we will most likely allow the user (especially the ones that came to the Nostr ecosystem through us) to fill in their profile metadata and we will broadcast the 0 kind event on their behalf to the configured relays.
- Future versions of OpenPrints may choose to validate `nip05` values, but this is not required for the current implementation.
