#!/usr/bin/env python3
"""List unarchived Codex tabs with evidence useful for /reflect recommendations."""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


REFLECT_TERMS = {
    "architecture",
    "cleanup",
    "complex",
    "duplicated",
    "duplication",
    "messy",
    "refactor",
    "reflect",
    "simplify",
    "tangled",
}

WORK_TERMS = {
    "api",
    "bug",
    "component",
    "database",
    "fix",
    "flow",
    "migration",
    "state",
    "test",
    "workflow",
}

PATH_RE = re.compile(
    r"(?<![\w/.-])(?:[A-Za-z0-9_.-]+/)+[A-Za-z0-9_.@-]+\.(?:ts|tsx|js|jsx|py|rb|go|rs|java|css|scss|md|json|yaml|yml|sql|sh)"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Summarize unarchived Codex tabs for /reflect triage.",
    )
    parser.add_argument("--cwd", help="Filter to an exact thread cwd.")
    parser.add_argument("--limit", type=int, default=30, help="Rows to inspect.")
    parser.add_argument("--state-db", help="Override Codex state database path.")
    parser.add_argument("--json", action="store_true", help="Emit JSON.")
    parser.add_argument(
        "--max-events",
        type=int,
        default=1200,
        help="Maximum transcript events to inspect per tab.",
    )
    return parser.parse_args()


def codex_home() -> Path:
    return Path(os.environ.get("CODEX_HOME", "~/.codex")).expanduser()


def resolve_state_db(home: Path, override: str | None) -> Path:
    if override:
        path = Path(override).expanduser()
        if path.exists():
            return path
        raise FileNotFoundError(f"State database not found: {path}")

    preferred = home / "state_5.sqlite"
    if preferred.exists():
        return preferred

    candidates = sorted(
        home.glob("state_*.sqlite"),
        key=lambda item: (item.stat().st_mtime, item.name),
        reverse=True,
    )
    if candidates:
        return candidates[0]

    raise FileNotFoundError(f"No state_*.sqlite file found under {home}")


def normalize(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.split())


def timestamp(value: Any) -> str:
    if not isinstance(value, int):
        return ""
    return datetime.fromtimestamp(value).strftime("%Y-%m-%d %H:%M:%S")


def fetch_threads(db_path: Path, cwd: str | None, limit: int) -> list[sqlite3.Row]:
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    query = """
        select id, title, cwd, updated_at, rollout_path
        from threads
        where archived = 0
    """
    params: list[Any] = []
    if cwd:
        query += " and cwd = ?"
        params.append(cwd)
    query += " order by updated_at desc limit ?"
    params.append(limit)
    try:
        return connection.execute(query, params).fetchall()
    finally:
        connection.close()


def read_events(path: Path, max_events: int) -> list[dict[str, Any]]:
    if not path.exists() or not path.is_file():
        return []

    events: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(event, dict):
                events.append(event)
                if len(events) > max_events:
                    events = events[-max_events:]
    return events


def event_payload_type(event: dict[str, Any]) -> str:
    payload = event.get("payload")
    if isinstance(payload, dict):
        return normalize(payload.get("type") or payload.get("phase") or payload.get("status"))
    return ""


def classify_last_event(events: list[dict[str, Any]], rollout_path: Path) -> tuple[str, str]:
    if not events:
        return "unknown", "missing-rollout" if not rollout_path.exists() else "empty-rollout"

    last = events[-1]
    event_type = normalize(last.get("type"))
    payload_type = event_payload_type(last)

    if event_type == "event_msg" and payload_type == "task_complete":
        return "done-open", "event_msg:task_complete"
    if event_type == "event_msg" and payload_type == "turn_aborted":
        return "interrupted", "event_msg:turn_aborted"
    if payload_type:
        return "active", f"{event_type}:{payload_type}"
    return ("active", event_type) if event_type else ("unknown", "missing-event-type")


def text_from_value(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return " ".join(text_from_value(item) for item in value)
    if isinstance(value, dict):
        parts = []
        for key in ("text", "content", "message", "cmd", "query", "pattern"):
            if key in value:
                parts.append(text_from_value(value[key]))
        return " ".join(parts)
    return ""


def extract_event_text(event: dict[str, Any]) -> tuple[str, str, str]:
    event_type = normalize(event.get("type"))
    payload = event.get("payload")
    role = ""
    kind = event_type
    text = ""

    if isinstance(payload, dict):
        kind = normalize(payload.get("type")) or event_type
        role = normalize(payload.get("role") or payload.get("type") or payload.get("source"))
        text = text_from_value(payload)
    else:
        text = text_from_value(event)

    return role or event_type, kind, normalize(text)


def collect_evidence(events: list[dict[str, Any]]) -> dict[str, Any]:
    user_messages: list[str] = []
    assistant_messages: list[str] = []
    seen_messages: set[tuple[str, str]] = set()
    scoring_text_parts: list[str] = []
    path_text_parts: list[str] = []
    paths: Counter[str] = Counter()

    for event in events:
        role, kind, text = extract_event_text(event)
        if not text:
            continue

        is_user = role == "user" or kind == "user_message"
        is_assistant = role == "assistant" or kind == "agent_message"
        is_tool_call = kind == "function_call"
        is_tool_output = kind == "function_call_output"

        if is_user and (
            text.startswith("# AGENTS.md instructions for ")
            or text.startswith("<skill>")
        ):
            continue

        if is_user or is_assistant:
            scoring_text_parts.append(text)
            path_text_parts.append(text)
        elif is_tool_call:
            path_text_parts.append(text)
        elif is_tool_output:
            # Tool outputs are often huge and contain ambient docs. Use them only
            # for local file-path hints, not for judging complexity language.
            path_text_parts.append(text)
        else:
            continue

        for match in PATH_RE.findall(" ".join(path_text_parts[-1:])):
            if not match.startswith(("r0/", "r1/", "r2/", "r3/", "r4/", "r5/", "r6/", "r7/", "r8/", "r9/", "r10/", "r11/", "r12/", "r13/")):
                paths[match] += 1

        if is_user:
            key = ("user", text)
            if key not in seen_messages:
                user_messages.append(text)
                seen_messages.add(key)
        elif is_assistant:
            key = ("assistant", text)
            if key not in seen_messages:
                assistant_messages.append(text)
                seen_messages.add(key)

    combined = " ".join(scoring_text_parts).lower()
    reflect_hits = sorted(term for term in REFLECT_TERMS if term in combined)
    work_hits = sorted(term for term in WORK_TERMS if term in combined)
    score = len(reflect_hits) * 3 + len(work_hits)
    score += min(len(paths), 8)
    score += min(len(user_messages), 5)

    return {
        "score": score,
        "reflect_terms": reflect_hits,
        "work_terms": work_hits,
        "mentioned_paths": [path for path, _ in paths.most_common(12)],
        "recent_user_messages": user_messages[-4:],
        "recent_assistant_messages": assistant_messages[-2:],
    }


def build_entries(args: argparse.Namespace) -> tuple[Path, list[dict[str, Any]]]:
    db_path = resolve_state_db(codex_home(), args.state_db)
    rows = fetch_threads(db_path, args.cwd, args.limit)
    entries: list[dict[str, Any]] = []

    for row in rows:
        rollout_path = Path(row["rollout_path"] or "")
        events = read_events(rollout_path, args.max_events)
        status, last_event = classify_last_event(events, rollout_path)
        evidence = collect_evidence(events)
        entries.append(
            {
                "score": evidence["score"],
                "status": status,
                "updated": timestamp(row["updated_at"]),
                "title": normalize(row["title"]),
                "cwd": normalize(row["cwd"]),
                "rollout_path": str(rollout_path),
                "last_event": last_event,
                **evidence,
            }
        )

    entries.sort(key=lambda item: (item["score"], item["updated"]), reverse=True)
    return db_path, entries


def shorten(text: str, width: int) -> str:
    if len(text) <= width:
        return text
    return text[: width - 3] + "..."


def print_text(db_path: Path, args: argparse.Namespace, entries: list[dict[str, Any]]) -> None:
    print(f"State DB: {db_path}")
    print(f"Scope: cwd={args.cwd}" if args.cwd else "Scope: all unarchived tabs")
    print(f"Unarchived tabs inspected: {len(entries)}")
    if not entries:
        return

    print("\nRanked tab triage hints:")
    for index, entry in enumerate(entries, start=1):
        print(
            f"\n{index}. score={entry['score']} status={entry['status']} "
            f"updated={entry['updated']}"
        )
        print(f"   title: {entry['title']}")
        print(f"   cwd: {entry['cwd']}")
        print(f"   last_event: {entry['last_event']}")
        print(f"   transcript: {entry['rollout_path']}")
        if entry["reflect_terms"]:
            print(f"   reflect_terms: {', '.join(entry['reflect_terms'])}")
        if entry["work_terms"]:
            print(f"   work_terms: {', '.join(entry['work_terms'])}")
        if entry["mentioned_paths"]:
            print(f"   mentioned_paths: {', '.join(entry['mentioned_paths'][:8])}")
        if entry["recent_user_messages"]:
            print("   recent_user_messages:")
            for message in entry["recent_user_messages"][-3:]:
                print(f"   - {shorten(message, 220)}")


def main() -> int:
    args = parse_args()
    try:
        db_path, entries = build_entries(args)
    except (FileNotFoundError, sqlite3.Error) as error:
        print(str(error), file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps({"state_db": str(db_path), "entries": entries}, indent=2))
    else:
        print_text(db_path, args, entries)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
