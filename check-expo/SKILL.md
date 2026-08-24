---
name: check-expo
description: Verify Expo React Native apps in mobile-native runtimes and capture screenshots. Use when the user asks to check, debug, visually inspect, screenshot, or prove an Expo app works in Expo Go, a development build, iOS Simulator, Android Emulator, or on mobile rather than only in the web browser.
---

# Check Expo

Use this skill to prove what an Expo app looks like in a native mobile runtime. Browser screenshots are not enough unless they are explicitly labeled as web-only fallback.

## Workflow

1. Read repo instructions first.
   Check `AGENTS.md`, `CLAUDE.md`, and repo docs before editing code or starting servers. If a repo pins Expo docs, obey that requirement.

2. Identify the runtime target and stay headless first.
   Prefer the target implied by the user: Expo Go, development build, iOS Simulator, Android Emulator, or physical device. If unspecified, use headless iOS Simulator automation when available, then headless Android Emulator automation, then headed simulator/emulator only when headless is blocked, then iOS/Android bundle export, then web fallback. Do not use iPhone Mirroring unless the user explicitly asks for physical-device verification or the bug requires real-device hardware.

3. Run static and dependency checks.
   Prefer the repo's scripts when present, then run:
   ```bash
   npx expo install --check
   npx expo-doctor
   npm run typecheck
   ```
   If `npm run typecheck` does not exist, skip it and say so.

4. Verify native bundle creation.
   Run the platform-specific export check:
   ```bash
   npx expo export --platform ios --output-dir /tmp/<repo>-ios-export --clear
   ```
   or:
   ```bash
   npx expo export --platform android --output-dir /tmp/<repo>-android-export --clear
   ```
   Treat this as bundle verification, not visual verification.

5. Start Metro with a clean cache.
   Use a deterministic port when possible:
   ```bash
   npx expo start --port 8082 --clear
   ```
   Keep the server running until runtime verification is complete. Stop servers started only for the check unless the user asks to keep them.

6. Capture a native screenshot headlessly first.
   For iOS Simulator, use `xcrun simctl`. A successful native visual check requires:
   - `xcrun simctl list devices` works
   - a booted simulator exists or can be booted
   - Expo Go or the development build is installed
   - the app loads from Metro
   - `xcrun simctl io booted screenshot <path>` creates an image

   If `simctl` is unavailable because Xcode is not installed or not selected, say that native screenshots are blocked and report the exact `xcode-select -p` / `xcrun simctl` result.

   For Android Emulator, use `emulator -no-window` plus `adb`. A successful native visual check requires:
   - `adb devices` sees an emulator as `device`
   - Expo Go or the development build is installed
   - the app loads from Metro using `exp://10.0.2.2:<port>` from inside the emulator
   - `adb exec-out screencap -p > <path>` creates an image

   If the only AVD is `x86_64` and headless launch fails with `failed to initialize HVF`, `failed to initialize HAX`, or `No accelerator found`, say that Android headless screenshots are blocked until an accelerated emulator or compatible ARM image is installed.

7. Inspect the screenshot directly.
   Open the saved image with Codex image viewing tools before claiming success. Classify the visual result as rendered, redbox, blank, stuck loading, permission prompt, or wrong surface.

8. Save artifacts under this skill.
   Use:
   ```text
   /Users/Henry/.codex/skills/check-expo/repos/<repo-key>/
     screenshots/
     logs/
     exports/
     workflow.md
   ```
   Keep screenshots and logs out of the product repo unless the user asks otherwise.

9. Interact with the mobile runtime when the visual state is blocked by native UI.
   Screenshots alone can prove rendering, but they are not enough when a modal, permission prompt, or Expo Go overlay blocks the app. Prefer stable automation in this order:
   - Android Emulator: use `adb shell input tap <x> <y>` and `adb shell input text ...` for basic headless interaction.
   - iOS Simulator: use Maestro when installed. It can inspect hierarchy, tap visible text, tap coordinates, handle iOS permission prompts, and save screenshots/debug artifacts.
   - iOS Simulator fallback: use the visible Simulator window plus `cliclick` only after bringing Simulator frontmost and capturing screenshots after every tap.
   - Physical iPhone/iPhone Mirroring: only when explicitly requested or when simulator behavior is insufficient.

   `xcrun simctl` can boot, launch, open URLs, terminate apps, and take screenshots, but it does not provide a general tap command. Do not treat that as "iOS cannot be interacted with"; it means taps need a different layer.

## Helper Script

Use `scripts/check-expo.sh` for the common path:

```bash
/Users/Henry/.codex/skills/check-expo/scripts/check-expo.sh --platform ios --port 8082
```

The script performs dependency checks, bundle export, Metro startup, and headless simulator/emulator screenshot capture when native tools exist. It is allowed to return `native_screenshot=blocked` when Xcode/simulator/emulator tooling is missing or unusable; that is a real environmental blocker, not an app pass.

Use `scripts/maestro-expo-flow.sh` for interactive mobile UI flows:

```bash
/Users/Henry/.codex/skills/check-expo/scripts/maestro-expo-flow.sh \
  --platform ios \
  --device <simulator-udid> \
  --flow <flow.yaml>
```

The script sets Maestro environment variables, checks flow syntax, runs the flow, and writes screenshots/logs under:

```text
/Users/Henry/.codex/skills/check-expo/repos/<repo-key>/screenshots/maestro/
/Users/Henry/.codex/skills/check-expo/repos/<repo-key>/logs/maestro/
```

## Native Interaction Notes

Use this section as field memory. It is allowed to grow with repeated prompts, coordinates, known Expo Go quirks, and command snippets that save future debugging time.

### Recommended Automation

- Prefer Maestro for repeatable mobile UI flows. It gives semantic steps such as `tapOn`, `assertVisible`, `takeScreenshot`, hierarchy inspection, and debug artifacts, which are much less brittle than desktop coordinates.
- If Maestro is unavailable and installation is acceptable, install it before doing extended iOS app exploration. Coordinate tapping is acceptable for a one-off unblock, but not for a serious interaction script.
- Android is easier to drive headlessly because `adb shell input tap x y` works against emulator framebuffer coordinates.
- iOS Simulator can be visually inspected headlessly with `simctl io booted screenshot`, but interaction needs either UI automation or a headed Simulator window plus a mouse-control helper such as `cliclick`.
- Consider Appium/XCUITest only if Maestro cannot express the needed interaction, cannot see a control, or deeper native automation is required. For normal Expo app exploration, Maestro is the fastest working layer.

### Local Maestro Setup

Henry's Mac has Maestro installed at `~/.maestro` via:

```bash
curl -Ls https://get.maestro.mobile.dev | bash
```

Current observed version: `2.6.1`. The install used about `344M`.

Use these environment variables for quiet local runs:

```bash
export PATH="$PATH:$HOME/.maestro/bin"
export MAESTRO_CLI_NO_ANALYTICS=1
export MAESTRO_CLI_ANALYSIS_NOTIFICATION_DISABLED=true
```

Useful commands:

```bash
maestro list-devices
maestro hierarchy
maestro check-syntax flow.yaml
maestro test --platform ios --device <simulator-udid> flow.yaml
```

For this machine's iPhone 17 simulator, the known UDID is:

```text
7EDA4327-C24A-4E2D-B7AC-CF587966F91E
```

Prefer the UDID over the friendly name because `maestro test --device iPhone-17` was not accepted even though `maestro list-devices` displayed that name.

### Maestro Flow Patterns

Templates live in:

```text
/Users/Henry/.codex/skills/check-expo/templates/maestro/
```

Current templates:

- `ios-expo-overlay-close.yaml`: coordinate tap for the normal Expo Go developer menu bottom sheet.
- `ios-expo-smoke.yaml`: skeleton for semantic app assertions/taps.
- `ios-allow-photos.yaml`: handles the iOS Photos permission prompt.
- `ios-photos-picker-select-first.yaml`: coordinate tap for the first visible photo in the iOS Photos picker.
- `android-expo-smoke.yaml`: skeleton for Android semantic app assertions/taps.

Repo-specific flows and screenshots should go under:

```text
/Users/Henry/.codex/skills/check-expo/repos/<repo-key>/flows/
/Users/Henry/.codex/skills/check-expo/repos/<repo-key>/screenshots/maestro/
```

Example iOS flow:

```yaml
appId: host.exp.Exponent
---
- assertVisible: "Habit Tracker"
- tapOn: "Import a photo"
- waitForAnimationToEnd
- takeScreenshot:
    path: ios-after-import-photo-tap
```

If the flow fails, inspect Maestro's generated failure screenshot and command JSON before changing code. A failure can mean the app is in a different valid state, such as the iOS Photos picker being open.

### Observed Habit Tracker iOS Flow

This project has proven working iOS Expo Go interaction via Maestro:

1. Close Expo Go developer menu overlay with `ios-expo-close-overlay.yaml`.
2. Tap `Import a photo` via semantic text.
3. Handle iOS Photos permission with `Allow Full Access`.
4. Select the first visible photo in the native Photos picker.
5. Verify the app returns to `Habit Tracker` and renders `Photo copied into private app storage.` plus the selected image.

Useful screenshot artifact:

```text
/Users/Henry/.codex/skills/check-expo/repos/habbit-tracker-/screenshots/maestro/screenshots/ios-after-select-first-photo.png
```

### iOS Simulator `cliclick` Fallback

Use this when a native iOS prompt or Expo Go overlay blocks the screen and no UI automation layer is available.

1. Bring Simulator frontmost and put the window in a known location:
   ```bash
   osascript <<'APPLESCRIPT'
   tell application "Simulator" to activate
   delay 0.3
   tell application "System Events"
     set frontmost of process "Simulator" to true
     tell process "Simulator"
       set position of window 1 to {80, 60}
     end tell
   end tell
   APPLESCRIPT
   ```

2. Capture before tapping:
   ```bash
   xcrun simctl io booted screenshot /tmp/before-tap.png
   ```

3. Tap with `cliclick`, then capture again:
   ```bash
   /opt/homebrew/bin/cliclick c:<desktop-x>,<desktop-y>
   sleep 1
   xcrun simctl io booted screenshot /tmp/after-tap.png
   ```

4. Inspect the screenshot directly. If the tap missed, recalibrate from the visible Simulator window, not from raw simulator framebuffer pixels. The screenshot may be 3x device pixels while `cliclick` uses macOS desktop points.

Known useful coordinates from the iPhone 17 Simulator on Henry's Mac when the Simulator window is positioned at `{80, 60}`:

- Expo Go first-run developer-menu tutorial `Continue`: `cliclick c:282,817`
- This tap advanced the tutorial into the normal Expo developer menu for the Habit Tracker app.
- Close buttons and other top-right glyphs are more sensitive to Simulator scaling; verify with screenshots and prefer Maestro if repeated.

If `cliclick` is missing and the install is small, install with:
```bash
brew install cliclick
```

### Expo Go Overlays

- Expo Go may show an iOS external-link confirmation sheet: `Open in "Expo Go"?`. `simctl openurl booted exp://127.0.0.1:<port>` can trigger it. Use a visible Simulator click or UI automation to tap `Open`.
- Expo Go may show a first-run developer-menu tutorial over an otherwise rendered app. This is not an app crash. The sheet can obscure the app while the app is fully running behind it.
- After dismissing the first-run tutorial, Expo Go can show the normal developer menu bottom sheet with project name, SDK version, runtime version, `Reload`, `Go Home`, and debugging actions. This is still an Expo overlay, not necessarily a product UI problem.
- Use Maestro before `cliclick` for these overlays when possible. `tapOn` by visible text works for many prompts; coordinate taps such as `point: 94%,33%` can close the normal Expo Go developer menu.

### Development Builds

- A native debug build made by `npx expo run:ios` is not automatically an Expo development-client app. If `expo-dev-client` is missing, the app can build and install but still show `No script URL provided` when opened with an `expo-development-client` URL. Install it with:
  ```bash
  npx expo install expo-dev-client
  npx expo prebuild --platform ios
  PATH="/opt/homebrew/bin:$PATH" bash -lc 'cd ios && pod install'
  ```
- On Henry's Mac, prefer Homebrew CocoaPods with `PATH="/opt/homebrew/bin:$PATH"`. The old system Ruby/CocoaPods path can fail on Apple Silicon with an x86_64 `ffi` native extension.
- When `expo-dev-client` is installed correctly, `npx expo run:ios --device <udid> --port <port>` should open a URL shaped like:
  ```text
  exp+<slug>://expo-development-client/?url=http%3A%2F%2F<host>%3A<port>
  ```
  If it opens an OAuth callback scheme instead, inspect `app.json` and generated `Info.plist` URL schemes.
- Do not put OAuth callback schemes beside the app launch scheme in the top-level Expo `scheme` array. It can make Expo CLI pick the wrong scheme for dev-client launch. Keep a single app scheme such as `habittracker`, and add extra iOS OAuth schemes through a config plugin that appends to `CFBundleURLTypes` after Expo has generated the app/dev-client schemes.
- Directly setting `ios.infoPlist.CFBundleURLTypes` can make Expo ignore the abstract `scheme` property during prebuild. If both are needed, prefer a config plugin that modifies `Info.plist` rather than a raw `ios.infoPlist.CFBundleURLTypes` override.
- The iOS external-link confirmation prompt for a dev build says `Open in "<App Name>"?`. Use Maestro by UDID:
  ```yaml
  appId: com.example.app
  ---
  - tapOn: "Open"
  - waitForAnimationToEnd
  - takeScreenshot:
      path: ios-dev-client-after-open
  ```
- Expo dev-client may show a first-run developer menu sheet over a successfully rendered app. For the iPhone 17 simulator used here, the normal sheet close button worked with:
  ```yaml
  - tapOn:
      point: "90%,49%"
  ```
  Capture a screenshot after closing to prove the actual app UI is visible.

### Google Sign-In / OAuth

- Expo Go cannot fully prove local Google OAuth redirects for apps that need a custom native URL scheme. Expo Go can load the app, but Google may reject the redirect as `Error 400: invalid_request` with `redirect_uri=exp://127.0.0.1:<port>`. Treat that as an Expo Go runtime limitation, not necessarily an app auth bug.
- For Google OAuth in a development build, register the reversed iOS client ID scheme from `GoogleService-Info.plist`, for example:
  ```text
  com.googleusercontent.apps.<ios-client-id-prefix>
  ```
  Pair it with an auth-session native redirect like:
  ```text
  com.googleusercontent.apps.<ios-client-id-prefix>:/oauthredirect
  ```
- A healthy iOS development-build Google start shows the ASWebAuthenticationSession prompt branded with the app name, such as `"HabitTracker" Wants to Use "accounts.google.com" to Sign In`, not `"Expo" Wants...`.
- Use Maestro environment variables for credentials and never write passwords into repo flows:
  ```bash
  maestro test --device <udid> -e GOOGLE_EMAIL='name@example.com' flow.yaml
  maestro test --device <udid> -e GOOGLE_PASSWORD='...' flow.yaml
  ```
  Plain shell environment variables are not enough for `${GOOGLE_PASSWORD}` / `${GOOGLE_TOTP_CODE}` expansion in Maestro flows. Pass values with Maestro `-e`, otherwise Maestro can type `undefined`.
  Flow files should contain placeholders only:
  ```yaml
  - inputText: "${GOOGLE_EMAIL}"
  ```
- Maestro may still expand `-e` values into debug/test artifacts such as `commands-*.json`, XCTest runner logs, and the default `~/.maestro/tests/<timestamp>/` run logs. For real credentials, either avoid `--debug-output` and persistent `--test-output-dir` during the secret entry step, or delete fresh artifact directories immediately and scan them with `rg` for the secret value.
- On iOS Google sign-in screens, the on-screen keyboard can cover Google's `Next` button. The keyboard submit key worked on the iPhone 17 simulator at:
  ```yaml
  - tapOn:
      point: "87%,89%"
  ```
- Henry's Google Account has a persistent Google Authenticator/TOTP secret for OAuth debugging across Expo apps. Store it globally under this skill, not in a product repo:
  ```text
  /Users/Henry/.codex/skills/check-expo/secrets/google-totp.env
  ```
  This file is intentionally gitignored by `/Users/Henry/.codex/skills/.gitignore` and should never be committed or copied into screenshots/logs. Generate a current 6-digit code from any Expo repo with:
  ```bash
  /Users/Henry/.codex/skills/check-expo/scripts/google-totp-code.py
  ```
  The helper reads `GOOGLE_TOTP_SECRET` from the global skill secret by default. It also supports `GOOGLE_TOTP_ENV=<path>`, `GOOGLE_TOTP_SECRET=<secret>`, and the old repo-local `.codex-google-totp.env` fallback. It prints the current code to stdout and `seconds_remaining=<n>` to stderr. For slow UI automation, generate the code at the final input screen with:
  ```bash
  /Users/Henry/.codex/skills/check-expo/scripts/google-totp-code.py --min-remaining 20
  ```
  `--min-remaining` waits until the current or next 30-second window has enough lifetime left. Use 20-25 seconds for Maestro/Simulator flows so the code is still valid after command startup and keyboard input.
- For fully automated Google OAuth in the iOS Simulator:
  1. Drive email/password with Maestro.
  2. Choose `Try another way` if Google starts with passkey.
  3. Choose `Get a verification code from the Google Authenticator app`.
  4. Navigate all the way to the 6-digit code field first, then generate a fresh code with `scripts/google-totp-code.py --min-remaining 20`.
  5. Enter only the 6-digit code into Maestro. Do not pass the long-term TOTP secret through Maestro `-e` because debug artifacts can persist expanded env values.
  6. On the Google Authenticator code page, the numeric keyboard can cover or intercept the page submit. This sequence worked on the iPhone 17 simulator:
     ```yaml
     - eraseText: 6
     - inputText: "${GOOGLE_TOTP_CODE}"
     - tapOn:
         point: "89%,61%" # keyboard/accessory checkmark; dismisses keyboard
     - tapOn: "Next"      # visible page button after keyboard dismiss
     ```
     If a screenshot is captured while a 6-digit code is visible, delete it after inspection even though the code is short-lived.
- Fast repeat sign-in after a successful Google OAuth is much faster than the first credential+2FA flow because Google remembers the account in the ASWebAuthenticationSession/Safari state. On Habit Tracker, after signing out of Firebase but not clearing Safari/Google session state, the reauth path is:
  ```yaml
  appId: com.henry.habittracker
  ---
  - tapOn: "Sign out"
  - tapOn: "Continue with Google"
  - tapOn: "Continue"      # Apple ASWebAuthenticationSession prompt
  - waitForAnimationToEnd
  - tapOn:
      point: "52%,43%"     # remembered account row on iPhone 17 simulator
  - waitForAnimationToEnd
  - tapOn: "Continue"      # "You're signing back in to <app>"
  - waitForAnimationToEnd
  - assertVisible: "Signed in as Henry Deutsch"
  ```
  Observed timing on Henry's iPhone 17 simulator: this single Maestro invocation succeeded in about 29.4 seconds. A broad exploratory version with an in-flow screenshot took about 26.5 seconds but stopped at the account chooser, not signed in. Separate Maestro invocations are much slower because each run pays driver/startup and selector wait overhead.
- Do not chase pure coordinate-only Google OAuth flows unless the screen is already known and stable. A coordinate-heavy sign-out/sign-in attempt missed the delayed Apple sign-in prompt and failed after about 44 seconds. State-aware semantic taps for the OS `Continue` prompt and final Google `Continue` are slower but reliable.
- A failed Maestro assertion/selector can burn 30+ seconds waiting for timeout. Before timing a speed-critical flow, confirm the starting screen with `simctl io <udid> screenshot` or `maestro hierarchy --compact`; do not use a long failing assertion as the probe.
- Beating a 20-second sign-out/sign-in target is unlikely with fresh `maestro test` CLI invocations on this setup. To get below that, use a lower-overhead interaction layer such as a persistent Maestro MCP/driver session if available, XCUITest/WebDriverAgent calls kept warm, or a calibrated visible-Simulator click helper. Keep Maestro as the reliable default for correctness and screenshots.
- Google account security can still block full headless completion after password entry with passkey, QR-code, or 2-step verification challenges. Capture that screen and report it as an external account-verification blocker rather than an Expo/app compile failure.
- Do not assume a separate browser or Gmail inbox can bypass Google 2-Step Verification. In the observed Habit Tracker flow, Google offered passkey, one-time security-key code, phone/tablet prompt, Google Authenticator, an unavailable SMS phone ending in `61`, backup codes, and another-way retry. There was no email-code option. A browser/Gmail helper is only useful if Google actually sends a code or link to an inbox or if a trusted browser already has access to the required second factor.
- Expo Go stores some onboarding and app history state in its simulator app container. Useful places to inspect:
  ```bash
  APP_DATA=$(xcrun simctl get_app_container booted host.exp.Exponent data)
  find "$APP_DATA" -maxdepth 6 -type f
  defaults read "$APP_DATA/Library/Preferences/host.exp.Exponent.plist"
  ```
- Known Expo Go defaults seen in SDK 54 simulator builds include `EXHomeIsNuxFinishedDefaultsKey`, `EXDevMenuMotionGestureEnabled`, and `EXDevMenuTouchGestureEnabled`. Setting defaults may help with home-screen onboarding, but it did not reliably suppress the per-project developer-menu overlay in the observed SDK 54 flow.

## Diagnosis Rules

- Expo Go compatibility failures usually mean SDK/runtime mismatch; compare `expo` in `package.json` with the installed Expo Go version.
- Metro bundle success does not guarantee runtime success. Redboxes from Firebase, native modules, or platform-specific imports require native runtime loading.
- Web rendering is a fallback surface. It can help inspect layout but must not be reported as proof of Expo Go/mobile success.
- If the app uses Firebase Auth and fails with `Component auth has not been registered yet`, inspect Metro resolver config for Firebase `.cjs` handling and package exports.
- If a screen depends on camera, photos, auth redirects, notifications, or hardware behavior, prefer simulator only for first-pass rendering and ask before using iPhone Mirroring or the physical phone.

## Final Response

Report:

- target runtime and platform
- commands/checks run
- whether native bundle export passed
- whether native screenshot was captured or why it was blocked
- screenshot path and inline image preview when available
- visual verdict from direct screenshot inspection
- remaining uncertainty
