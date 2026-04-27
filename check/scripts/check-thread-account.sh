#!/usr/bin/env bash

check_trim() {
  local value="${1:-}"
  value="${value#"${value%%[![:space:]]*}"}"
  value="${value%"${value##*[![:space:]]}"}"
  printf '%s\n' "$value"
}

check_slugify_account_key() {
  local value
  value="$(check_trim "$1")"
  value="$(printf '%s' "$value" | tr '[:upper:]' '[:lower:]' | tr -cs 'a-z0-9' '-')"
  value="${value#-}"
  value="${value%-}"

  if [[ -z "$value" ]]; then
    value="default"
  fi

  printf '%s\n' "${value:0:48}"
}

check_account_strategy() {
  local strategy
  strategy="$(check_trim "${CHECK_ACCOUNT_STRATEGY:-shared}")"
  strategy="$(printf '%s' "$strategy" | tr '[:upper:]' '[:lower:]')"

  if [[ -z "$strategy" ]]; then
    strategy="shared"
  fi

  printf '%s\n' "$strategy"
}

check_account_target() {
  local target
  target="$(check_trim "${CHECK_ACCOUNT_TARGET:-auto}")"
  target="$(printf '%s' "$target" | tr '[:upper:]' '[:lower:]')"

  if [[ -z "$target" ]]; then
    target="auto"
  fi

  printf '%s\n' "$target"
}

check_henry_email() {
  printf '%s\n' "${CHECK_HENRY_EMAIL:-henrymdeutsch@gmail.com}"
}

check_uses_thread_local_account() {
  local target strategy
  target="$(check_account_target)"

  if [[ "$target" == "henry" || "$target" == "shared" ]]; then
    return 1
  fi

  if [[ "$target" == "isolated" || "$target" == "thread-local" || "$target" == "thread-isolated" ]]; then
    return 0
  fi

  strategy="$(check_account_strategy)"
  [[ "$strategy" == "thread-local" || "$strategy" == "thread-isolated" ]]
}

check_resolve_session_key() {
  if [[ -n "${CHECK_SESSION_KEY:-}" ]]; then
    check_slugify_account_key "$CHECK_SESSION_KEY"
    return
  fi

  if [[ -n "${CODEX_THREAD_ID:-}" ]]; then
    check_slugify_account_key "$CODEX_THREAD_ID"
    return
  fi

  check_slugify_account_key "default"
}

check_resolve_check_email() {
  if ! check_uses_thread_local_account; then
    printf '%s\n' "${CHECK_EMAIL:-$(check_henry_email)}"
    return
  fi

  local repo_key email_prefix email_domain session_key local_part
  repo_key="$(check_slugify_account_key "${CHECK_REPO_KEY:-repo}")"
  email_prefix="$(check_slugify_account_key "${CHECK_LOCAL_USER_EMAIL_PREFIX:-codex-check}")"
  email_domain="$(check_trim "${CHECK_LOCAL_USER_EMAIL_DOMAIN:-check.local}")"
  session_key="$(check_resolve_session_key)"
  local_part="${email_prefix}+${repo_key}-${session_key}"
  printf '%s\n' "${local_part}@${email_domain}"
}

check_resolve_account_name() {
  if ! check_uses_thread_local_account; then
    printf '%s\n' "${CHECK_ACCOUNT_DISPLAY_NAME:-Henry Check}"
    return
  fi

  local name_prefix session_key
  name_prefix="$(check_trim "${CHECK_LOCAL_USER_NAME_PREFIX:-Codex Check}")"
  session_key="$(check_resolve_session_key)"
  printf '%s\n' "${name_prefix} ${session_key}"
}

check_resolve_state_file() {
  if ! check_uses_thread_local_account; then
    printf '%s\n' "${CHECK_STATE_FILE:-$CHECK_REPO_DIR/state/henry-auth.json}"
    return
  fi

  local session_key
  session_key="$(check_resolve_session_key)"
  printf '%s/state/%s-auth.json\n' "$CHECK_REPO_DIR" "$session_key"
}
