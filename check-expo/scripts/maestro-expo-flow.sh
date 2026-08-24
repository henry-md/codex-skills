#!/usr/bin/env bash
set -euo pipefail

platform="ios"
device=""
repo_dir="$(pwd)"
flow=""
skill_dir="/Users/Henry/.codex/skills/check-expo"

usage() {
  cat <<'EOF'
Usage:
  maestro-expo-flow.sh --flow <flow.yaml> [--platform ios|android] [--device <udid-or-id>] [--repo <repo-dir>]

Runs a Maestro flow against an Expo app/emulator/simulator and stores artifacts under:
  /Users/Henry/.codex/skills/check-expo/repos/<repo-key>/

Examples:
  /Users/Henry/.codex/skills/check-expo/scripts/maestro-expo-flow.sh \
    --flow /Users/Henry/.codex/skills/check-expo/templates/maestro/ios-expo-overlay-close.yaml \
    --platform ios \
    --device 7EDA4327-C24A-4E2D-B7AC-CF587966F91E

  /Users/Henry/.codex/skills/check-expo/scripts/maestro-expo-flow.sh \
    --flow flows/smoke.yaml \
    --platform android
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --platform)
      platform="$2"
      shift 2
      ;;
    --device|--udid)
      device="$2"
      shift 2
      ;;
    --repo)
      repo_dir="$2"
      shift 2
      ;;
    --flow)
      flow="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ -z "$flow" ]]; then
  echo "Missing required --flow" >&2
  usage >&2
  exit 2
fi

repo_dir="$(cd "$repo_dir" && pwd)"
repo_key="$(basename "$repo_dir" | tr -cs 'A-Za-z0-9._-' '-')"
run_dir="$skill_dir/repos/$repo_key"
log_dir="$run_dir/logs/maestro"
output_dir="$run_dir/screenshots/maestro"

mkdir -p "$log_dir" "$output_dir"

export PATH="$PATH:$HOME/.maestro/bin"
export MAESTRO_CLI_NO_ANALYTICS=1
export MAESTRO_CLI_ANALYSIS_NOTIFICATION_DISABLED=true

if ! command -v maestro >/dev/null 2>&1; then
  echo "maestro=missing"
  echo "Install with: curl -Ls https://get.maestro.mobile.dev | bash"
  exit 127
fi

if [[ "$flow" != /* ]]; then
  flow="$repo_dir/$flow"
fi

echo "repo=$repo_dir"
echo "platform=$platform"
echo "device=${device:-auto}"
echo "flow=$flow"
echo "output_dir=$output_dir"
echo "debug_output=$log_dir"

maestro check-syntax "$flow"

args=(test --platform "$platform" --debug-output "$log_dir" --test-output-dir "$output_dir")
if [[ -n "$device" ]]; then
  args+=(--device "$device")
fi
args+=("$flow")

maestro "${args[@]}"
