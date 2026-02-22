def valid_draft_payload() -> dict:
    return {
        "artifact_version": 1,
        "meta": {"state": "draft", "source": "openprints-cli"},
        "event": {
            "kind": 33301,
            "created_at": 1730000000,
            "tags": [
                ["d", "openprints:stub-design-id"],
                ["name", "Stub Design"],
                ["format", "stl"],
                ["sha256", "0000000000000000000000000000000000000000000000000000000000000000"],
                ["url", "https://example.invalid/stub.stl"],
            ],
            "content": "Stub payload from tests.",
        },
    }
