# Scripts

Small scripts for verifying and bootstrapping the local dev stack. Referenced from [docs/dev-setup.md](../docs/dev-setup.md).

## Preferred usage

Use Makefile targets from repo root for normal workflows:

```bash
make setup
make relay-up
make relay-down
make relay-logs
make relay-test-up
make relay-test-ws
make relay-check
```

## Script-level usage (power users)

These scripts are the lower-level commands behind Make targets:

- `scripts/setup.sh`
- `scripts/test-relay-up.sh`
- `scripts/test-relay-ws.sh`
- `scripts/test-relay-node.mjs`
- `scripts/test-relay.py`

Default relay base URL is `http://localhost:7447` and default relay WebSocket URL is `ws://localhost:7447`. Override with `RELAY_BASE_URL` / `RELAY_WS_URL` when needed.
