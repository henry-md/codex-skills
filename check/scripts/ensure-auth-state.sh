#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/repo-paths.sh"
CHECK_ROOT="${CHECK_ROOT:-$(check_detect_repo_root "$PWD")}"
CHECK_CONFIG="${CHECK_CONFIG:-$(check_repo_dir "$CHECK_ROOT")/config.env}"
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
CHECK_EMAIL="${CHECK_EMAIL:-henrymdeutsch@gmail.com}"
CHECK_BASE_URL="${CHECK_BASE_URL:-http://127.0.0.1:3000}"
CHECK_SESSION_URL="${CHECK_SESSION_URL:-$CHECK_BASE_URL/api/auth/session}"
CHECK_STATE_FILE="${CHECK_STATE_FILE:-$CHECK_REPO_DIR/state/henry-auth.json}"
CHECK_OUTPUT_DIR="${CHECK_OUTPUT_DIR:-$CHECK_REPO_DIR/output}"
CHECK_AUTH_STRATEGY="${CHECK_AUTH_STRATEGY:-interactive-playwright}"
CHECK_DATABASE_ENV_FILE="${CHECK_DATABASE_ENV_FILE:-.env}"
CHECK_PRISMA_CLIENT_PATH="${CHECK_PRISMA_CLIENT_PATH:-generated/prisma/client.ts}"
CHECK_PRISMA_ADAPTER_PACKAGE="${CHECK_PRISMA_ADAPTER_PACKAGE:-@prisma/adapter-pg}"
CHECK_PRISMA_ADAPTER_EXPORT="${CHECK_PRISMA_ADAPTER_EXPORT:-PrismaPg}"

CHECK_STATE_FILE_ABS="$(resolve_path "$CHECK_STATE_FILE")"
CHECK_OUTPUT_DIR_ABS="$(resolve_path "$CHECK_OUTPUT_DIR")"
CHECK_DATABASE_ENV_FILE_ABS="$(resolve_path "$CHECK_DATABASE_ENV_FILE")"

mkdir -p "$CHECK_OUTPUT_DIR_ABS" "$(dirname "$CHECK_STATE_FILE_ABS")"
chmod 700 "$(dirname "$CHECK_STATE_FILE_ABS")"

if python3 "$SCRIPT_DIR/verify-nextauth-session.py" \
  "$CHECK_STATE_FILE_ABS" \
  "$CHECK_SESSION_URL" \
  "$CHECK_EMAIL"; then
  exit 0
fi

rm -f "$CHECK_STATE_FILE_ABS"

case "$CHECK_AUTH_STRATEGY" in
  nextauth-prisma)
    NODE_ARGS=(--experimental-strip-types)
    if [[ -f "$CHECK_DATABASE_ENV_FILE_ABS" ]]; then
      NODE_ARGS=(--env-file="$CHECK_DATABASE_ENV_FILE_ABS" "${NODE_ARGS[@]}")
    fi

    node "${NODE_ARGS[@]}" \
      "$SCRIPT_DIR/seed-nextauth-prisma-state.mjs" \
      "$CHECK_ROOT" \
      "$CHECK_STATE_FILE" \
      "$CHECK_BASE_URL" \
      "$CHECK_EMAIL" \
      "$CHECK_PRISMA_CLIENT_PATH" \
      "$CHECK_PRISMA_ADAPTER_PACKAGE" \
      "$CHECK_PRISMA_ADAPTER_EXPORT"
    ;;
  command)
    if [[ -z "${CHECK_AUTH_REFRESH_COMMAND:-}" ]]; then
      echo "CHECK_AUTH_REFRESH_COMMAND is required when CHECK_AUTH_STRATEGY=command" >&2
      exit 1
    fi
    eval "$CHECK_AUTH_REFRESH_COMMAND"
    ;;
  interactive-playwright)
    npx playwright open \
      --browser chromium \
      --save-storage "$CHECK_STATE_FILE_ABS" \
      "$CHECK_BASE_URL"
    ;;
  *)
    echo "Unsupported CHECK_AUTH_STRATEGY: $CHECK_AUTH_STRATEGY" >&2
    exit 1
    ;;
esac

chmod 600 "$CHECK_STATE_FILE_ABS"

python3 "$SCRIPT_DIR/verify-nextauth-session.py" \
  "$CHECK_STATE_FILE_ABS" \
  "$CHECK_SESSION_URL" \
  "$CHECK_EMAIL"
