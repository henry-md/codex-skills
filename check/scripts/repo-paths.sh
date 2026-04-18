#!/usr/bin/env bash

check_detect_repo_root() {
  local start_dir="${1:-$PWD}"

  if git -C "$start_dir" rev-parse --show-toplevel >/dev/null 2>&1; then
    git -C "$start_dir" rev-parse --show-toplevel
    return
  fi

  printf '%s\n' "$start_dir"
}

check_skill_dir() {
  local helper_dir
  helper_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
  printf '%s\n' "$helper_dir"
}

check_repo_hash() {
  local value="$1"

  if command -v shasum >/dev/null 2>&1; then
    printf '%s' "$value" | shasum | awk '{print substr($1, 1, 12)}'
    return
  fi

  printf '%s' "$value" | sha1sum | awk '{print substr($1, 1, 12)}'
}

check_repo_slug() {
  local value="$1"
  printf '%s\n' "$value" | tr '[:upper:]' '[:lower:]' | tr -cs 'a-z0-9' '-' | sed 's/^-//; s/-$//'
}

check_repo_key() {
  local repo_root="$1"
  local repo_name repo_hash

  repo_name="$(check_repo_slug "$(basename "$repo_root")")"
  repo_hash="$(check_repo_hash "$repo_root")"
  printf '%s-%s\n' "${repo_name:-repo}" "$repo_hash"
}

check_repo_dir() {
  local repo_root="$1"
  local skill_dir repo_key

  skill_dir="$(check_skill_dir)"
  repo_key="$(check_repo_key "$repo_root")"
  printf '%s/repos/%s\n' "$skill_dir" "$repo_key"
}
