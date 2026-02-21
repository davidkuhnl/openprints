#!/usr/bin/env bash
# Unified Nostr WebSocket check wrapper for the local relay.
# Usage:
#   ./scripts/test-relay-ws.sh             # interactive prompt (python or node)
#   ./scripts/test-relay-ws.sh --python    # run python check via uv
#   ./scripts/test-relay-ws.sh --node      # run node check
# Optional:
#   RELAY_WS_URL=ws://localhost:7447 ./scripts/test-relay-ws.sh

set -e
SCRIPT_DIR="${SCRIPT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"
REPO_ROOT="${REPO_ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}"
cd "$REPO_ROOT"

run_python() {
  echo "Running Python WebSocket check (uv + websockets)..."
  uv run --with websockets python scripts/test-relay.py
}

run_node() {
  echo "Running Node WebSocket check..."
  node scripts/test-relay-node.mjs
}

case "${1:-}" in
  --python)
    run_python
    exit 0
    ;;
  --node)
    run_node
    exit 0
    ;;
  "")
    ;;
  *)
    echo "Unknown option: $1"
    echo "Usage: ./scripts/test-relay-ws.sh [--python|--node]"
    exit 1
    ;;
esac

echo "Choose WebSocket test implementation:"
echo "  1) Python (via uv)"
echo "  2) Node"
read -r -p "Enter 1 or 2: " choice

case "$choice" in
  1)
    run_python
    ;;
  2)
    run_node
    ;;
  *)
    echo "Invalid choice: $choice (expected 1 or 2)"
    exit 1
    ;;
esac
