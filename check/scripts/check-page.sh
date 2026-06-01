#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/repo-paths.sh"
source "$SCRIPT_DIR/check-thread-account.sh"
CHECK_ROOT="${CHECK_ROOT:-$(check_detect_repo_root "$PWD")}"
CHECK_CONFIG="${CHECK_CONFIG:-$(check_repo_dir "$CHECK_ROOT")/config.env}"
TARGET_INPUT="${1:-/dashboard}"
OUTPUT_NAME="${2:-}"
export CHECK_ROOT CHECK_CONFIG

"$SCRIPT_DIR/setup-check-repo.sh"

CHECK_ACCOUNT_TARGET_OVERRIDE="${CHECK_ACCOUNT_TARGET-}"
CHECK_ACCOUNT_STRATEGY_OVERRIDE="${CHECK_ACCOUNT_STRATEGY-}"
CHECK_EMAIL_OVERRIDE="${CHECK_EMAIL-}"
CHECK_HENRY_EMAIL_OVERRIDE="${CHECK_HENRY_EMAIL-}"
CHECK_SESSION_KEY_OVERRIDE="${CHECK_SESSION_KEY-}"
CHECK_STATE_FILE_OVERRIDE="${CHECK_STATE_FILE-}"

# shellcheck disable=SC1090
source "$CHECK_CONFIG"

if [[ -n "${CHECK_ACCOUNT_TARGET_OVERRIDE:-}" ]]; then
  CHECK_ACCOUNT_TARGET="$CHECK_ACCOUNT_TARGET_OVERRIDE"
fi
if [[ -n "${CHECK_ACCOUNT_STRATEGY_OVERRIDE:-}" ]]; then
  CHECK_ACCOUNT_STRATEGY="$CHECK_ACCOUNT_STRATEGY_OVERRIDE"
fi
if [[ -n "${CHECK_EMAIL_OVERRIDE:-}" ]]; then
  CHECK_EMAIL="$CHECK_EMAIL_OVERRIDE"
fi
if [[ -n "${CHECK_HENRY_EMAIL_OVERRIDE:-}" ]]; then
  CHECK_HENRY_EMAIL="$CHECK_HENRY_EMAIL_OVERRIDE"
fi
if [[ -n "${CHECK_SESSION_KEY_OVERRIDE:-}" ]]; then
  CHECK_SESSION_KEY="$CHECK_SESSION_KEY_OVERRIDE"
fi
if [[ -n "${CHECK_STATE_FILE_OVERRIDE:-}" ]]; then
  CHECK_STATE_FILE="$CHECK_STATE_FILE_OVERRIDE"
fi

CHECK_REPO_DIR="${CHECK_REPO_DIR:-$(check_repo_dir "$CHECK_ROOT")}"
CHECK_EMAIL="$(check_resolve_check_email)"
CHECK_STATE_FILE="$(check_resolve_state_file)"
export CHECK_EMAIL CHECK_STATE_FILE

resolve_path() {
  local value="$1"
  if [[ "$value" = /* ]]; then
    printf '%s\n' "$value"
  else
    printf '%s\n' "$CHECK_ROOT/$value"
  fi
}

CHECK_BASE_URL="${CHECK_BASE_URL:-http://127.0.0.1:3000}"
CHECK_OUTPUT_DIR="${CHECK_OUTPUT_DIR:-$CHECK_REPO_DIR/output}"
CHECK_AUTH_STRATEGY="${CHECK_AUTH_STRATEGY:-interactive-playwright}"
CHECK_SKIP_AUTH_STATE="${CHECK_SKIP_AUTH_STATE:-false}"

CHECK_STATE_FILE_ABS="$(resolve_path "$CHECK_STATE_FILE")"
CHECK_OUTPUT_DIR_ABS="$(resolve_path "$CHECK_OUTPUT_DIR")"
mkdir -p "$CHECK_OUTPUT_DIR_ABS"

if [[ "$TARGET_INPUT" == http://* || "$TARGET_INPUT" == https://* ]]; then
  TARGET_URL="$TARGET_INPUT"
  TARGET_LABEL="$TARGET_INPUT"
else
  TARGET_URL="${CHECK_BASE_URL}${TARGET_INPUT}"
  TARGET_LABEL="$TARGET_INPUT"
fi

if [[ -z "$OUTPUT_NAME" ]]; then
  OUTPUT_NAME="$(printf '%s' "$TARGET_LABEL" | sed 's#^https\?://##' | tr '/:?&=' '-' | tr -s '-' | sed 's/^-//; s/-$//')"
  OUTPUT_NAME="${OUTPUT_NAME:-root}"
fi

SHOT_FILE="$CHECK_OUTPUT_DIR_ABS/${OUTPUT_NAME}.png"

PLAYWRIGHT_STORAGE_ARGS=()
if [[ "$CHECK_SKIP_AUTH_STATE" != "true" && "$CHECK_AUTH_STRATEGY" != "none" ]]; then
  "$SCRIPT_DIR/ensure-auth-state.sh"
  PLAYWRIGHT_STORAGE_ARGS=(--load-storage "$CHECK_STATE_FILE_ABS")
fi

if ((${#PLAYWRIGHT_STORAGE_ARGS[@]})); then
  STORAGE_ARGS=("${PLAYWRIGHT_STORAGE_ARGS[@]}")
else
  STORAGE_ARGS=()
fi

npx playwright screenshot \
  --browser chromium \
  --full-page \
  --wait-for-timeout 1500 \
  "${STORAGE_ARGS[@]+"${STORAGE_ARGS[@]}"}" \
  "$TARGET_URL" \
  "$SHOT_FILE"

echo "Saved screenshot to $SHOT_FILE"
