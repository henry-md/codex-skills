#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ -x "/opt/homebrew/opt/python@3.13/bin/python3.13" ]]; then
  PYTHON="${VISUAL_DIFF_PYTHON:-/opt/homebrew/opt/python@3.13/bin/python3.13}"
else
  PYTHON="${VISUAL_DIFF_PYTHON:-python3}"
fi

exec "$PYTHON" "$SCRIPT_DIR/compare_page.py" "$@"
