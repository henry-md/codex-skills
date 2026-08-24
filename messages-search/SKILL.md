---
name: messages-search
description: Search a user's local Apple Messages history through a read-only, privacy-scoped query that learns confirmed contact-name-to-handle mappings locally. Use when the user asks to find, summarize, or review iMessage/SMS texts for a named person, search terms, or a specific date range.
---

# Messages Search

Use `scripts/search_messages.py` to query the local Messages database. The script opens the database read-only and emits JSON; it cannot send, edit, delete, or sync messages.

## Privacy rules

- Obtain a concrete scope before running: a participant or search phrase, plus a date range. If no range is given, use the script's 30-day default.
- Do not enumerate the user's complete history, contacts, or conversations. Do not raise the result limit above 100.
- Return a concise summary by default. Show raw message text only when the user asks for it.
- Explain permission errors without retrying privileged workarounds. The user must grant Full Disk Access to the app or helper that runs Codex.

## Local learning

Treat this as a self-learning skill only within these limits:

- Resolve a contact name through the local Contacts app only when an explicitly requested search needs it.
- Save only the confirmed name and its Messages phone/email handle in `references/contact-aliases.json`; never save message text, dates, conversation metadata, or Contacts unrelated to the query.
- Consult that local alias cache before opening Contacts, so repeat searches are faster. Keep the cache private to this skill and do not use it for background work.
- If a name matches more than one Contact, ask the user to choose; do not learn an ambiguous mapping. Use `--no-learn` if the user asks not to retain a new mapping.

## Query

Run the script with at least one selector:

```bash
python3 /Users/Henry/.codex/skills/messages-search/scripts/search_messages.py \
  --participant 'Alex' --after 2026-08-01 --before 2026-08-14
```

Use `--contains` for a phrase search, `--days` for a recent window, and `--limit` for a smaller result set. Contact-name searches automatically use the local alias cache and learn a new unambiguous mapping after a successful Contacts lookup. Dates are inclusive and use local calendar dates. Read `--help` before using an option not listed here.

## Limitations

Only text stored in the database's standard `text` field is returned. Attachments, reactions, handwritten messages, and some rich content may not have searchable text. Never claim a search is exhaustive when the output reports unavailable content.
