#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/repo-paths.sh"
CHECK_ROOT="${CHECK_ROOT:-$(check_detect_repo_root "$PWD")}"
CHECK_REPO_DIR="${CHECK_REPO_DIR:-$(check_repo_dir "$CHECK_ROOT")}"
CHECK_CONFIG="${CHECK_CONFIG:-$CHECK_REPO_DIR/config.env}"
CHECK_WORKFLOW="$CHECK_REPO_DIR/workflow.md"

mkdir -p "$CHECK_REPO_DIR"

detect_env_file() {
  local candidate

  for candidate in .env .env.local .env.development .env.development.local; do
    if [[ -f "$CHECK_ROOT/$candidate" ]]; then
      printf '%s\n' "$candidate"
      return
    fi
  done

  printf '%s\n' ".env"
}

detect_prisma_client_path() {
  local candidate

  for candidate in \
    generated/prisma/client.ts \
    generated/prisma/client.js \
    generated/prisma/client.mjs
  do
    if [[ -f "$CHECK_ROOT/$candidate" ]]; then
      printf '%s\n' "$candidate"
      return
    fi
  done

  printf '%s\n' ""
}

detect_auth_strategy() {
  local prisma_client_path="$1"

  if rg -l --quiet "next-auth|NextAuth|getServerSession|PrismaAdapter" \
    "$CHECK_ROOT" \
    --glob '!node_modules/**' \
    --glob '!agent-docs/check/**'; then
    if [[ -n "$prisma_client_path" ]]; then
      printf '%s\n' "nextauth-prisma"
      return
    fi
  fi

  printf '%s\n' "interactive-playwright"
}

detect_adapter_package() {
  if rg -l --quiet "@prisma/adapter-pg" \
    "$CHECK_ROOT/package.json" \
    "$CHECK_ROOT/package-lock.json" \
    "$CHECK_ROOT/pnpm-lock.yaml" 2>/dev/null; then
    printf '%s\n' "@prisma/adapter-pg"
    return
  fi

  printf '%s\n' ""
}

detect_adapter_export() {
  local adapter_package="$1"

  if [[ "$adapter_package" == "@prisma/adapter-pg" ]]; then
    printf '%s\n' "PrismaPg"
    return
  fi

  printf '%s\n' ""
}

if [[ ! -f "$CHECK_WORKFLOW" ]]; then
  cat >"$CHECK_WORKFLOW" <<EOF
Check notes for $(basename "$CHECK_ROOT")

- Repo root: $CHECK_ROOT
- Repo runtime dir: $CHECK_REPO_DIR
- Keep repo-specific assumptions here only when they do not belong in the global skill.
- Generated auth state belongs under \`$CHECK_REPO_DIR/state/\`.
- Generated screenshots belong under \`$CHECK_REPO_DIR/output/\`.
EOF
fi

if [[ ! -f "$CHECK_CONFIG" ]]; then
  CHECK_EMAIL="${CHECK_EMAIL:-henrymdeutsch@gmail.com}"
  CHECK_HENRY_EMAIL="${CHECK_HENRY_EMAIL:-henrymdeutsch@gmail.com}"
  CHECK_BASE_URL="${CHECK_BASE_URL:-http://127.0.0.1:3000}"
  CHECK_SESSION_URL="${CHECK_SESSION_URL:-$CHECK_BASE_URL/api/auth/session}"
  CHECK_STATE_FILE="${CHECK_STATE_FILE:-$CHECK_REPO_DIR/state/henry-auth.json}"
  CHECK_ACCOUNT_TARGET="${CHECK_ACCOUNT_TARGET:-auto}"
  CHECK_ACCOUNT_STRATEGY="${CHECK_ACCOUNT_STRATEGY:-shared}"
  CHECK_LOCAL_USER_EMAIL_PREFIX="${CHECK_LOCAL_USER_EMAIL_PREFIX:-codex-check}"
  CHECK_LOCAL_USER_EMAIL_DOMAIN="${CHECK_LOCAL_USER_EMAIL_DOMAIN:-check.local}"
  CHECK_LOCAL_USER_NAME_PREFIX="${CHECK_LOCAL_USER_NAME_PREFIX:-Codex Check}"
  CHECK_LOCAL_USER_AUTO_CREATE="${CHECK_LOCAL_USER_AUTO_CREATE:-false}"
  CHECK_ALLOW_SHARED_ACCOUNT_CLEANUP="${CHECK_ALLOW_SHARED_ACCOUNT_CLEANUP:-false}"
  CHECK_OUTPUT_DIR="${CHECK_OUTPUT_DIR:-$CHECK_REPO_DIR/output}"
  CHECK_DATABASE_ENV_FILE="${CHECK_DATABASE_ENV_FILE:-$(detect_env_file)}"
  CHECK_PRISMA_CLIENT_PATH="${CHECK_PRISMA_CLIENT_PATH:-$(detect_prisma_client_path)}"
  CHECK_AUTH_STRATEGY="${CHECK_AUTH_STRATEGY:-$(detect_auth_strategy "$CHECK_PRISMA_CLIENT_PATH")}"
  CHECK_PRISMA_ADAPTER_PACKAGE="${CHECK_PRISMA_ADAPTER_PACKAGE:-$(detect_adapter_package)}"
  CHECK_PRISMA_ADAPTER_EXPORT="${CHECK_PRISMA_ADAPTER_EXPORT:-$(detect_adapter_export "$CHECK_PRISMA_ADAPTER_PACKAGE")}"
  CHECK_REPO_KEY="${CHECK_REPO_KEY:-$(check_repo_key "$CHECK_ROOT")}"

  cat >"$CHECK_CONFIG" <<EOF
CHECK_ROOT="$CHECK_ROOT"
CHECK_REPO_KEY="$CHECK_REPO_KEY"
CHECK_REPO_DIR="$CHECK_REPO_DIR"
CHECK_EMAIL="$CHECK_EMAIL"
CHECK_HENRY_EMAIL="$CHECK_HENRY_EMAIL"
CHECK_BASE_URL="$CHECK_BASE_URL"
CHECK_SESSION_URL="$CHECK_SESSION_URL"
CHECK_STATE_FILE="$CHECK_STATE_FILE"
CHECK_ACCOUNT_TARGET="$CHECK_ACCOUNT_TARGET"
CHECK_ACCOUNT_STRATEGY="$CHECK_ACCOUNT_STRATEGY"
CHECK_LOCAL_USER_EMAIL_PREFIX="$CHECK_LOCAL_USER_EMAIL_PREFIX"
CHECK_LOCAL_USER_EMAIL_DOMAIN="$CHECK_LOCAL_USER_EMAIL_DOMAIN"
CHECK_LOCAL_USER_NAME_PREFIX="$CHECK_LOCAL_USER_NAME_PREFIX"
CHECK_LOCAL_USER_AUTO_CREATE="$CHECK_LOCAL_USER_AUTO_CREATE"
CHECK_ALLOW_SHARED_ACCOUNT_CLEANUP="$CHECK_ALLOW_SHARED_ACCOUNT_CLEANUP"
CHECK_OUTPUT_DIR="$CHECK_OUTPUT_DIR"
CHECK_AUTH_STRATEGY="$CHECK_AUTH_STRATEGY"
CHECK_DATABASE_ENV_FILE="$CHECK_DATABASE_ENV_FILE"
CHECK_PRISMA_CLIENT_PATH="$CHECK_PRISMA_CLIENT_PATH"
CHECK_PRISMA_ADAPTER_PACKAGE="$CHECK_PRISMA_ADAPTER_PACKAGE"
CHECK_PRISMA_ADAPTER_EXPORT="$CHECK_PRISMA_ADAPTER_EXPORT"
EOF
fi
