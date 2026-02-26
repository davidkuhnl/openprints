# OpenPrints CLI Payload Contract

This document defines the handoff contract across `openprints-cli build`, `openprints-cli sign`, and `openprints-cli publish`.

The contract is intentionally separate from Nostr protocol fields so the CLI artifact can evolve safely over time.

Current workflow:

- `build` emits a `draft` artifact
- `sign` consumes `draft` and emits `signed`
- `publish` consumes `signed` and sends to relay(s)

Current signer backend in CLI:

- `dev-nsec` (local development key from `OPENPRINTS_DEV_NSEC`)
- `remote` is reserved as an extension point and not implemented yet

Utility commands:

- `openprints-cli keygen` can generate local dev `nsec`/`npub` values for testing.
- `make cli-hash` can compute SHA256 of a given file

## Publish Output Contract (Current)

`publish` returns machine-readable JSON:

Current scope: `publish` sends to one relay per invocation.
Planned enhancement: multi-relay fan-out with per-relay results in a single invocation.
Retry behavior (current):

- Transport failures/timeouts can be retried (`--retries`, `--retry-backoff-ms`).
- Relay-level `OK=false` is a deliberate hard failure and is **not retried**.

## Subscribe Runtime Notes (Current)

- `subscribe` connects to one relay per invocation.
- It emits matching events as JSON lines to stdout.
- It emits an execution summary (`ok`, `relay_results`) to stderr.
- `EOSE` marks end-of-stored-events only; in live mode (`--limit 0`) the subscription remains open for new events until timeout/interrupt.
- Relay disconnect is treated as a graceful summary event (`status: disconnected`) rather than a hard validation error.
- Planned reconnect/backoff behavior will be implemented at this disconnect hook.
- Planned enhancement: multi-relay subscribe fan-out with event-id deduplication.

- Success:

```json
{
  "ok": true,
  "relay_results": [
    {
      "relay": "ws://localhost:7447",
      "event_id": "<event id>",
      "accepted": true,
      "message": "ok"
    }
  ]
}
```

- Failure:

```json
{
  "ok": false,
  "errors": [
    {
      "code": "INVALID_VALUE",
      "path": "relay",
      "message": "<error message>"
    }
  ],
  "relay_results": [
    {
      "relay": "ws://localhost:7447",
      "event_id": "<event id>",
      "accepted": false,
      "message": "<relay or transport error>"
    }
  ]
}
```

## v1 Envelope

```json
{
  "artifact_version": 1,
  "meta": {
    "state": "draft",
    "source": "openprints-cli"
  },
  "event": {
    "kind": 33301,
    "created_at": 1730000000,
    "tags": [],
    "content": ""
  }
}
```

Top-level fields:

- `artifact_version` (required, integer)
- `meta` (required, object)
- `event` (required, object)

## `meta` Field

Required fields:

- `state`: `draft` or `signed`
- `source`: non-empty string (currently `openprints-cli`)

## `event` Field

For both `draft` and `signed`, required:

- `kind` (currently only `33301` supported)
- `created_at` (unix timestamp integer)
- `tags` (list of tag arrays; each tag array must contain strings)
- `content` (string; may be Markdown)

Required tags for `kind=33301`:

- `d`
- `name`
- `format`
- `sha256`
- `url`

Additional validation currently enforced:

- `name` must be 1..120 chars after trimming/whitespace normalization.

### Draft vs Signed

When `meta.state = "draft"`:

- `event.id` and `event.sig` MUST NOT be present.

When `meta.state = "signed"`:

- `event.id`, `event.sig`, and `event.pubkey` are required.

## Structured Validation Errors

`sign` and `publish` return machine-readable validation errors:

```json
{
  "ok": false,
  "errors": [
    {
      "code": "MISSING_REQUIRED_FIELD",
      "path": "event.created_at",
      "message": "event.created_at is required"
    }
  ]
}
```

Current error codes include:

- `UNSUPPORTED_ARTIFACT_VERSION`
- `MISSING_REQUIRED_FIELD`
- `INVALID_TYPE`
- `INVALID_VALUE`
- `MISSING_REQUIRED_TAG`
- `DRAFT_CONTAINS_SIGNED_FIELDS`
- `SIGNED_MISSING_SIGNATURE_FIELDS`
- `UNSUPPORTED_EVENT_KIND`
- `INVALID_JSON`

## `artifact_version` Policy

`artifact_version` versions the CLI artifact format, not Nostr protocol.

- v1 is the current supported version.
- `publish` rejects unsupported versions.
- Backward-incompatible contract changes require incrementing `artifact_version`.
- Additive optional fields may remain in the same version when compatibility is preserved.
