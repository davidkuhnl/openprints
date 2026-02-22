#!/usr/bin/env bash
# Bootstrap script: check prerequisites and run idempotent in-repo setup.
# Usage: ./scripts/setup.sh
# Run from repo root.

set -euo pipefail
SCRIPT_DIR="${SCRIPT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"
REPO_ROOT="${REPO_ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}"
cd "$REPO_ROOT"

MISSING=()
HINTS=()

# --- Git ---
if ! command -v git &>/dev/null; then
  MISSING+=(git)
  HINTS+=("Git: https://git-scm.com/book/en/v2/Getting-Started-Installing-Git")
fi

# --- Docker + Docker Compose ---
if ! command -v docker &>/dev/null; then
  MISSING+=(Docker)
  HINTS+=("Docker: https://docs.docker.com/get-docker/")
fi
if command -v docker &>/dev/null && ! docker compose version &>/dev/null; then
  MISSING+=("Docker Compose")
  HINTS+=("Docker Compose: https://docs.docker.com/compose/install/")
fi

# --- Python 3.11+ ---
PYTHON=
for cmd in python3 python; do
  if command -v "$cmd" &>/dev/null; then
    PYTHON=$cmd
    break
  fi
done
if [[ -z "$PYTHON" ]]; then
  MISSING+=(Python)
  HINTS+=("Python 3.11+: https://www.python.org/downloads/ or your system package manager")
else
  MAJOR=$("$PYTHON" -c "import sys; print(sys.version_info.major)" 2>/dev/null || echo 0)
  MINOR=$("$PYTHON" -c "import sys; print(sys.version_info.minor)" 2>/dev/null || echo 0)
  if [[ "$MAJOR" -lt 3 ]] || { [[ "$MAJOR" -eq 3 ]] && [[ "$MINOR" -lt 11 ]]; }; then
    MISSING+=("Python 3.11+ (found $($PYTHON --version 2>&1))")
    HINTS+=("Python 3.11+: https://www.python.org/downloads/ or uv: https://github.com/astral-sh/uv")
  fi
fi

# --- uv ---
if ! command -v uv &>/dev/null; then
  MISSING+=(uv)
  HINTS+=("uv: curl -LsSf https://astral.sh/uv/install.sh | sh  (or brew install uv)")
fi

# --- Node 20+ ---
if ! command -v node &>/dev/null; then
  MISSING+=(Node.js)
  HINTS+=("Node 20+: https://nodejs.org/ or nvm/fnm/volta")
else
  NODE_MAJOR=$(node -e "console.log(process.versions.node.split('.')[0])" 2>/dev/null || echo 0)
  if [[ "${NODE_MAJOR:-0}" -lt 20 ]]; then
    MISSING+=("Node 20+ (found $(node --version))")
    HINTS+=("Node 20+: https://nodejs.org/ or nvm/fnm/volta")
  fi
fi

# --- npm or pnpm ---
if ! command -v npm &>/dev/null && ! command -v pnpm &>/dev/null; then
  MISSING+=(npm or pnpm)
  HINTS+=("npm comes with Node.js; pnpm: npm install -g pnpm")
fi

# --- Report missing ---
if [[ ${#MISSING[@]} -gt 0 ]]; then
  echo "Missing or insufficient prerequisites:"
  for i in "${!MISSING[@]}"; do
    echo "  - ${MISSING[$i]}"
    echo "    ${HINTS[$i]}"
  done
  echo ""
  echo "Install the above, then run ./scripts/setup.sh again."
  exit 1
fi

echo "Prerequisites OK (git, docker, python, uv, node, npm/pnpm)."
echo ""

# --- In-repo setup (idempotent) ---
if [[ -f "$REPO_ROOT/apps/indexer/pyproject.toml" ]]; then
  echo "Setting up indexer (uv sync)..."
  (cd "$REPO_ROOT/apps/indexer" && uv sync)
  echo "Indexer deps ready."
elif [[ -f "$REPO_ROOT/apps/indexer/requirements.txt" ]]; then
  echo "Setting up indexer (uv pip install)..."
  (cd "$REPO_ROOT/apps/indexer" && uv pip install -r requirements.txt)
  echo "Indexer deps ready."
fi

if [[ -f "$REPO_ROOT/apps/client/package.json" ]]; then
  echo "Setting up client..."
  if [[ -f "$REPO_ROOT/apps/client/pnpm-lock.yaml" ]]; then
    (cd "$REPO_ROOT/apps/client" && pnpm install)
  else
    (cd "$REPO_ROOT/apps/client" && npm install)
  fi
  echo "Client deps ready."
fi

# --- Git hooks (pre-commit) ---
if [[ -d "$REPO_ROOT/.git" ]]; then
  echo "Installing pre-commit hook..."
  if command -v pre-commit &>/dev/null; then
    if pre-commit install; then
      echo "pre-commit hook installed via local pre-commit binary."
    else
      echo "Warning: pre-commit install failed. You can run it manually later."
    fi
  else
    # Use uv in project context so setup stays reproducible without global tool installs.
    if [[ -f "$REPO_ROOT/apps/indexer/pyproject.toml" ]]; then
      if (cd "$REPO_ROOT/apps/indexer" && uv run --with pre-commit pre-commit install); then
        echo "pre-commit hook installed via uv (project context)."
      else
        echo "Warning: pre-commit install via uv failed. You can run it manually later."
      fi
    else
      echo "Skipping pre-commit hook install: no project context available for uv fallback."
    fi
  fi
else
  echo "Skipping pre-commit hook install (not a git checkout)."
fi

echo ""
echo "Setup complete."
echo "Next: run 'make relay-up' then 'make relay-check' to verify relay health."
