#!/usr/bin/env python3
"""Search Apple's local Messages database without changing it."""

import argparse
import datetime as dt
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Any


APPLE_EPOCH = dt.datetime(2001, 1, 1, tzinfo=dt.timezone.utc)
MAX_LIMIT = 100
SKILL_DIRECTORY = Path(__file__).resolve().parents[1]
DEFAULT_ALIAS_CACHE = SKILL_DIRECTORY / "references/contact-aliases.json"


def normalize_name(value: str) -> str:
    """Normalize a contact name for exact alias-cache lookup."""
    return " ".join(value.casefold().split())


def looks_like_handle(value: str) -> bool:
    """Keep phone numbers and email addresses out of the Contacts lookup path."""
    return "@" in value or sum(character.isdigit() for character in value) >= 3


def load_aliases(path: Path) -> dict[str, dict[str, Any]]:
    """Load the skill's small local cache without treating a missing file as an error."""
    if not path.exists():
        return {}
    try:
        aliases = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(f"Cannot read the Messages contact cache: {path}") from error
    if not isinstance(aliases, dict):
        raise RuntimeError("Messages contact cache has an unexpected format.")
    return aliases


def save_alias(path: Path, lookup_name: str, contact_name: str, handles: list[str]) -> None:
    """Persist only a confirmed contact name and its Messages handles for future searches."""
    aliases = load_aliases(path)
    aliases[normalize_name(lookup_name)] = {
        "name": contact_name,
        "handles": sorted(set(handles)),
        "learned_at": dt.datetime.now(tz=dt.timezone.utc).replace(microsecond=0).isoformat(),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w") as cache_file:
        json.dump(aliases, cache_file, ensure_ascii=False, indent=2, sort_keys=True)
        cache_file.write("\n")
    path.chmod(0o600)


def lookup_contact(name: str) -> list[dict[str, Any]]:
    """Find exact-name candidates in Contacts without enumerating the address book."""
    script = """
        function run(argv) {
          const Contacts = Application('Contacts');
          const query = argv[0].toLowerCase();
          const people = Contacts.people.whose({name: {_contains: argv[0]}})();
          const unique = {};
          people.forEach(person => {
            const name = person.name();
            if (name.toLowerCase().includes(query)) {
              const handles = person.phones().map(phone => phone.value())
                .concat(person.emails().map(email => email.value()));
              const key = JSON.stringify([name, handles.slice().sort()]);
              unique[key] = {
                name: name,
                handles: handles
              };
            }
          });
          return JSON.stringify(Object.values(unique));
        }
    """
    completed = subprocess.run(
        ["osascript", "-l", "JavaScript", "-e", script, name],
        capture_output=True,
        check=False,
        text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError("Contacts lookup was not permitted. Allow Contacts access or use Scarlett's phone/email handle.")
    try:
        results = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError("Contacts returned an unreadable result.") from error
    return results if isinstance(results, list) else []


def resolve_participant(arguments: argparse.Namespace) -> list[str]:
    """Resolve a named person from the cache or Contacts, learning only unambiguous matches."""
    if not arguments.participant:
        return []
    if looks_like_handle(arguments.participant):
        return [arguments.participant]

    aliases = load_aliases(arguments.alias_cache)
    cached = aliases.get(normalize_name(arguments.participant))
    if isinstance(cached, dict) and isinstance(cached.get("handles"), list):
        return [str(handle) for handle in cached["handles"] if handle]

    candidates = lookup_contact(arguments.participant)
    candidates = [candidate for candidate in candidates if candidate.get("handles")]
    if not candidates:
        raise RuntimeError(f"No exact Contacts match was found for {arguments.participant!r}. Use a phone number or email instead.")
    if len(candidates) > 1:
        names = ", ".join(str(candidate.get("name", "unnamed contact")) for candidate in candidates)
        raise RuntimeError(f"More than one Contact matches {arguments.participant!r}: {names}. Use a handle instead.")

    candidate = candidates[0]
    handles = [str(handle) for handle in candidate["handles"] if handle]
    if not arguments.no_learn:
        save_alias(arguments.alias_cache, arguments.participant, str(candidate["name"]), handles)
    return handles


def parse_day(value: str) -> dt.date:
    """Validate an ISO calendar date passed on the command line."""
    try:
        return dt.date.fromisoformat(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("Use YYYY-MM-DD dates.") from error


def apple_timestamp(value: Any) -> str | None:
    """Convert the several observed Apple Messages timestamp units to ISO UTC."""
    if value is None:
        return None
    try:
        seconds = float(value)
    except (TypeError, ValueError):
        return None
    if abs(seconds) > 10_000_000_000:
        seconds /= 1_000_000_000
    return (APPLE_EPOCH + dt.timedelta(seconds=seconds)).isoformat()


def to_apple_seconds(value: dt.datetime) -> int:
    """Translate a timezone-aware datetime into Messages' Apple-epoch seconds."""
    return int((value.astimezone(dt.timezone.utc) - APPLE_EPOCH).total_seconds())


def open_database(path: Path) -> sqlite3.Connection:
    """Open an existing database in SQLite read-only mode and forbid writes."""
    if not path.exists():
        raise RuntimeError(f"Messages database not found: {path}")
    database_url = f"file:{path}?mode=ro"
    try:
        connection = sqlite3.connect(database_url, uri=True)
    except sqlite3.OperationalError as error:
        raise RuntimeError(
            "Cannot open Messages. Grant Full Disk Access to the app or helper running Codex, "
            "then try again."
        ) from error
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only = ON")
    return connection


def require_schema(connection: sqlite3.Connection) -> None:
    """Fail clearly when the local Messages schema is unavailable or unexpected."""
    tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    needed = {"message", "handle", "chat_message_join", "chat_handle_join"}
    missing = needed - tables
    if missing:
        raise RuntimeError(f"Messages database is missing expected tables: {', '.join(sorted(missing))}")
    columns = {row[1] for row in connection.execute("PRAGMA table_info(message)")}
    required = {"date", "handle_id", "is_from_me", "text"}
    missing = required - columns
    if missing:
        raise RuntimeError(f"Messages database is missing expected message fields: {', '.join(sorted(missing))}")


def make_query(arguments: argparse.Namespace) -> tuple[str, list[Any]]:
    """Build a bounded text-only query against direct and group conversations."""
    clauses = ["m.text IS NOT NULL", "trim(m.text) <> ''"]
    parameters: list[Any] = []

    if arguments.contains:
        clauses.append("lower(m.text) LIKE lower(?)")
        parameters.append(f"%{arguments.contains}%")

    if arguments.participant_handles:
        direct_matches = " OR ".join("lower(coalesce(h.id, '')) LIKE lower(?)" for _ in arguments.participant_handles)
        group_matches = " OR ".join("lower(participant_handle.id) LIKE lower(?)" for _ in arguments.participant_handles)
        clauses.append(
            f"""(
                {direct_matches}
                OR EXISTS (
                    SELECT 1
                    FROM chat_message_join AS cmj
                    JOIN chat_handle_join AS chj ON chj.chat_id = cmj.chat_id
                    JOIN handle AS participant_handle ON participant_handle.ROWID = chj.handle_id
                    WHERE cmj.message_id = m.ROWID
                      AND ({group_matches})
                )
            )"""
        )
        wildcard_handles = [f"%{handle}%" for handle in arguments.participant_handles]
        parameters.extend(wildcard_handles)
        parameters.extend(wildcard_handles)

    end_day = arguments.before or dt.date.today()
    start_day = arguments.after or (end_day - dt.timedelta(days=arguments.days - 1))
    if start_day > end_day:
        raise RuntimeError("--after must be on or before --before.")

    start = dt.datetime.combine(start_day, dt.time.min, tzinfo=dt.timezone.utc)
    end = dt.datetime.combine(end_day + dt.timedelta(days=1), dt.time.min, tzinfo=dt.timezone.utc)
    normalized_date = "CASE WHEN abs(m.date) > 10000000000 THEN m.date / 1000000000 ELSE m.date END"
    clauses.extend([f"{normalized_date} >= ?", f"{normalized_date} < ?"])
    parameters.extend([to_apple_seconds(start), to_apple_seconds(end)])

    query = f"""
        SELECT m.ROWID AS message_id, m.guid, m.date, m.is_from_me, m.text,
               h.id AS handle
        FROM message AS m
        LEFT JOIN handle AS h ON h.ROWID = m.handle_id
        WHERE {' AND '.join(clauses)}
        ORDER BY m.date DESC
        LIMIT ?
    """
    parameters.append(arguments.limit)
    return query, parameters


def search(connection: sqlite3.Connection, arguments: argparse.Namespace) -> list[dict[str, Any]]:
    """Run the selected read-only search and normalize its JSON-safe output."""
    arguments.participant_handles = resolve_participant(arguments)
    query, parameters = make_query(arguments)
    results = []
    for row in connection.execute(query, parameters):
        results.append(
            {
                "timestamp": apple_timestamp(row["date"]),
                "direction": "sent" if row["is_from_me"] else "received",
                "participant": row["handle"],
                "text": row["text"],
            }
        )
    return results


def create_parser() -> argparse.ArgumentParser:
    """Define a deliberately narrow, read-only command-line interface."""
    parser = argparse.ArgumentParser(description="Search local Apple Messages text without modifying it.")
    parser.add_argument("--participant", help="Part of a phone number, email, or handle in the conversation.")
    parser.add_argument("--contains", help="A text phrase to find, case-insensitively.")
    parser.add_argument("--after", type=parse_day, help="First local date to include (YYYY-MM-DD).")
    parser.add_argument("--before", type=parse_day, help="Last local date to include (YYYY-MM-DD).")
    parser.add_argument("--days", type=int, default=30, help="Recent-day window when --after is omitted (default: 30).")
    parser.add_argument("--limit", type=int, default=50, help="Maximum results, 1-100 (default: 50).")
    parser.add_argument("--no-learn", action="store_true", help="Do not save a newly resolved contact name locally.")
    parser.add_argument(
        "--database",
        type=Path,
        default=Path.home() / "Library/Messages/chat.db",
        help=argparse.SUPPRESS,
    )
    parser.add_argument("--self-test", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--alias-cache", type=Path, default=DEFAULT_ALIAS_CACHE, help=argparse.SUPPRESS)
    return parser


def run_self_test() -> None:
    """Exercise query construction without accessing the user's Messages history."""
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.executescript(
        """
        CREATE TABLE message (guid TEXT, date INTEGER, handle_id INTEGER, is_from_me INTEGER, text TEXT);
        CREATE TABLE handle (id TEXT);
        CREATE TABLE chat_message_join (chat_id INTEGER, message_id INTEGER);
        CREATE TABLE chat_handle_join (chat_id INTEGER, handle_id INTEGER);
        INSERT INTO handle (id) VALUES ('alex@example.com');
        INSERT INTO message (guid, date, handle_id, is_from_me, text)
        VALUES ('test-guid', 0, 1, 0, 'Lunch tomorrow?');
        """
    )
    arguments = create_parser().parse_args(["--participant", "alex@example.com", "--after", "2001-01-01", "--before", "2001-01-01"])
    results = search(connection, arguments)
    if len(results) != 1 or results[0]["text"] != "Lunch tomorrow?":
        raise RuntimeError("Self-test did not return the expected message.")
    print("Self-test passed: the script can query a synthetic Messages database read-only.")


def main() -> None:
    """Validate scope, run the search, and print only the selected message records."""
    arguments = create_parser().parse_args()
    if arguments.self_test:
        run_self_test()
        return
    if not arguments.participant and not arguments.contains:
        raise SystemExit("Provide --participant or --contains to keep every search scoped.")
    if arguments.days < 1 or arguments.days > 365:
        raise SystemExit("--days must be between 1 and 365.")
    if arguments.limit < 1 or arguments.limit > MAX_LIMIT:
        raise SystemExit(f"--limit must be between 1 and {MAX_LIMIT}.")

    connection = open_database(arguments.database)
    try:
        require_schema(connection)
        results = search(connection, arguments)
    finally:
        connection.close()
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as error:
        print(f"Error: {error}", file=sys.stderr)
        raise SystemExit(1) from error
