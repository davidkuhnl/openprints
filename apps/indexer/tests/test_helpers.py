# Fixed nsec for test fixtures so valid_signed_payload() is deterministic.
_TEST_NSEC = "nsec1xrlvm3fn0wdqhymgmlvjkjqjgylxefr9y9ppudnx3dufaqy3ge5s897hvn"


def valid_draft_payload() -> dict:
    return {
        "artifact_version": 1,
        "meta": {"state": "draft", "source": "openprints-cli"},
        "event": {
            "kind": 33301,
            "created_at": 1730000000,
            "tags": [
                ["d", "openprints:00000000-0000-4000-8000-000000000000"],
                ["name", "Stub Design"],
                ["format", "stl"],
                ["sha256", "0000000000000000000000000000000000000000000000000000000000000000"],
                ["url", "https://example.invalid/stub.stl"],
            ],
            "content": "Stub payload from tests.",
        },
    }


def valid_signed_payload() -> dict:
    """Return a cryptographically valid signed payload (verify_event_signature passes)."""
    from openprints.common.signers.dev_nsec import DevNsecSigner

    payload = valid_draft_payload()
    payload["meta"] = dict(payload["meta"])
    payload["meta"]["state"] = "signed"
    signer = DevNsecSigner.from_nsec(_TEST_NSEC)
    payload["event"] = signer.sign_event(payload["event"])
    return payload
