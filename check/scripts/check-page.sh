#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/repo-paths.sh"
CHECK_ROOT="${CHECK_ROOT:-$(check_detect_repo_root "$PWD")}"
CHECK_CONFIG="${CHECK_CONFIG:-$(check_repo_dir "$CHECK_ROOT")/config.env}"
TARGET_INPUT="${1:-/dashboard}"
OUTPUT_NAME="${2:-}"
export CHECK_ROOT CHECK_CONFIG

"$SCRIPT_DIR/setup-check-repo.sh"

# shellcheck disable=SC1090
source "$CHECK_CONFIG"

resolve_path() {
  local value="$1"
  if [[ "$value" = /* ]]; then
    printf '%s\n' "$value"
  else
    printf '%s\n' "$CHECK_ROOT/$value"
  fi
}

CHECK_REPO_DIR="${CHECK_REPO_DIR:-$(check_repo_dir "$CHECK_ROOT")}"
CHECK_BASE_URL="${CHECK_BASE_URL:-http://127.0.0.1:3000}"
CHECK_STATE_FILE="${CHECK_STATE_FILE:-$CHECK_REPO_DIR/state/henry-auth.json}"
CHECK_OUTPUT_DIR="${CHECK_OUTPUT_DIR:-$CHECK_REPO_DIR/output}"

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

"$SCRIPT_DIR/ensure-auth-state.sh"

npx playwright screenshot \
  --browser chromium \
  --full-page \
  --wait-for-timeout 1500 \
  --load-storage "$CHECK_STATE_FILE_ABS" \
  "$TARGET_URL" \
  "$SHOT_FILE"

echo "Saved screenshot to $SHOT_FILE"
