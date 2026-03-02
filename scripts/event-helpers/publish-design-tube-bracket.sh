#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="${SCRIPT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"
REPO_ROOT="${REPO_ROOT:-$(cd "$SCRIPT_DIR/../.." && pwd)}"
cd "$REPO_ROOT"

INDEXER_DIR="$REPO_ROOT/apps/indexer"
DESIGN_JSON="$REPO_ROOT/apps/client/public/temp-design-storage/tube-bracket/design.json"

# 1) Generate and export a fresh dev key (nsec) into env
export "$(cd "$INDEXER_DIR" && uv run openprints-cli keygen --env)"

prefix=$(echo "${OPENPRINTS_DEV_NSEC:-}" | cut -c1-5)
if [[ "$prefix" != "nsec1" ]]; then
  echo "Unexpected key prefix: $prefix (expected nsec1)"
  exit 1
fi

# 2) Load design data from design.json
NAME=$(jq -r '.name' "$DESIGN_JSON")
DESCRIPTION=$(jq -r '.description' "$DESIGN_JSON")
FORMAT=$(jq -r '.format' "$DESIGN_JSON")
SHA256=$(jq -r '.sha256' "$DESIGN_JSON")
URL=$(jq -r '.url' "$DESIGN_JSON")

# 3) Build, inject preview tags, sign, and publish the design
#    We keep cli-build-design/cli-sign/cli-publish-design as-is and use jq to
#    add ["preview", "<url>"] tags based on the design.json preview array.

# Read preview array once as JSON (or [] if missing)
PREVIEWS_JSON=$(jq -c '.preview // []' "$DESIGN_JSON")

NAME="$NAME" \
FORMAT="$FORMAT" \
URL="$URL" \
CONTENT="$DESCRIPTION" \
SHA256="$SHA256" \
  make cli-build-design \
  | jq --arg previews "$PREVIEWS_JSON" \
       '.event.tags += (( $previews | fromjson ) | map(["preview", .]))' \
   | make cli-sign \
   | make cli-publish-design

read -r -p "Attach kind0 identity event for this identity? [y/N] " attach_identity
echo
if [[ "$attach_identity" =~ ^[yY] ]]; then
  "$REPO_ROOT/scripts/event-helpers/publish-identity-kind0.sh"
fi

