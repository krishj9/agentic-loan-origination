#!/usr/bin/env bash
# load_env.sh — Source environment variables for local development.
#
# Usage:
#   source scripts/load_env.sh [package]
#
# Examples:
#   source scripts/load_env.sh           # loads backend/.env by default
#   source scripts/load_env.sh backend   # loads backend/.env
#   source scripts/load_env.sh agents    # loads agents/.env
#
# Rules:
#   - Only loads .env files that exist (no error on missing file).
#   - Prints a summary of variables loaded (names only, never values).
#   - NEVER prints secret values to stdout.
#   - The root .env (if present) is always loaded first, then the
#     package-specific .env overrides it.

set -euo pipefail

# Determine script directory reliably, handling both sourced and direct execution contexts
if [[ -n "${BASH_SOURCE[0]:-}" ]]; then
  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
else
  # Fallback for shells where BASH_SOURCE is not available (zsh, sourced in certain contexts)
  # Use PWD or current directory as best guess
  SCRIPT_DIR="$(pwd)"
  # Check if we're in the scripts directory
  if [[ "$(basename "$SCRIPT_DIR")" != "scripts" ]]; then
    # If we're not in scripts/, try to find it
    if [[ -d "./scripts" ]]; then
      SCRIPT_DIR="$(pwd)/scripts"
    elif [[ -d "../scripts" ]]; then
      SCRIPT_DIR="$(cd .. && pwd)/scripts"
    else
      echo "[load_env] ERROR: Could not determine scripts directory. Please run from repo root or scripts/ directory." >&2
      return 1 2>/dev/null || exit 1
    fi
  fi
fi

REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

TARGET="${1:-backend}"

load_env_file() {
  local env_file="$1"
  if [[ -f "$env_file" ]]; then
    echo "[load_env] Loading: $env_file"
    local count=0
    while IFS= read -r line || [[ -n "$line" ]]; do
      # Skip blank lines and comments
      [[ -z "$line" || "$line" == \#* ]] && continue
      # Only export KEY=VALUE pairs
      if [[ "$line" =~ ^([A-Za-z_][A-Za-z0-9_]*)= ]]; then
        export "$line"
        count=$((count + 1))
      fi
    done < "$env_file"
    echo "[load_env] Loaded $count variable(s) from $(basename "$env_file")."
  else
    echo "[load_env] No .env file found at $env_file — skipping."
  fi
}

# 1. Load repo-root .env if present (shared overrides)
load_env_file "${REPO_ROOT}/.env"

# 2. Load package-specific .env
load_env_file "${REPO_ROOT}/${TARGET}/.env"

echo "[load_env] Done. AWS_REGION=${AWS_REGION:-<not set>}, APP_ENV=${APP_ENV:-<not set>}, RUNTIME_MODE=${RUNTIME_MODE:-<not set>}"
echo "[load_env] Secret values (API keys, tokens) are NOT echoed — check your .env file directly."
