#!/usr/bin/env python3
import argparse
import base64
import hmac
import hashlib
import os
import struct
import sys
import time
from pathlib import Path
from typing import Dict, Optional


def read_env_file(path: Path) -> Dict[str, str]:
    values = {}
    if not path.exists():
        return values

    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")

    return values


def totp(secret: str, timestamp: Optional[int] = None) -> str:
    clean_secret = "".join(secret.split()).upper()
    padding = "=" * ((8 - len(clean_secret) % 8) % 8)
    key = base64.b32decode(clean_secret + padding, casefold=True)
    counter = int((timestamp or time.time()) // 30)
    digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return f"{code % 1_000_000:06d}"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate a Google Authenticator-compatible TOTP code."
    )
    parser.add_argument(
        "--min-remaining",
        type=int,
        default=0,
        help=(
            "Wait for the next 30-second TOTP window when the current code has "
            "fewer than this many seconds remaining."
        ),
    )
    args = parser.parse_args()

    if args.min_remaining < 0 or args.min_remaining > 29:
        print("--min-remaining must be between 0 and 29.", file=sys.stderr)
        return 2

    repo_root = Path(os.environ.get("CHECK_EXPO_REPO_ROOT", os.getcwd()))
    skill_root = Path(__file__).resolve().parents[1]
    default_env_path = skill_root / "secrets" / "google-totp.env"
    legacy_repo_env_path = repo_root / ".codex-google-totp.env"
    env_path = Path(os.environ.get("GOOGLE_TOTP_ENV", default_env_path))

    values = read_env_file(env_path)
    if not values and env_path == default_env_path:
        values = read_env_file(legacy_repo_env_path)

    secret = os.environ.get("GOOGLE_TOTP_SECRET") or values.get("GOOGLE_TOTP_SECRET")

    if not secret:
        print(
            "GOOGLE_TOTP_SECRET not found. Set it in "
            f"{env_path}, {legacy_repo_env_path}, or the environment.",
            file=sys.stderr,
        )
        return 1

    now = int(time.time())
    remaining = 30 - (now % 30)
    if args.min_remaining and remaining < args.min_remaining:
        time.sleep(remaining + 1)
        now = int(time.time())

    print(totp(secret, now))
    print(f"seconds_remaining={30 - (now % 30)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
