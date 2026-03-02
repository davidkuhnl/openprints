#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="${SCRIPT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"
REPO_ROOT="${REPO_ROOT:-$(cd "$SCRIPT_DIR/../.." && pwd)}"
cd "$REPO_ROOT"

INDEXER_DIR="$REPO_ROOT/apps/indexer"
PROFILE_JSON="$REPO_ROOT/apps/client/public/temp-identity-storage/profile-1.json"

if [[ ! -f "$PROFILE_JSON" ]]; then
  echo "Missing profile JSON: $PROFILE_JSON"
  exit 1
fi

# 1) Use currently exported dev key (no keygen here)
if [[ -z "${OPENPRINTS_DEV_NSEC:-}" ]]; then
  echo "OPENPRINTS_DEV_NSEC is not set. Export your current identity key first."
  exit 1
fi

prefix=$(echo "${OPENPRINTS_DEV_NSEC:-}" | cut -c1-5)
if [[ "$prefix" != "nsec1" ]]; then
  echo "Unexpected key prefix: $prefix (expected nsec1)"
  exit 1
fi

# 2) Build, sign, and publish identity metadata (kind 0) for current identity
PROFILE_FILE="$PROFILE_JSON" \
  make cli-build-identity \
  | make cli-sign \
  | make cli-publish-identity
