#!/usr/bin/env bash
set -euo pipefail

platform="ios"
port="8082"
repo_dir="$(pwd)"
repo_key="$(basename "$repo_dir" | tr -cs 'A-Za-z0-9._-' '-')"
skill_dir="/Users/Henry/.codex/skills/check-expo"
run_dir="$skill_dir/repos/$repo_key"
log_dir="$run_dir/logs"
screenshot_dir="$run_dir/screenshots"
export_dir="$run_dir/exports/$platform"
metro_log="$log_dir/metro-$platform.log"
metro_pid_file="$run_dir/metro.pid"
screenshot_path="$screenshot_dir/${platform}-$(date +%Y%m%d-%H%M%S).png"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --platform)
      platform="$2"
      shift 2
      ;;
    --port)
      port="$2"
      shift 2
      ;;
    --repo)
      repo_dir="$2"
      shift 2
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

repo_dir="$(cd "$repo_dir" && pwd)"
repo_key="$(basename "$repo_dir" | tr -cs 'A-Za-z0-9._-' '-')"
run_dir="$skill_dir/repos/$repo_key"
log_dir="$run_dir/logs"
screenshot_dir="$run_dir/screenshots"
export_dir="$run_dir/exports/$platform"
metro_log="$log_dir/metro-$platform.log"
metro_pid_file="$run_dir/metro.pid"
screenshot_path="$screenshot_dir/${platform}-$(date +%Y%m%d-%H%M%S).png"

mkdir -p "$log_dir" "$screenshot_dir" "$(dirname "$export_dir")"

cd "$repo_dir"

echo "repo=$repo_dir"
echo "platform=$platform"
echo "port=$port"
echo "run_dir=$run_dir"

if [[ -f package.json ]]; then
  npm run typecheck --if-present
fi

npx expo install --check
npx expo-doctor
npx expo export --platform "$platform" --output-dir "$export_dir" --clear

if [[ -f "$metro_pid_file" ]] && kill -0 "$(cat "$metro_pid_file")" 2>/dev/null; then
  kill "$(cat "$metro_pid_file")" || true
fi

npx expo start --port "$port" --clear >"$metro_log" 2>&1 &
metro_pid="$!"
echo "$metro_pid" > "$metro_pid_file"
echo "metro_pid=$metro_pid"
echo "metro_log=$metro_log"

for _ in $(seq 1 40); do
  if grep -Eq "Metro waiting on|Waiting on http://|Web is waiting on" "$metro_log"; then
    break
  fi
  sleep 1
done

if ! grep -Eq "Metro waiting on|Waiting on http://|Web is waiting on" "$metro_log"; then
  echo "metro_ready=false"
  exit 1
fi

echo "metro_ready=true"

if [[ "$platform" == "ios" ]]; then
  if ! xcrun simctl list devices >/dev/null 2>&1; then
    echo "native_screenshot=blocked"
    echo "reason=simctl_unavailable"
    xcode-select -p || true
    xcrun simctl list devices || true
    exit 0
  fi

  if ! xcrun simctl list devices | grep -q "(Booted)"; then
    echo "native_screenshot=blocked"
    echo "reason=no_booted_ios_simulator"
    exit 0
  fi

  xcrun simctl openurl booted "exp://127.0.0.1:$port"
  sleep 8
  xcrun simctl io booted screenshot "$screenshot_path"
  echo "native_screenshot=captured"
  echo "screenshot=$screenshot_path"
elif [[ "$platform" == "android" ]]; then
  if ! command -v adb >/dev/null 2>&1; then
    echo "native_screenshot=blocked"
    echo "reason=adb_unavailable"
    exit 0
  fi

  adb start-server >/dev/null

  if ! adb devices | grep -q "device$"; then
    avd_name="${CHECK_EXPO_ANDROID_AVD:-}"
    if [[ -z "$avd_name" ]]; then
      first_avd_ini="$(find "$HOME/.android/avd" -maxdepth 1 -name "*.ini" -print 2>/dev/null | head -n 1 || true)"
      if [[ -n "$first_avd_ini" ]]; then
        avd_name="$(basename "$first_avd_ini" .ini)"
      fi
    fi
    if [[ -z "$avd_name" ]] && command -v emulator >/dev/null 2>&1; then
      avd_name="$(emulator -list-avds 2>/dev/null | grep -Ev '^(INFO|WARNING|ERROR)[[:space:]]' | head -n 1 || true)"
    fi

    if [[ -z "$avd_name" ]] || ! command -v emulator >/dev/null 2>&1; then
      echo "native_screenshot=blocked"
      echo "reason=no_android_device_or_avd"
      exit 0
    fi

    emulator -avd "$avd_name" -no-window -gpu swiftshader_indirect -no-audio -no-boot-anim -no-snapshot-load >"$log_dir/android-emulator.log" 2>&1 &
    emulator_pid="$!"
    echo "android_emulator_pid=$emulator_pid"
    echo "android_emulator_log=$log_dir/android-emulator.log"

    for _ in $(seq 1 90); do
      if adb devices | grep -q "device$"; then
        break
      fi
      if ! kill -0 "$emulator_pid" 2>/dev/null; then
        echo "native_screenshot=blocked"
        echo "reason=android_emulator_exited"
        tail -80 "$log_dir/android-emulator.log" || true
        exit 0
      fi
      sleep 2
    done
  fi

  if ! adb devices | grep -q "device$"; then
    echo "native_screenshot=blocked"
    echo "reason=android_emulator_not_visible_to_adb"
    exit 0
  fi

  for _ in $(seq 1 90); do
    if [[ "$(adb shell getprop sys.boot_completed 2>/dev/null | tr -d '\r')" == "1" ]]; then
      break
    fi
    sleep 2
  done

  if [[ "$(adb shell getprop sys.boot_completed 2>/dev/null | tr -d '\r')" != "1" ]]; then
    echo "native_screenshot=blocked"
    echo "reason=android_emulator_not_booted"
    exit 0
  fi

  adb shell am start -a android.intent.action.VIEW -d "exp://10.0.2.2:$port" >/dev/null || true
  sleep 10
  adb exec-out screencap -p > "$screenshot_path"
  echo "native_screenshot=captured"
  echo "screenshot=$screenshot_path"
else
  echo "native_screenshot=blocked"
  echo "reason=unsupported_platform"
fi
