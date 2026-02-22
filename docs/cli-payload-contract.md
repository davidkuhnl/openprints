# OpenPrints CLI Payload Contract

This document defines the handoff contract between `openprints-cli build` and `openprints-cli publish`.

The contract is intentionally separate from Nostr protocol fields so the CLI artifact can evolve safely over time.

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

`publish` returns machine-readable validation errors:

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
