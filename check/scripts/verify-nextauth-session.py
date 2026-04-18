#!/usr/bin/env python3
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


def load_cookie_header(storage_path: Path, session_url: str) -> str:
    storage = json.loads(storage_path.read_text())
    host = urllib.parse.urlparse(session_url).hostname or ""
    cookie_pairs: list[str] = []

    for cookie in storage.get("cookies", []):
        domain = str(cookie.get("domain", "")).lstrip(".")
        if domain and domain != host and not host.endswith(f".{domain}"):
            continue

        name = cookie.get("name")
        value = cookie.get("value")
        if name and value is not None:
            cookie_pairs.append(f"{name}={value}")

    if not cookie_pairs:
        raise SystemExit(f"No cookies in {storage_path} matched host {host}.")

    return "; ".join(cookie_pairs)


def main() -> int:
    if len(sys.argv) != 4:
        print(
            "Usage: verify-nextauth-session.py <storage-state> <session-url> <expected-email>",
            file=sys.stderr,
        )
        return 2

    storage_path = Path(sys.argv[1])
    session_url = sys.argv[2]
    expected_email = sys.argv[3]

    if not storage_path.exists():
        print(f"Storage state file not found: {storage_path}", file=sys.stderr)
        return 1

    cookie_header = load_cookie_header(storage_path, session_url)
    request = urllib.request.Request(
        session_url,
        headers={
            "Accept": "application/json",
            "Cookie": cookie_header,
        },
    )

    try:
        with urllib.request.urlopen(request) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as error:
        print(f"Unable to load {session_url}: {error}", file=sys.stderr)
        return 1

    actual_email = (
        payload.get("user", {}).get("email")
        if isinstance(payload, dict)
        else None
    )
    if actual_email != expected_email:
        print(
            f"Expected {expected_email} but session resolved to {actual_email!r}.",
            file=sys.stderr,
        )
        return 1

    print(f"Verified NextAuth session for {actual_email}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
