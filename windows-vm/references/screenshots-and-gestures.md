# Guest screenshots and macOS gestures

Snapshot: **2026-09-13**, Windows App **11.4.0**, physical **Keychron Q11**. Screenshot shortcuts and intermittent swipe behavior remain unresolved.

## Capture inside Windows

The user's requirement is **physical Command-Shift-4 for region capture and Command-Shift-3 for full-screen capture while the VM is active**, with both images accessible inside Windows. A native CUA `app.getScreenshot()` successfully showed the guest to the agent, but that observation alone does not put an image on the Windows clipboard or filesystem. The user reports that built-in Mac Command-Shift-4 saves a screenshot accessible only on the Mac.

The following guest mouse workflow succeeded while remote controls were available:

1. Open Windows Start, then **Snipping Tool**.
2. Select **New**, select a bounded region, and verify the captured image appears in Snipping Tool.
3. Use the guest Save dialog. The save action completed with `windows-screenshot-test-2026-09-13.png` in guest Pictures; no separate filesystem readback was performed.
4. Select Snipping Tool's **Copy** button, open guest **Paint**, and paste. The captured image visibly appeared in Paint, establishing that it was accessible inside Windows.

The user's physical Q11 **Command-Shift-3 and Command-Shift-4 did nothing**. Guest remap entries and a working mouse capture do not establish shortcut success. Do not present either chord as a working solution or claim Snipping Tool auto-save was tested. The verified mouse route provides immediate capture but does not fulfill the exact shortcut requirement.

An isolated Q11 Windows Fn-layer **Fn+4 → Win-Shift-S** test binding was applied, then rejected by the user because it changed the requested chord. It was immediately restored without a successful physical test; two full readbacks matched the original keymap SHA-256 `507faf86ccab178ddc71de9c0846ff12fe6656b97b4fe3cb169f7bcf8e5d28ee`. Mac layers, macros, and encoders were preserved. **Do not propose Fn+4 again or substitute other hardware chords.** The exact Command chords remain the requirement.

Remote coordinate clicks later returned `noWindowsAvailable` after resizing/focus changes. Raising/zooming did not reliably recover them. Capture and input are separate capabilities: a failed click does not mean `app.getScreenshot()` cannot capture the session. Inspect current state and avoid repeated identical recovery attempts.

## Leaving the VM with three fingers

Live macOS Trackpad settings already showed horizontal **Swipe between full-screen applications: three fingers** and **Mission Control: three fingers up**. Horizontal swipe was toggled off, restored to three fingers, and verified in the UI. Windows App's `FullScreenMode` was already **System**.

The user reports that three-finger swipe sometimes works, then stops after entering and exiting the VM. The restored preference is configuration evidence only; it did not establish a behavioral fix. After Windows App was normally quit and reopened to its device list with the VM disconnected, the user confirmed that three-finger swipe worked again. Initially, reconnecting returned to full screen despite the previous normal-window session. After selecting **Window → Exit Full Screen**, the user explicitly confirmed that three-finger swipe worked in windowed mode.

**Current verified workaround:** use the VM in a normal window after this client restart. Device custom settings were subsequently changed to `StartSessionInFullScreen=false`, and the reconnected session visibly opened in a normal window; see [current client settings](vm-control.md). This supports investigating session/client runtime state; it does not establish a universal cause or a permanent full-screen fix. Recheck the actual window mode after reconnecting.

Do not repeat setting changes as though the feature was merely disabled. Verify behavior after entering and leaving the VM, and distinguish the full-screen transition from losing gesture behavior afterward. No cause for the intermittent failure has been established.
