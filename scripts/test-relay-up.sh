#!/usr/bin/env bash
# Quick HTTP health check for the local Nostr relay.
# Usage: ./scripts/test-relay-up.sh [BASE_URL]
# Example: RELAY_BASE_URL=http://localhost:7447 ./scripts/test-relay-up.sh

set -e

RELAY_BASE_URL="${RELAY_BASE_URL:-http://localhost:7447}"

echo "Checking relay at ${RELAY_BASE_URL} ..."
code=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 3 "${RELAY_BASE_URL}/" || true)

if [[ -z "$code" || "$code" == "000" ]]; then
  echo "Relay is not up (HTTP ${code:-000} = no response: connection refused, timeout, or unreachable)."
  exit 1
fi

echo "Relay responded with HTTP ${code}."
if [[ "$code" == "200" || "$code" == "204" ]]; then
  echo "OK: relay is up."
  exit 0
fi

# Some relays return 400 for GET /; still means "listening"
if [[ "$code" -ge 400 ]]; then
  echo "OK: relay is up (HTTP ${code})."
  exit 0
fi

exit 0
