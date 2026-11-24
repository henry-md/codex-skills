---
name: check-codex-tabs
description: Inspect local state on this Mac to identify which Codex tabs or Claude Code sessions are open, still active, finished but left open, or interrupted. Use when the user asks which Codex tabs are in-flight, which Claude Code sessions are active, which open chats are done editing, or to audit recent local AI coding activity for the current repo or across all workspaces.
---

# Check Codex / Claude Code Tabs

Use this skill to answer tab-status questions from local filesystem data instead of guessing from the visible app UI. Covers both Codex Desktop and Claude Code (Cursor sidebar or desktop app).

## Codex Source Of Truth

1. `~/.codex/state_5.sqlite` — `threads` table. `archived = 0` = tab is open (exists in UI); `archived = 1` = tab was explicitly deleted and will never appear again. All unarchived threads are considered open.
2. `rollout_path` from each `threads` row — JSONL transcript under `~/.codex/sessions/...`; inspect the last JSON object to classify activity.
3. `~/.codex/session_index.jsonl` — fallback if the state database is unavailable.
4. `~/Library/Application Support/Codex` — ignore unless `~/.codex` is missing.

Do not start with `logs_*.sqlite`.

## Claude Code Source Of Truth

Claude Code has no archived/unarchived distinction. A conversation either exists (JSONL file is present) or was deleted (file is gone — you'll never see it). All files you find are open sessions.

1. `~/.claude/projects/<slug>/*.jsonl` — one file per conversation. Presence = open/exists. Inspect the last JSON line to classify activity.
2. `~/.claude/sessions/*.json` — currently running Claude Code processes (`pid`, `sessionId`, `cwd`, `kind`, `entrypoint`). Cross-reference these to identify which conversations are actively executing right now.
3. `~/.claude/ide/*.lock` — one per active Cursor/IDE window (`pid`, `workspaceFolders`, `ideName`). Lock file present = a Cursor window is live.

To map a project slug back to a repo path: the slug is the absolute path with `/` replaced by `-` (e.g. `/Users/Henry/Developer/job-helper` → `-Users-Henry-Developer-job-helper`).

## Fast Workflow

1. Determine the scope and runtime first.
   - If the user asks about the current repo, run `git rev-parse --show-toplevel`.
   - If the user asks about Codex specifically, use the Codex path. If Claude Code specifically, use the Claude Code path. If unspecified, check both.

2. **Codex** — prefer the helper script:
   ```bash
   python3 /Users/Henry/.codex/skills/check-codex-tabs/scripts/check_codex_tabs.py
   ```
   Add `--cwd /absolute/repo/root` for repo-specific output, `--active-only` for in-flight only, `--limit N` for slice size.
   Fall back to a direct SQLite query if the script is unavailable.

3. **Claude Code** — list sessions for the repo and inspect last events:
   ```bash
   # list sessions for a repo (replace slug as needed)
   ls -lt ~/.claude/projects/-Users-Henry-Developer-job-helper/*.jsonl | head -20

   # get last event from a session
   tail -n 1 ~/.claude/projects/-Users-Henry-Developer-job-helper/<session-id>.jsonl

   # see which sessions are actively running right now
   ls ~/.claude/sessions/
   cat ~/.claude/sessions/<pid>.json
   ```

## Manual Codex Query

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

```bash
sqlite3 -header -column ~/.codex/state_5.sqlite "<query above>"
tail -n 1 "$rollout_path"
```

## Status Rules

Use the last event in the transcript to classify activity:

**Codex** (rollout JSONL):
- `event_msg` + `task_complete`: `done-open`
- `event_msg` + `turn_aborted`: `interrupted`
- anything else as last event: `active`
- missing/unreadable file: `unknown`
- Common active signals: last events such as `exec_command_end`, `function_call_output`, `patch_apply_end`, or `token_count`.
- Do not equate `archived = 0` with active work; many tabs stay open after finishing cleanly.

**Claude Code** (session JSONL — last line is a JSON message object):
- `role: assistant` with a final text message (no tool calls in progress): `done-open`
- Session pid present in `~/.claude/sessions/` and last event is a tool call or partial turn: `active`
- Session pid absent from `~/.claude/sessions/` and last event is mid-turn: `interrupted`
- Unreadable file: `unknown`

## Output

1. Group into `Active`, `Done But Open`, and `Interrupted Or Unknown`.
2. Include each session's title or session ID, `cwd`, updated time, and last event used to classify it.
3. If the user only asked which sessions are in-flight, report only `Active`.
4. If there are no active sessions in scope, say so explicitly.
5. Label each result with its runtime: `[Codex]` or `[Claude Code]`.

## Constraints

- For Codex: treat `archived = 0` as open. For Claude Code: treat every existing JSONL as open.
- Do not claim to know which tab is frontmost or visually selected.
- Prefer exact `cwd` matching for repo-specific requests.
- Prefer the helper script over fragile shell pipelines that parse SQLite output with tabs or newlines in titles.
- If `state_5.sqlite` is missing, search for the newest `state_*.sqlite` under `~/.codex` before falling back to `session_index.jsonl`.
