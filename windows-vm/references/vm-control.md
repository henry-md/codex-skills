# Temporary guest control attempt

Snapshot: **2026-09-13**. The user requested tooling inside the VM to make control reliable and explicitly directed stopping if permissions or policy block it. This is a separate capability from the still-required physical Command-Shift-3/4 screenshot shortcuts.

## Client settings and transport

The intended device's Windows App custom settings were enabled (`UseCustomSettings`: false → true). The only folder added was writable **vm-control**, pointing to `/Users/henry/Documents/Codex/2026-09-13/use/work/vm-control`; removal of this unused share is pending. `StartSessionInFullScreen` changed true → false to retain the user-confirmed windowed-mode gesture workaround. The session was returned to a visibly normal window; other exposed display defaults were preserved.

The guest's exact UNC-folder test returned **false**. The existing `RDP-Tcp` `fDisableCdm` value was 0 and the corresponding Policies value was absent; these checks do not prove that the managed connection permits folder redirection, and false is not itself a permission-denial error. Share read/write remains unestablished. Remote coordinate input still returned `noWindowsAvailable`; plain key/text input worked. The device card's native context menu had been offscreen in full screen and became accessible after exiting full screen and opening Connection Center.

## Verified keyboard bootstrap

Guest File Explorer **F4**, followed by the exact text **powershell.exe** and a separate Return, launched ordinary Windows PowerShell in Windows Terminal without user help. Bare `powershell` instead selected an existing `Documents/PowerShell` folder. Explorer interpreted `//tsclient/vm-control` as a web URL and opened Edge; that was not share-access evidence. Probe the transport from PowerShell instead.

An **Open Folder** action exposed Explorer. In this run it came from a PowerToys diagnostic package, which created a local guest archive and was not uploaded; use an existing Explorer/Open Folder entry when available rather than regenerating diagnostics. Synthetic Shift-Tab arrived as plain Tab. Inspect each focus change and use plain keys, with text entry and Return separate.

## Direct guest UI Automation evidence

Windows PowerShell 5.1 reported `FullLanguage` and loaded `UIAutomationClient`/`UIAutomationTypes`. `AutomationElement.FromHandle` reached the verified PowerToys Settings window. Descendant inspection exposed its search TextBox with ValuePattern and navigation items with SelectionItemPattern, including Home (`DashboardNavItem`) and General (`GeneralNavItem`). The Input/Output item exposed ExpandCollapsePattern as well. Keyboard Manager Engine was running; that does not prove physical remaps work.

Selecting Home through SelectionItemPattern returned success, and the actual Home page visibly appeared after a delay. This is bounded UI-action proof. Selection also foregrounded PowerToys and left the console behind; an API success value alone neither proves the displayed result nor preserves command focus. Console-focus recovery tooling was prepared but not validated. If the user changes to another guest application or sign-in flow, stop sending input until the owned console is visibly available.

## Current blocker

The complete helper was neither transferred into the guest nor executed. No explicit UIA permission denial was observed. The host control/channel is currently the bottleneck: native CUA coordinate calls repeatedly returned `noWindowsAvailable`, including after native Raise and verified exit from full screen. Synthetic Alt-Tab while Unicode was requested arrived as plain Tab. The successful direct UIA action also hid its controller behind the target application.

Reliable end-to-end guest control is **not established**. Stop blind coordinate, modifier, or focus retries. Resume with a new evidence-producing control/transport approach or the owned console visibly restored; do not treat another unchanged Raise/resize/restart as a demonstrated fix.

## External artifacts and evidence boundary

Workspace: `/Users/henry/Documents/Codex/2026-09-13/use/`.

| Relative artifact | Status |
| --- | --- |
| `work/vm-control-draft/VmControl.ps1`, `Probe-VmControl.ps1`, `README.md` | Prepared and reviewed; complete helper not guest-transferred or executed |
| `work/vm-control/VmControl.ps1`, `Probe-VmControl.ps1` | Reviewed Mac-side copies in the attempted redirected folder; no guest transfer or execution established |

The helper is designed for an ordinary visible Windows PowerShell session: a bounded file queue, UI Automation inspection/invoke/set-value/focus, and guest `CopyFromScreen` capture. Default runtime is 15 minutes, with a `STOP` file. There is no listener, elevation, persistence, compiled executable, keyboard hook, or policy override. Design review is not runtime, policy-acceptance, or physical shortcut evidence.

Before treating this path as usable, establish permitted execution and share read/write, then independently verify a screenshot and harmless UI operation. On an execution-policy, WDAC/AppLocker, ASR, language-mode, or permission denial, retain the exact error and stop this tooling attempt; do not weaken or bypass the restriction.

## Stop and restore

If launched, stop through the helper's `STOP` file and confirm its termination evidence. Remove only the **vm-control** redirection when the experiment ends. The earlier device state had custom settings disabled and full-screen startup enabled; restoring that complete state would also remove the working windowed-start preference. Preserve later user changes and treat tooling cleanup separately from restoring full-screen behavior. No guest OS security settings were changed.
