#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/repo-paths.sh"
source "$SCRIPT_DIR/check-thread-account.sh"
CHECK_ROOT="${CHECK_ROOT:-$(check_detect_repo_root "$PWD")}"
CHECK_CONFIG="${CHECK_CONFIG:-$(check_repo_dir "$CHECK_ROOT")/config.env}"
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
CHECK_LOCAL_USER_AUTO_CREATE="${CHECK_LOCAL_USER_AUTO_CREATE:-$(
  if check_uses_thread_local_account; then
    printf '%s' "true"
  else
    printf '%s' "false"
  fi
)}"
export CHECK_EMAIL CHECK_LOCAL_USER_AUTO_CREATE CHECK_STATE_FILE
export CHECK_ACCOUNT_RESOLVED_NAME="$(check_resolve_account_name)"

resolve_path() {
  local value="$1"
  if [[ "$value" = /* ]]; then
    printf '%s\n' "$value"
  else
    printf '%s\n' "$CHECK_ROOT/$value"
  fi
}

CHECK_BASE_URL="${CHECK_BASE_URL:-http://127.0.0.1:3000}"
CHECK_SESSION_URL="${CHECK_SESSION_URL:-$CHECK_BASE_URL/api/auth/session}"
CHECK_OUTPUT_DIR="${CHECK_OUTPUT_DIR:-$CHECK_REPO_DIR/output}"
CHECK_AUTH_STRATEGY="${CHECK_AUTH_STRATEGY:-interactive-playwright}"
CHECK_DATABASE_ENV_FILE="${CHECK_DATABASE_ENV_FILE:-.env}"
CHECK_PRISMA_CLIENT_PATH="${CHECK_PRISMA_CLIENT_PATH:-generated/prisma/client.ts}"
CHECK_PRISMA_ADAPTER_PACKAGE="${CHECK_PRISMA_ADAPTER_PACKAGE:-@prisma/adapter-pg}"
CHECK_PRISMA_ADAPTER_EXPORT="${CHECK_PRISMA_ADAPTER_EXPORT:-PrismaPg}"
CHECK_AUTH_VERIFY_STRATEGY="${CHECK_AUTH_VERIFY_STRATEGY:-nextauth-session}"
CHECK_AUTH_VERIFY_URL="${CHECK_AUTH_VERIFY_URL:-$CHECK_BASE_URL/dashboard}"
CHECK_AUTH_VERIFY_REQUIRED_TEXT="${CHECK_AUTH_VERIFY_REQUIRED_TEXT:-}"
CHECK_AUTH_VERIFY_FORBIDDEN_TEXT="${CHECK_AUTH_VERIFY_FORBIDDEN_TEXT:-}"
if [[ -z "${CHECK_PYTHON:-}" && -x "/opt/homebrew/opt/python@3.13/bin/python3.13" ]]; then
  CHECK_PYTHON="/opt/homebrew/opt/python@3.13/bin/python3.13"
fi
CHECK_PYTHON="${CHECK_PYTHON:-python3}"

CHECK_STATE_FILE_ABS="$(resolve_path "$CHECK_STATE_FILE")"
CHECK_OUTPUT_DIR_ABS="$(resolve_path "$CHECK_OUTPUT_DIR")"
CHECK_DATABASE_ENV_FILE_ABS="$(resolve_path "$CHECK_DATABASE_ENV_FILE")"

mkdir -p "$CHECK_OUTPUT_DIR_ABS" "$(dirname "$CHECK_STATE_FILE_ABS")"
chmod 700 "$(dirname "$CHECK_STATE_FILE_ABS")"

verify_auth_state() {
  case "$CHECK_AUTH_VERIFY_STRATEGY" in
    none)
      [[ -f "$CHECK_STATE_FILE_ABS" ]]
      ;;
    nextauth-session)
      "$CHECK_PYTHON" "$SCRIPT_DIR/verify-nextauth-session.py" \
        "$CHECK_STATE_FILE_ABS" \
        "$CHECK_SESSION_URL" \
        "$CHECK_EMAIL"
      ;;
    firebase-route|route)
      "$CHECK_PYTHON" "$SCRIPT_DIR/verify-route-storage-state.py" \
        "$CHECK_STATE_FILE_ABS" \
        "$CHECK_AUTH_VERIFY_URL" \
        "$CHECK_AUTH_VERIFY_REQUIRED_TEXT" \
        "$CHECK_AUTH_VERIFY_FORBIDDEN_TEXT"
      ;;
    *)
      echo "Unsupported CHECK_AUTH_VERIFY_STRATEGY: $CHECK_AUTH_VERIFY_STRATEGY" >&2
      return 1
      ;;
  esac
}

if verify_auth_state; then
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

verify_auth_state
