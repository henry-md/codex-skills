# Keyboard setup: evidence and handoff

Snapshot: **2026-09-10**, Windows App **11.4.0**, Keychron **Q11 ANSI Knob**, guest PowerToys **0.101.2362.0**. This is an incomplete setup, not a validated installation recipe. The user confirmed the failure inside the VM with the physical keyboard set to Windows. Work stopped; the Windows remaps remain installed and no rollback was performed.

## What succeeded, and what did not

| Area | Established result | Boundary |
| --- | --- | --- |
| Hardware configuration | Guarded VIA writes and repeated full readbacks matched the intended Windows changes; Mac layers 0/1, macros, and encoders preserved | Stored configuration, not application behavior or live switch position |
| PowerToys installation | Official Microsoft-signed per-user installer exited 0; hash matched WinGet and Authenticode passed | Does not establish every remap works |
| Guest configuration | Two key rows and 27 shortcut rows read back; engine started; settings loaded and handler events appeared in logs | A running process/configuration is not proof of effective input handling |
| Historical Notepad A/S/W | With the **former direct-Right-Control hardware**, physical select-all/save/close passed; guest file contained `TEST PASSED`; VM stayed connected | Not retested successfully after the later transport change |
| Current console arrows | Standalone console captured Option-Left → Ctrl-Left and Command-Left → Home; user confirmed both registered | Console-event proof only |
| Current Notepad arrows | Physical Command-Left moved line 1/column 46 → 41 instead of 1; user reports Command skips words and Option does nothing | **Failed; unresolved**, including after PowerToys restart |
| Screenshots, retested 2026-09-13 | User reports Q11 Command-Shift-3/4 do nothing; built-in Mac Command-Shift-4 creates a host-only capture | **Failed; unresolved**. Guest Snipping Tool capture and Paint paste worked by mouse; see [screenshots and gestures](screenshots-and-gestures.md) |
| Remaining shortcuts | Shift-selection variants, redo, tab switching, and most ordinary commands are configured or native equivalents | Not individually verified; no blanket pass |

A selected final line in a multistep exercise did not prove that each movement/selection shortcut worked. Do not override the user's failure report with that screenshot. Full inventory: `outputs/shortcut-test-matrix.md` in the workspace below.

At **14:47:53 guest time**, a normal-user PowerToys restart created engine PID **23132**. `PROFILE_UNCHANGED=True` confirmed no profile drift; the same two key rows/27 shortcuts remained. Windows listed only `en-US`, input method `0409:00000409`. The user then confirmed the same Notepad failure. **Another unchanged restart is not a new fix.**

## Current shortcut architecture

Command → Q11 **Right Alt** → Windows App → PowerToys **Right Control** → native Control handling or a shortcut remap. Left Option emits Left Alt. The key physically labeled **right Control** emits Left Control; earlier diagnostic prompts incorrectly called it right Option. Other keyboards' Right Alt is also affected by this guest mapping.

Windows App's Keyboard → **Allow Close** was disabled and verified through native UI, preventing its Command-W session-close action. Historical remote-document close proof is scoped in the table above.

| Physical input | Configured guest result |
| --- | --- |
| Command + ordinary letters, including A/C/X/V/S/F/Z/T | Right Ctrl + letter; application-dependent |
| Command + Left/Right/Up/Down | Home / End / Ctrl-Home / Ctrl-End |
| Command + Shift + arrows | Corresponding boundary movement with Shift selection |
| Option + arrows; Option + Shift + arrows | Ctrl-arrows; Ctrl-Shift-arrows |
| Option + Backspace / forward Delete | Ctrl-Backspace / Ctrl-Delete |
| Command-Shift-Z; Command-Shift-[ / ] | Ctrl-Y; Ctrl-Page Up / Ctrl-Page Down |
| Command-Shift-3 / 4 | Windows-Print Screen / Windows-Shift-S |
| Command-Q / Space / Tab / Shift-Tab | Alt-F4 / Windows-S / Alt-Tab / Alt-Shift-Tab |
| Command-Delete line deletion; exact Command-M minimize | **Not implemented** |

Only Keyboard Manager was enabled; `startup=True`, `run_elevated=False`. Its current-user autorun task was enabled/Ready with a non-elevated principal and a three-second logon delay. Fresh-login startup was not tested; reconnecting Windows App is not a guest login. Elevated-application coverage is unverified.

Guest paths, relative to `%LOCALAPPDATA%`:

- Executable: `PowerToys/PowerToys.exe`; engine: `PowerToys/PowerToys.KeyboardManagerEngine/PowerToys.KeyboardManagerEngine.exe`.
- General settings: `Microsoft/PowerToys/settings.json`.
- Module/profile: `Microsoft/PowerToys/Keyboard Manager/settings.json` and `default.json`; read `properties.activeConfiguration.value` rather than assuming the active filename.
- Dated engine log: `Microsoft/PowerToys/Keyboard Manager/Engine/Logs/v0.101.2362/log_2026-09-10.log`. Searching only for `log.log` missed it.

The two individual-key rows are `165 → 163` and `131 → 91;82` (F20 → Win-R). The 17 Command shortcut sources use Right Ctrl `163`; ten Option sources use generic Alt `18`. All 27 have `exactMatch:true`. No reliable full guest profile checksum was transcribed; the before/after equality check above is valid without inventing a checksum.

## Major unsuccessful approaches

| Approach | Observed outcome / consequence |
| --- | --- |
| Synthetic modifier chords and automation function keys | Control/Super combinations often became plain keys. F20 did not open Run after either mode was requested; F24 returned `keyNotFound`. No autonomous terminal-launch key was established. |
| Repeated mode selection, focus recovery, and engine restart | Some restored setup-text entry, but did not establish a navigation fix. The actual checked mode was not conclusively captured; `KeyboardDriverMode=0` was not decoded. |
| Custom native keyboard helper | C# compilation and PowerShell `FullLanguage` succeeded, but Defender ASR blocked `KeychronShortcuts.exe` at **16:22:42 UTC**, event **1121**, rule **01443614-CD74-433A-B99E-2ECDC07BFC25**. No helper process/startup or automated-suite run was established. |
| AutoHotkey | Official vendor download blocked by corporate unevaluated-site policy; not installed through that route. |
| Existing macOS modifier-remap hypothesis | Global and Q11-specific `UserKeyMapping` / `HIDKeyboardModifierMappingPairs` returned null; current/global preferences had no modifier mappings. This check yielded no fix. |

The ASR event identifies an executable reputation/age/trust restriction, not a general ban on PowerShell or proof that compilation implies launch permission. Minimal current-console Get/SetConsoleMode code ran; official signed PowerToys installed normally. Do not recreate the blocked helper through in-memory execution, rename it, weaken policy, or evade the AutoHotkey restriction through mirrors. [Microsoft ASR reference](https://learn.microsoft.com/en-us/defender-endpoint/attack-surface-reduction-rules-reference)

## Diagnostic traps and working mechanics

**Console input is not editor behavior.** Terminal/ConPTY can reconstruct modifier sides: the ordinary VT decoder reconstructs Control characters with Left Ctrl; richer win32 input carries control-state fields. The negotiated protocol was not established. Standalone `conhost.exe -ForceNoHandoff powershell.exe -NoLogo -NoProfile -NoExit -File "<owned path>"` avoided Terminal delegation and ran the hash-verified probe. [VT decoder](https://github.com/microsoft/terminal/blob/main/src/terminal/parser/InputStateMachineEngine.cpp), [win32 serialization](https://github.com/microsoft/terminal/blob/main/src/terminal/input/terminalInput.cpp)

Classic-console content clicks entered QuickEdit (`Select` title/white caret), invalidating early trials. The corrected probe temporarily disabled QuickEdit for its own console, with mode 439 observed, and restored the original mode afterward. Focus title bars/taskbar when available. Many similarly named Untitled Notepads caused wrong-window tests; use a uniquely named owned fixture, not another ambiguous window.

**Ignore dummy events before accepting a sample.** PowerToys defines `DUMMY_KEY=0xFF` and injects it before the real Alt remap. The first arrow probe consumed VK255 and flushed away the real arrow. Its corrected version ignores 255 and captured Option-Left as **VK37 + LeftCtrlPressed, NumLockOn, EnhancedKey** at **18:16:05.5344133 UTC**, and Command-Left as **VK36/Home + NumLockOn, EnhancedKey**, no Ctrl, at **18:16:07.7552234 UTC**. [Constant](https://github.com/microsoft/PowerToys/blob/v0.101.2362.0/src/modules/keyboardmanager/common/KeyboardManagerConstants.h), [dummy-event handling](https://github.com/microsoft/PowerToys/blob/v0.101.2362.0/src/modules/keyboardmanager/common/Helpers.cpp)

**Use Terminal for transfers.** Chunked exact text/Base64 plus guest hash verification worked there. Classic interactive PowerShell ignored Unicode-requested input; direct `-File` execution worked. Terminal loaded PSReadLine 2.0.0; its historical [Packet/Unicode RDP fix](https://github.com/PowerShell/PSReadLine/pull/2632) is only a candidate explanation because the failing classic prompt's module version was not verified.

**Preserve settings transactions.** Back up current files, check for drift, stop PowerToys and Settings before replacement, and restart normally afterward. PowerShell 5.1 `File.Replace(...,$null,$true)` coerced the backup argument to an invalid empty path; supplying a real backup filename worked. The setup script's `-FreshInstallation` is only for a verified fresh baseline, never normal repeats.

## What remains to be figured out

The cause of **correct console events but failed Notepad navigation is unknown**. The next investigation must distinguish the actual modifier sides/state reaching Notepad, application/engine integrity, and effective remap handling. These are hypotheses, not findings. No user input-monitoring or hook change was installed to settle them. A running engine does not prove its hook remains effective; a hook timeout was considered but never demonstrated here.

Do not blindly apply these source-reviewed ideas as fixes:

- Setting `exactMatch:false` is not a general solution: shortcut-to-shortcut paths retain a separate unconditional state-clear check. Mouse buttons and VK255 are already ignored by that check.
- Changing Command sources from `163` to generic Ctrl `17` would also alter physical Control behavior. It can accept both Ctrl sides while restoration leaves the other held. It was not applied or tested. Shortcut-generated Alt→Ctrl output is flagged to avoid recursive shortcut remapping; single-key-generated Ctrl remains eligible.

These conclusions came from the installed-version [shortcut handler](https://github.com/microsoft/PowerToys/blob/v0.101.2362.0/src/modules/keyboardmanager/KeyboardManagerEngineLibrary/KeyboardEventHandlers.cpp), [Shortcut.cpp](https://github.com/microsoft/PowerToys/blob/v0.101.2362.0/src/modules/keyboardmanager/common/Shortcut.cpp), and Helpers.cpp linked above.

The remaining physical tests include current-transport A/S/W, copy/cut/paste/find/undo, all navigation/selection directions, redo, and browser tabs. Test Command-T in the intended browser; Notepad tab support/binding was not established for this guest. Q11 screenshot shortcuts explicitly failed on 2026-09-13; retry after a meaningful change, not as an untested configuration. The mouse route produced a bounded guest image and verified Paint paste. Snipping Tool auto-save remains unverified.

PowerToys' current profile does not implement Command-Delete line deletion. Stock VIA fixed macros cannot inspect caret/selection or branch on held Shift. Repurposing Windows Fn layer 3 as a Command layer was considered, not applied: it conflicts with existing Fn controls and does not cleanly handle Shift-dependent redo/tab/screenshot outputs. Custom firmware was not flashed.

## Hardware state, artifacts, and recovery

Q11: VID `0x3434`, PID `0x01E0`, VIA 11, raw interface usage page `0xFF60` / usage `0x61`, matrix 12×9, four layers, two encoders per layer. The first nine-key stage applied at **15:56:27 UTC**. At **18:13:40 UTC**, four guarded replacements changed Windows layer 2 Command positions row/column **5/3, 5/4, 11/2** to Right Alt, and physical right Control **11/3** to Left Control. Left Option remains Left Alt, Fn is **11/4**, and Fn+Command remains GUI/Windows. Current keymap SHA-256: `507faf86ccab178ddc71de9c0846ff12fe6656b97b4fe3cb169f7bcf8e5d28ee`.

Repeated full readbacks verified Mac layers 0/1 and all macro/encoder bytes unchanged. The original Mac layer already had two adjacent left Command assignments; preserve the backup, not an assumed factory layout. Concurrent raw-HID clients caused `open failed`; release/coordinate the existing client rather than inferring a permissions problem.

**Stored-keymap readback cannot verify the physical switch position.** Stock VIA exposes no active/default-layer or DIP-switch getter. Q11's separate GPIO A8 callback selects default layer 0/2; the matrix getter does not read that switch. No supported live-mode query was established, and this is not evidence that the user selected the wrong mode. [VIA protocol](https://github.com/Keychron/qmk_firmware/blob/403b0addea48548abdbde6203d8673f2b77164a7/quantum/via.c), [Q11 switch handler](https://github.com/Keychron/qmk_firmware/blob/playground/keyboards/keychron/q11/q11.c)

Local workspace root: `/Users/henry/Documents/Codex/2026-09-10/i-hav/`. Relative artifact paths below are outside this documentation-only skill and will not accompany a shared copy.

| Artifact | Status / use |
| --- | --- |
| `outputs/q11-original-20260910T155128Z.json` | Full original raw keymap/macros/encoders; repeat-read verified |
| `outputs/q11-original-via.layout.json` | Original VIA format; local symbolic round-trip passed; GUI import untested |
| `outputs/q11-apply-receipt-20260910T155627486211Z.json` | First nine-key application receipt |
| `outputs/q11-alt-apply-receipt-20260910T181340660802Z.json`, `q11-before-alt-20260910T181340660802Z.json`, `q11-alt-transport-proposed.json` | Latest four-key receipt, before snapshot, plan; latter two also under `outputs/` |
| `work/q11-backup/configure_alt_transport.py`, `configure_windows.py` | Live application/readback passed; rollback/failure simulations passed; **live restore untested** |
| `outputs/configure-powertoys.ps1`, `desired-mappings.json`, `powertoys-setup-and-rollback.md` | Keep together. Latest script repeat-guard revision was reviewed, not re-executed in Windows |
| `work/windows-powertoys/console-arrow-probe.ps1` | Corrected, guest-executed probe; SHA-256 `afd92253936c0ecbc6e13563cbe7d94bc59c35b30ce50f5aba600054ce726acd` |
| `work/diagnose-context.ps1` | Prepared/read-only source review; **not executed**. Process integrity, layouts, profile, bounded Notepad modifier samples; post-hook asynchronous snapshots cannot prove the exact pre-hook state |
| `work/windows-powertoys/form-modifier-probe.ps1`, `text-shortcut-tests.ps1` | Prepared, **not executed**; not a validated suite or a substitute for Notepad evidence |

For an authorized hardware rollback, use `work/q11-hid-venv/bin/python` and inspect the guarded helper `status` first. Undo the **latest four-key stage** with `configure_alt_transport.py restore`; only then use `configure_windows.py restore` for full original restoration. Both default to offline `plan` and guard the complete expected state. Unexpected state requires investigation, not resetting Mac layers.

Guest rollback is separate. The latest pre-transport profile is `%LOCALAPPDATA%/KeychronMacWindows/powertoys-before-alt-20260910T141313.json` (plus `.replace`); the initial audited backup is `powertoys-backup-20260910T164427704Z-3c17b701` in that parent. Stop PowerToys/settings, preserve current files, and follow the package guide while retaining later user changes. Undoing only the four-key stage also requires undoing the guest `165→163` mapping. The blocked custom helper's unused `--stop` does not control PowerToys.

## MacBook-only portability

VM-control lessons apply without a Keychron; this hardware recipe does not. Windows App supports built-in Mac keyboards and translates some Command shortcuts. A Karabiner-based, foreground-Windows-App alternative was discussed; its signed DMG was downloaded only, not installed, permissioned, or tested. [Windows input](https://learn.microsoft.com/en-us/windows-app/input-keyboard-mouse-touch-pen), [Karabiner application conditions](https://karabiner-elements.pqrs.org/docs/json/complex-modifications-manipulator-definition/conditions/frontmost-application/)

For a requested laptop-keyboard setup, account for double translation, Windows App settings windows matching the same app rule, screenshot destinations, and return to Mac applications. Sharing this skill shares documentation, not a working keyboard configuration or the local helpers above.
