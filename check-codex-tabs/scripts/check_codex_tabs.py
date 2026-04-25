#!/usr/bin/env python3
"""Summarize unarchived Codex threads and classify which ones are still active."""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inspect local Codex state and classify open tabs by status.",
    )
    parser.add_argument(
        "--cwd",
        help="Filter to an exact thread cwd, usually the repo root.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=40,
        help="Maximum number of unarchived threads to inspect (default: 40).",
    )
    parser.add_argument(
        "--active-only",
        action="store_true",
        help="Show only unfinished tabs.",
    )
    parser.add_argument(
        "--state-db",
        help="Override the Codex state database path.",
    )
    return parser.parse_args()


def resolve_codex_home() -> Path:
    raw = os.environ.get("CODEX_HOME")
    if raw:
        return Path(raw).expanduser()
    return Path.home() / ".codex"


def resolve_state_db(codex_home: Path, override: str | None) -> Path:
    if override:
        path = Path(override).expanduser()
        if path.exists():
            return path
        raise FileNotFoundError(f"State database not found: {path}")

    preferred = codex_home / "state_5.sqlite"
    if preferred.exists():
        return preferred

    candidates = sorted(
        codex_home.glob("state_*.sqlite"),
        key=lambda path: (path.stat().st_mtime, path.name),
        reverse=True,
    )
    if candidates:
        return candidates[0]

    raise FileNotFoundError(
        f"No state_*.sqlite file found under {codex_home}",
    )


def normalize_text(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.split())


def format_timestamp(unix_seconds: object) -> str:
    if not isinstance(unix_seconds, int):
        return ""
    return datetime.fromtimestamp(unix_seconds).strftime("%Y-%m-%d %H:%M:%S")


def read_last_nonempty_line(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None

    with path.open("rb") as handle:
        handle.seek(0, os.SEEK_END)
        position = handle.tell()
        buffer = b""

        while position > 0:
            chunk_size = min(4096, position)
            position -= chunk_size
            handle.seek(position)
            buffer = handle.read(chunk_size) + buffer

            lines = buffer.splitlines()
            if position == 0 or len(lines) > 1:
                for raw_line in reversed(lines):
                    if raw_line.strip():
                        return raw_line.decode("utf-8", errors="replace")

    return None


def parse_last_event(rollout_path: Path) -> tuple[str, str]:
    last_line = read_last_nonempty_line(rollout_path)
    if not last_line:
        return "unknown", "missing-rollout"

    try:
        event = json.loads(last_line)
    except json.JSONDecodeError:
        return "unknown", "unparseable-last-line"

    event_type = normalize_text(event.get("type"))
    payload = event.get("payload")
    payload_type = ""
    if isinstance(payload, dict):
        payload_type = normalize_text(
            payload.get("type")
            or payload.get("phase")
            or payload.get("status")
        )

    if event_type == "event_msg" and payload_type == "task_complete":
        return "done-open", "event_msg:task_complete"
    if event_type == "event_msg" and payload_type == "turn_aborted":
        return "interrupted", "event_msg:turn_aborted"

    if payload_type:
        return "active", f"{event_type}:{payload_type}"
    if event_type:
        return "active", event_type
    return "unknown", "missing-event-type"


def fetch_threads(state_db: Path, cwd: str | None, limit: int) -> list[sqlite3.Row]:
    connection = sqlite3.connect(state_db)
    connection.row_factory = sqlite3.Row

    query = """
        select
          id,
          title,
          cwd,
          updated_at,
          rollout_path
        from threads
        where archived = 0
    """
    params: list[object] = []

    if cwd:
        query += " and cwd = ?"
        params.append(cwd)

    query += " order by updated_at desc limit ?"
    params.append(limit)

    try:
        return connection.execute(query, params).fetchall()
    finally:
        connection.close()


def shorten(value: str, width: int) -> str:
    if len(value) <= width:
        return value.ljust(width)
    return (value[: width - 3] + "...").ljust(width)


def main() -> int:
    args = parse_args()
    codex_home = resolve_codex_home()

    try:
        state_db = resolve_state_db(codex_home, args.state_db)
    except FileNotFoundError as error:
        print(str(error), file=sys.stderr)
        return 1

    rows = fetch_threads(state_db, args.cwd, args.limit)

    entries = []
    counts = {
        "active": 0,
        "done-open": 0,
        "interrupted": 0,
        "unknown": 0,
    }

    for row in rows:
        rollout_path = Path(row["rollout_path"]) if row["rollout_path"] else Path()
        status, last_event = parse_last_event(rollout_path)
        counts[status] = counts.get(status, 0) + 1
        entries.append(
            {
                "status": status,
                "updated": format_timestamp(row["updated_at"]),
                "title": normalize_text(row["title"]),
                "cwd": normalize_text(row["cwd"]),
                "last_event": last_event,
            }
        )

    if args.active_only:
        entries = [entry for entry in entries if entry["status"] == "active"]

    print(f"State DB: {state_db}")
    if args.cwd:
        print(f"Scope: cwd={args.cwd}")
    else:
        print("Scope: all unarchived threads")
    print(
        "Summary: "
        f"active={counts['active']} "
        f"done-open={counts['done-open']} "
        f"interrupted={counts['interrupted']} "
        f"unknown={counts['unknown']}"
    )

    if not entries:
        if args.active_only:
            print("\nNo active tabs matched the current scope.")
        else:
            print("\nNo unarchived tabs matched the current scope.")
        return 0

    print()
    header = (
        f"{'STATUS':<12}"
        f"{'UPDATED':<20}"
        f"{'TITLE':<38}"
        f"{'LAST EVENT':<32}"
        "CWD"
    )
    print(header)
    print("-" * len(header))

    for entry in entries:
        print(
            f"{entry['status']:<12}"
            f"{entry['updated']:<20}"
            f"{shorten(entry['title'], 38)}"
            f"{shorten(entry['last_event'], 32)}"
            f"{entry['cwd']}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
