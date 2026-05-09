# Cursor Terminal, Diff, and SCM Debugging

## Mental model

Cursor can look like it is "finding Git" or "loading the terminal" when the actual bottleneck is the VS Code/Cursor window lifecycle:

- Raw Git commands may be fast.
- The Git/SCM provider may not register in the extension host.
- The diff UI may wait on Cursor's git context provider.
- The terminal UI may be delayed by panel/window state or stale persistent terminal restore.
- Per-repo `workspaceStorage` can preserve broken SCM/sidebar/panel/terminal state across reloads.

Use this distinction before changing repo files.

## Key paths on macOS

User settings:

```text
/Users/Henry/Library/Application Support/Cursor/User/settings.json
```

Logs:

```text
/Users/Henry/Library/Application Support/Cursor/logs
```

Per-workspace state:

```text
/Users/Henry/Library/Application Support/Cursor/User/workspaceStorage
```

Installed extensions:

```text
/Users/Henry/.cursor/extensions
```

## Raw repo checks

Run these before blaming Cursor or changing repo settings:

```sh
time git -C /path/to/repo status --short --untracked-files=all
time git -C /path/to/repo diff --name-only
time git -C /path/to/repo rev-parse --show-toplevel
du -sh /path/to/repo /path/to/repo/.git
```

Interpretation:

- If Git is slow here, debug the repo: huge untracked files, filesystem, hooks, worktrees, submodules, network mounts, or shell prompt integrations.
- If Git is fast here but Cursor takes minutes, debug Cursor state, extensions, logs, or `workspaceStorage`.

In the April 2026 case, `intention-setting` had raw `git status --untracked-files=all` around 16 ms and `.git` around 17 MB, but Cursor still took minutes. That proved the bottleneck was not Git.

## Log signatures

Search recent log folders with targeted patterns. Avoid broad log dumps because Cursor extension logs can contain huge minified payloads.

```sh
latest="$(find "/Users/Henry/Library/Application Support/Cursor/logs" -maxdepth 1 -type d -name '20*' -print | sort | tail -1)"
rg -n 'Timed out waiting for git context provider|No source control providers|No search provider registered|Initial repository scan|repositories \\(0\\)|Extension host terminating|Revived process|orphan|GitKraken|MCP' "$latest"
```

Important signatures:

```text
[WorktreeManager] Timed out waiting for git context provider
No source control providers registered
No search provider registered for scheme: file, waiting
Initial repository scan completed - repositories (0)
Extension host terminating: renderer closed the MessagePort
Revived process ...
Persistent process ... was an orphan
GkCliIntegrationProvider.setupMCPCore -- failed [300013ms]
installCLI exceeded 300000ms
```

Meaning:

- `Timed out waiting for git context provider`: Cursor's internal git context did not become ready; diff/worktree features can wait 30 seconds per attempt.
- `repositories (0)` for a real repo: Git provider did not register/discover correctly in that window.
- `No source control providers registered`: SCM UI is missing a provider, not necessarily missing Git.
- `Revived process` or `orphan`: persistent terminal restore may be reviving stale shells.
- GitLens GitKraken MCP timeouts around 300000 ms: disable GitLens auto MCP setup.

## WorkspaceStorage mapping

Find which `workspaceStorage` folder belongs to a repo:

```sh
rg -l '"folder": "file:///Users/Henry/Developer/intention-setting"' \
  "/Users/Henry/Library/Application Support/Cursor/User/workspaceStorage"/*/workspace.json
```

Inspect useful keys:

```sh
sqlite3 "/Users/Henry/Library/Application Support/Cursor/User/workspaceStorage/<id>/state.vscdb" \
  "select key, value from ItemTable where key in ('workbench.sidebar.activeviewletid','terminal.integrated.layoutInfo','scm:view:visibleRepositories','vscode.git');"
```

Suspicious examples from the April 2026 case:

```text
workbench.sidebar.activeviewletid|workbench.view.scm
terminal.integrated.layoutInfo|{"workspaceId":"...","tabs":[{"isActive":true,"activePersistentProcessId":27,...}]}
scm:view:visibleRepositories|{"all":["git:Git:file:///Users/Henry/Developer/intention-setting"],...}
```

This meant the UI remembered SCM and an old persistent terminal while the live Git provider had scanned zero repos.

## Safe per-repo cache reset

Use when one repo is slow, raw Git is fast, and logs point to SCM/provider/window state.

1. Fully quit Cursor, not only the affected window.
2. Verify Cursor is not holding the workspace DB open.
3. Move the workspace storage folder to a backup.
4. Reopen Cursor so it recreates the folder.

Commands:

```sh
storage="/Users/Henry/Library/Application Support/Cursor/User/workspaceStorage/<id>"
backup="${storage}.backup-$(date +%Y%m%dT%H%M%S)"

osascript -e 'tell application "Cursor" to quit' >/dev/null 2>&1 || true

for i in {1..40}; do
  if ! pgrep -x Cursor >/dev/null 2>&1 && ! lsof +D "$storage" >/dev/null 2>&1; then
    break
  fi
  sleep 0.25
done

lsof +D "$storage" 2>/dev/null | head -50
mv "$storage" "$backup"
echo "moved_to=$backup"
```

If `lsof` still shows Cursor holding `state.vscdb`, do not move it yet. Quit Cursor fully and retry.

This reset does not touch repo files. It only discards Cursor's per-workspace UI/cache state. Move, do not delete, so the old state can be restored if needed.

## Global settings that helped

Set these in Cursor user settings when the symptoms match:

```json
"gitlens.gitkraken.mcp.autoEnabled": false,
"terminal.integrated.enablePersistentSessions": false,
"window.restoreWindows": "none"
```

Why:

- `gitlens.gitkraken.mcp.autoEnabled: false` avoids GitLens spending up to 5 minutes on GitKraken MCP CLI setup.
- `terminal.integrated.enablePersistentSessions: false` avoids reviving stale integrated terminals and orphaned shells.
- `window.restoreWindows: "none"` reduces stale workspace/window restoration and helps make reopen behavior clean.

Validate JSON after editing:

```sh
python3 -m json.tool "/Users/Henry/Library/Application Support/Cursor/User/settings.json" >/dev/null
```

## Extension suspects from the case

These extensions showed noisy or suspicious behavior in logs. Treat them as suspects if the cache reset and global settings are not enough:

- `ms-vscode-remote.remote-wsl`: activation failure/noisy dump on macOS.
- `ms-vscode.js-debug-nightly`: duplicate built-in JS debug views/commands.
- `ms-vscode-remote.remote-ssh`: can duplicate Cursor's own `anysphere.remote-ssh` registrations.
- `iagolaguna.vscodefy`: deactivation error reading `globalState`.

Do not uninstall or disable extensions as the first move when a per-repo cache reset is safer and reversible. If testing extensions, use a new Cursor window with extensions disabled or disable one suspect at a time.

## Recurring cache fix

If a repo works after `workspaceStorage` reset but soon creates the same bad state again, the cache is probably being poisoned during Cursor startup. In the April 2026 recurrence for `intention-setting`, raw Git was still fast, but the new cache again recorded SCM state while Cursor logs showed:

```text
Initial repository scan completed - repositories (0)
No search provider registered for scheme: file, waiting
[WorktreeManager] Timed out waiting for git context provider, skipping worktree discovery
```

The durable fix was:

1. Quit Cursor.
2. Move the known-conflicting extension folders outside `~/.cursor/extensions` as a reversible backup.
3. Reset the repo `workspaceStorage` folder.
4. Reopen once so Cursor invalidates its extension scan cache.
5. Run Cursor's official uninstall command for the same extension IDs so the extension registry no longer reports them.

Extension IDs removed:

```text
ms-vscode.js-debug-nightly
ms-vscode-remote.remote-wsl
ms-vscode-remote.remote-ssh
ms-vscode-remote.remote-ssh-edit
iagolaguna.vscodefy
```

Why these:

- `ms-vscode.js-debug-nightly` duplicated Cursor's built-in `ms-vscode.js-debug` commands, views, and settings.
- `ms-vscode-remote.remote-wsl` threw a syntax error during activation on macOS.
- `ms-vscode-remote.remote-ssh` and `ms-vscode-remote.remote-ssh-edit` duplicated Cursor's built-in `anysphere.remote-ssh` commands and settings.
- `iagolaguna.vscodefy` activated at startup and threw during extension-host shutdown.

Use the official uninstall command after any manual backup/move:

```sh
cursor_bin="/Applications/Cursor.app/Contents/Resources/app/bin/cursor"
for id in \
  ms-vscode.js-debug-nightly \
  ms-vscode-remote.remote-wsl \
  ms-vscode-remote.remote-ssh \
  ms-vscode-remote.remote-ssh-edit \
  iagolaguna.vscodefy
do
  "$cursor_bin" --uninstall-extension "$id"
done

"$cursor_bin" --list-extensions --show-versions | rg 'ms-vscode\\.js-debug-nightly|ms-vscode-remote\\.remote-(wsl|ssh)|iagolaguna\\.vscodefy|eamodio\\.gitlens' || true
```

Expected verification:

- The suspect IDs should no longer appear in `--list-extensions`; GitLens may still appear if intentionally kept.
- Fresh startup logs should not contain duplicate JS debug view/command errors, Remote-SSH duplicate registration errors, WSL activation syntax errors, or vscodefy errors.
- `vscode.git/Git.log` should report `repositories (1)` for the repo.
- There should be no 30-second `Timed out waiting for git context provider` entry.

## Case notes: April 28, 2026

Observed symptoms:

- Cursor took minutes to load terminal and diff.
- SCM showed `No source control providers registered`.
- GitLens said no data provider was registered.
- Reloading the window did not help.
- Fully quitting/reopening initially helped another repo but not `intention-setting`.

Findings:

- Raw Git in `intention-setting` was fast: about 16 ms for `git status --untracked-files=all`.
- `.git` was small, around 17 MB.
- Logs showed `Timed out waiting for git context provider` and `Initial repository scan completed - repositories (0)`.
- The per-workspace DB had stale SCM and terminal layout state.
- Cursor kept the `state.vscdb` open even after the visible repo window closed; a full Cursor quit was needed.

Fix:

```text
Moved /Users/Henry/Library/Application Support/Cursor/User/workspaceStorage/61807ebda8c69c80a85f8a8c1b3065e9
to    /Users/Henry/Library/Application Support/Cursor/User/workspaceStorage/61807ebda8c69c80a85f8a8c1b3065e9.backup-20260428T204359
```

After reopening, `intention-setting` loaded terminal and diff quickly.

Recurrence fix:

```text
Moved conflicting extensions to:
/Users/Henry/.cursor/extensions-disabled-codex-20260428T214629

Reset recurring intention-setting cache:
/Users/Henry/Library/Application Support/Cursor/User/workspaceStorage/61807ebda8c69c80a85f8a8c1b3065e9.backup-20260428T214629

Then uninstalled the extension IDs with Cursor CLI so the registry stopped reporting them.
After a clean relaunch, the latest log showed repositories (1), no git-context timeout, and no duplicate JS-debug/Remote-SSH/WSL/vscodefy signatures.
```

## Summary for future prompts

Give future agents this compact context:

```text
Cursor is slow to load terminal/diff/SCM in one repo, but raw Git is fast.
Previously, this was fixed by fully quitting Cursor and moving aside that repo's Cursor workspaceStorage folder.
Check logs for WorktreeManager timed out waiting for git context provider, Initial repository scan completed - repositories (0), and No source control providers registered.
Do not change repo files first. Diagnose raw Git, then reset Cursor per-workspace cache if Git is fast.
```
