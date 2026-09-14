---
name: windows-vm
description: Documentation and self-learning guidance for operating Windows App VMs on macOS, verifying results inside Windows, and retaining useful lessons. Use for Windows App VM work; configure keyboard shortcuts only when requested.
---

# Windows VM

Inspect the intended session and current control tools. Distinguish Mac actions, guest configuration, synthetic input, and physical application behavior. Configure shortcuts only when requested.

## Current handoff

On **2026-09-13**, Windows Snipping Tool captured a region inside the guest and its copied image visibly pasted into guest Paint. The Q11's physical Command-Shift-3/4 **failed**; the user requires those exact chords, and a rejected Fn+4 alternate was restored. Three-finger swipe intermittently stopped after entering/exiting the VM. Read [screenshots-and-gestures.md](references/screenshots-and-gestures.md) for the working mouse route and current evidence; neither shortcut nor full-screen swipe is fixed.

The 2026-09-10 Keychron setup **remains incomplete**: physical Command arrows performed word navigation and Option arrows did nothing in Notepad, including after a verified PowerToys restart. Earlier console-event passes did not establish editor success. Windows remaps remain installed; Mac hardware layers were preserved. Read [keyboard-context.md](references/keyboard-context.md) before resuming keyboard work for successes, failed approaches, unresolved questions, and rollback. Do not reapply the recipe as a proven solution.

The user explicitly requested guest tooling for reliable control, with work to stop if permissions or policy block it. Direct guest UI Automation read and selected a PowerToys page, but the complete helper remains untransferred/unexecuted. The host control channel is the current bottleneck; no explicit UIA permission denial was observed. Read [vm-control.md](references/vm-control.md) before continuing, and do not repeat blind focus/input attempts.

## Control and recovery

These observations came from Windows App 11.4.0 (`com.microsoft.rdc.macos`), native CUA, and Windows PowerShell. Recheck after tool or environment changes.

- Native CUA `app.getScreenshot()` captured the visible guest on 2026-09-13. Remote coordinate clicks worked for Snipping Tool and Paint, then `noWindowsAvailable` recurred after resizing/focus changes. Raising or zooming the window was not a reliable recovery. Distinguish capture from input: a click failure does not establish screenshot failure. Avoid repeating unchanged failed actions.
- Normal-window/zoom transitions recovered access on some attempts. A fresh native accessibility **session-window click** restored typing when its center was visibly inside the owned Windows Terminal. Use a fresh element index and a safe target; this is not reliable coordinate clicking and can enter QuickEdit in classic consoles.
- If Connection Center appears while the session is active, use the native **Window** menu's connected-session entry (`activateSession:`), then verify the remote window. Do not reconnect solely because Connection Center is visible.
- After focus changes or a “user changed app” error, inspect before sending more input. A command visible at the prompt may not have executed. Coordinate uninterrupted access when necessary.

## Text transfer and testing

Windows Terminal accepted chunked Unicode/Base64 transfers with hash verification after Unicode was selected through the menu. Trials requesting Scancode lost case; direct strings lost backslashes. Use `Join-Path`, forward slashes, or `[char]92`. **Type, inspect until the complete command is visible, then send Return separately**: Return in the same call overtook the slow guest buffer and split commands.

Classic `conhost` ignored typing after requesting Unicode at its interactive PowerShell prompt but accepted `exit`/Return after requesting Scancode. Transfer and hash-verify files through Terminal, then launch the owned file directly with PowerShell `-File` under `conhost.exe -ForceNoHandoff`.

Microsoft recommends Scancode for arrows/combinations; use Unicode temporarily for setup. The session's checked mode was never conclusively verified, and `KeyboardDriverMode=0` remains uninterpreted. Menu selection alone does not prove the mode; if checked state is inaccessible, record it as unknown instead of repeating the clicks. [Keyboard modes](https://learn.microsoft.com/en-us/windows-app/input-keyboard-mouse-touch-pen#keyboard-modes)

Synthetic Control/Super combinations often arrived as plain keys. F20 did not open Run; F24 was rejected. No reliable automation launch key or complete automated shortcut suite was established. Console probes must account for QuickEdit, ConPTY reconstruction, and PowerToys' `0xFF` dummy events; see the reference.

For this user, request a simple test of the affected shortcuts after a meaningful change; avoid ordered cursor exercises and repeated identical requests. A user-reported application failure outweighs a passing configuration check. Stop an unproductive loop, record the blocker, and require a new evidence-producing approach before resuming.

## Maintain this skill

The user authorized frequent updates that save substantial future work. Keep dated successes, failures, evidence boundaries, and unresolved questions; replace stale guidance and prune repetition instead of accumulating a journal.

Keep this skill documentation-only: no credentials, client content, or executable helpers. Link external artifacts with their tested/unexecuted status. Maintenance does not authorize VM changes or background automation. Validate with the skill-creator validator when available.
