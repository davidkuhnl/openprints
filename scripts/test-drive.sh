#!/usr/bin/env bash
# End-to-end test drive: dev key, relay, indexer, publish designs + update, then tear down.
# Usage: ./scripts/test-drive.sh
# Run from repo root. You will be prompted to run the indexer and DB stats in another terminal.

set -euo pipefail
SCRIPT_DIR="${SCRIPT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"
REPO_ROOT="${REPO_ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}"
cd "$REPO_ROOT"

INDEXER_DIR="$REPO_ROOT/apps/indexer"
DB_PATH="$INDEXER_DIR/openprints.db"
DESIGN_ID_1="openprints:11111111-1111-4000-8000-000000000001"
DESIGN_ID_2="openprints:22222222-2222-4000-8000-000000000002"

# Colors (only when stdout is a terminal)
if [[ -t 1 ]]; then
  R='\033[0m'
  B='\033[1m'
  D='\033[2m'
  G='\033[32m'
  C='\033[36m'
else
  R=; B=; D=; G=; C=
fi

_sep() {
  echo -e "${D}────────────────────────────────────────────────────────${R}"
}

_step() {
  echo -e "\n${B}Step $1:${R} $2"
}

_cmd() {
  echo -e "  ${C}$1${R}"
}

_ok() {
  echo -e "${G}✔${R} $1"
}

_pause() {
  echo
  read -r -s -n 1 -p "Press any key to continue to the next step (Ctrl+C to stop the test drive)..."
  echo
  echo
}

_wait_enter() {
  echo
  read -r -p "Press Enter when $1 to continue (Ctrl+C to stop the test drive)..."
  echo
  echo
}

echo -e "\n${B}=== OpenPrints test drive ===${R}\n"
_sep

# --- 0) Wipe relay? (confirm) ---
_sep
_step 0 "Wipe the relay (stop + remove data volume) for a clean test?"
read -p "Run relay-down-wipe now? [y/N] " -r
echo
if [[ "$REPLY" =~ ^[yY] ]]; then
  make relay-down-wipe
  _ok "Relay wiped."
fi
_pause

# --- 1) Spin up relay ---
_sep
_step 1 "Starting relay..."
make relay-up
echo "Waiting for relay to be ready..."
sleep 2
_ok "Relay up."
_pause

# --- 2) Check relay OK ---
_sep
_step 2 "Checking relay health..."
make relay-test-up
_ok "Relay healthy."
_pause

# --- 3) Export dev key ---
_sep
_step 3 "Generating and exporting dev key..."
export "$(cd "$INDEXER_DIR" && uv run openprints-cli keygen --env)"
prefix=$(echo "$OPENPRINTS_DEV_NSEC" | cut -c1-5)
if [[ "$prefix" != "nsec1" ]]; then
  echo "Unexpected key prefix: $prefix (expected nsec1)"
  exit 1
fi
_ok "Key exported (prefix: nsec1...)."
_pause

# --- 4) DB exists? Offer to wipe ---
_sep
_step 4 "Indexer database (optional wipe for clean test)."
if [[ -f "$DB_PATH" ]]; then
  read -p "Indexer DB exists at $DB_PATH. Wipe it for a clean test? [y/N] " -r
  echo
  if [[ "$REPLY" =~ ^[yY] ]]; then
    make cli-db-wipe
    _ok "DB wiped."
  fi
else
  echo -e "${D}No existing DB at $DB_PATH.${R}"
fi
_pause

# --- 5) Ask user to run indexer ---
_sep
_step 5 "Start the indexer in another terminal:"
_cmd "make cli-index"
echo -e "${D}(Ensure database_path is set in apps/indexer/openprints.indexer.toml so events are persisted.)${R}"
_wait_enter "the indexer is running"

# --- 6) Ask user to run DB stats (initial) ---
_sep
_step 6 "In yet another terminal run:"
_cmd "make cli-db-stats"
echo "You should see 0 designs and 0 versions if we are starting with a fresh relay and DB wiped."
_wait_enter "done"

# --- 7) Publish first design + check stats ---
_sep
_step 7 "Publish first design, then run make cli-db-stats in the other terminal."
_cmd "make cli-db-stats"
echo "You should see 1 design, 1 version."
DESIGN_ID="$DESIGN_ID_1" make cli-build | make cli-sign | make cli-publish
_ok "First design published."
_wait_enter "you have checked the stats"

# --- 8) Publish second design + check stats ---
_sep
_step 8 "Publish second design, then run make cli-db-stats in the other terminal."
_cmd "make cli-db-stats"
echo "You should see 2 designs and 2 versions."
DESIGN_ID="$DESIGN_ID_2" NAME="Second Design" make cli-build | make cli-sign | make cli-publish
_ok "Second design published."
_wait_enter "you have checked the stats"

# --- 9) Publish update to first design + check stats ---
_sep
_step 9 "Publish an update to the first design (replaceable event), then run make cli-db-stats."
_cmd "make cli-db-stats"
echo "You should see 2 designs and 3 versions."
DESIGN_ID="$DESIGN_ID_1" NAME="First Design - updated" CONTENT="Updated description." make cli-build | make cli-sign | make cli-publish
_ok "Update published."
_wait_enter "you have checked the stats"

# --- 10) Tear down ---
_sep
_step 10 "Tear down."
read -p "Wipe relay volume and indexer DB? [y/N] " -r
echo
if [[ "$REPLY" =~ ^[yY] ]]; then
  make relay-down-wipe
  make cli-db-wipe
  _ok "Relay and DB wiped."
else
  make relay-down
  _ok "Relay stopped (volume and DB left as-is)."
fi
echo ""
echo -e "${D}The indexer should have shut down on relay disconnect.${R}"
echo -e "${D}If you had it running, its final output should show stats like:${R}"
echo -e "${D}  \"stats\": { \"processed\": 3, \"reduced\": 3, \"duplicates\": 0 }${R}"
echo ""
echo -e "\n${B}=== Test drive complete ===${R}"
