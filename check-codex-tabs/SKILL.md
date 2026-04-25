---
name: check-codex-tabs
description: Inspect Codex Desktop's local state on this Mac to identify which Codex tabs or threads are open, still active, finished but left open, or interrupted. Use when the user asks which Codex tabs are in-flight, which open Codex chats are done editing, or to audit recent local Codex activity for the current repo or across all workspaces.
---

# Check Codex Tabs

Use this skill to answer Codex tab-status questions from local filesystem data instead of guessing from the visible app UI.

## Source Of Truth

Check these locations in order:

1. `~/.codex/state_5.sqlite`
   Use the `threads` table. `archived = 0` is the best local proxy for an open Codex tab or thread.
2. `rollout_path` from each `threads` row
   Open the referenced JSONL transcript, usually under `~/.codex/sessions/...`, and inspect the last JSON object.
3. `~/.codex/session_index.jsonl`
   Use only as fallback if the state database is unavailable.
4. `~/Library/Application Support/Codex`
   Ignore for this task unless `~/.codex` is missing. It contains app caches, but it is not the fast path for open-thread status.

Do not start with `logs_*.sqlite`. The logs database is useful for internal debugging, not for quickly classifying tabs.

## Fast Workflow

1. Determine the scope first.
   If the user asks about the current repo, run `git rev-parse --show-toplevel` and filter `threads.cwd` to that exact absolute path.
   If the user asks about all open Codex tabs on the laptop, do not filter by `cwd`.

2. Prefer the helper script.
   Run:

   ```bash
   python3 /Users/Henry/.codex/skills/check-codex-tabs/scripts/check_codex_tabs.py
   ```

   Add `--cwd /absolute/repo/root` for repo-specific output.
   Add `--active-only` when the user only wants unfinished tabs.
   Add `--limit N` when the user wants a larger or smaller slice of recent open threads.

3. Fall back to a direct SQLite query if the script is unavailable or you need to inspect raw rows.

4. For each returned row, inspect the last JSON object in `rollout_path` and classify the tab from that last event.

## Manual Query

Use this query for the current repo after resolving the repo root:

```sql
select
  datetime(updated_at, 'unixepoch', 'localtime') as updated,
  title,
  cwd,
  rollout_path
from threads
where archived = 0
  and cwd = '/absolute/repo/root'
order by updated_at desc
limit 40;
```

Run it with:

```bash
sqlite3 -header -column ~/.codex/state_5.sqlite "<query above>"
```

Then inspect the last JSON line in each transcript:

```bash
tail -n 1 "$rollout_path"
```

## Status Rules

Use the last rollout event, not the thread title, to decide whether the tab is still active:

- `event_msg` plus `task_complete`: `done-open`
- `event_msg` plus `turn_aborted`: `interrupted`
- anything else as the last event: `active`
- missing or unreadable rollout file: `unknown`

Common active signals include last events such as `exec_command_end`, `function_call_output`, `patch_apply_end`, or `token_count`.

Do not equate `archived = 0` with active work. Many tabs remain open after they finish cleanly.

## Output

When answering the user:

1. Group the results into `Active`, `Done But Open`, and `Interrupted Or Unknown`.
2. Include each tab's title, `cwd`, updated time, and the last event you used to classify it.
3. If the user only asked which tabs are still in-flight, report only the `Active` group.
4. If there are no active tabs in scope, say that explicitly.

## Constraints

- Treat unarchived threads as open tabs for this skill's purpose.
- Do not claim to know which tab is frontmost or visually selected in the app.
- Prefer exact `cwd` matching for repo-specific requests.
- Prefer the helper script over fragile shell pipelines that parse SQLite output with tabs or newlines in titles.
- If `state_5.sqlite` is missing, search for the newest `state_*.sqlite` under `~/.codex` before falling back to `session_index.jsonl`.
