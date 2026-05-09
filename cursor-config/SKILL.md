---
name: cursor-config
description: Reference and diagnostic guidance for Cursor/VS Code configuration, workspace state, and extension issues. Use when the user asks why Cursor is slow, hung, or unable to load terminals, diffs, Git/SCM providers, GitLens views, or source control state; when Cursor says "No source control providers registered"; when raw Git may be fast but Cursor UI is stuck; or when preserving learnings about Cursor settings, logs, workspaceStorage, terminal persistence, and repo-specific cache resets.
---

# Cursor Config

## Overview

Use this skill as a compact knowledge base for debugging Cursor configuration and state problems, especially slow terminal, diff, Git, SCM, and GitLens startup. The goal is usually to distinguish actual repo/Git slowness from Cursor window state, extension host, terminal restore, or per-workspace cache problems.

For detailed commands, paths, log signatures, and the case notes from the terminal/diff investigation, read [references/cursor-terminal-scm-debugging.md](references/cursor-terminal-scm-debugging.md).

## Working Model

Treat Cursor as three layers:

1. Raw repo tools: `git`, shell startup, filesystem size, watchers.
2. Cursor global state: user settings, installed extensions, window restore, terminal persistence.
3. Cursor per-workspace state: `workspaceStorage/<id>`, saved SCM/sidebar/panel/terminal state, retrieval metadata, and cached UI state for one folder.

If every repo is slow, suspect global Cursor state, settings, or extensions. If one repo is slow and raw Git is fast, suspect that repo's Cursor `workspaceStorage` entry before changing repo files.

## First Checks

Do not assume Git is slow because Cursor's diff is slow. Time Git directly:

```sh
time git -C /path/to/repo status --short --untracked-files=all
time git -C /path/to/repo diff --name-only
```

If these are milliseconds or low seconds while Cursor takes minutes, look at Cursor logs and workspace state.

Relevant symptoms:

- Terminal panel opens slowly, never becomes usable, or revives old sessions.
- Source Control says `No source control providers registered`.
- GitLens says no provider/data available.
- Diff or SCM tab waits for minutes while raw Git is instant.
- Cursor logs contain `Timed out waiting for git context provider`.
- Cursor's Git extension logs `Initial repository scan completed - repositories (0)` for a real repo.

## Fix Strategy

Prefer reversible changes:

1. Confirm raw Git and shell startup are not the bottleneck.
2. Inspect Cursor logs for extension host churn, missing Git provider, terminal restore, or GitLens MCP hangs.
3. For global slowness, review global settings and noisy extensions.
4. For one-repo slowness, fully quit Cursor and move only that repo's `workspaceStorage/<id>` directory to a timestamped backup.
5. If the same repo quickly regenerates bad cache, treat the cache as a symptom and remove recurring extension conflicts before resetting it again.
6. Reopen Cursor and let it recreate clean per-workspace state.

Never delete Cursor state when a move-to-backup is enough. Avoid editing repo files, `.gitignore`, or workspace settings until there is evidence the repo itself is the cause.

## Known Helpful Settings

These global Cursor settings helped with prior terminal/diff startup issues:

```json
"gitlens.gitkraken.mcp.autoEnabled": false,
"terminal.integrated.enablePersistentSessions": false,
"window.restoreWindows": "none"
```

The first avoids a known GitLens GitKraken MCP auto-setup hang. The second prevents stale integrated terminals from being revived. The third prevents old windows/workspaces from being restored into the same bad state.

## Recurring Bad Cache

If a reset helps but the same repo soon returns to `repositories (0)` or git-context timeouts, look for extensions that fail or duplicate built-in Cursor functionality on every startup. In the April 2026 recurrence, the durable fix was to uninstall conflicting user extensions, then reset the repo cache once more. See [references/cursor-terminal-scm-debugging.md](references/cursor-terminal-scm-debugging.md) for the exact extension IDs and commands.
