---
name: verify-page
description: Open a route in a real browser with Playwright, capture a screenshot, and visually inspect the result before claiming the page works. Use when the user asks you to see a page, verify that a route loads, or check UI changes directly.
---

# Verify Page

Use this skill when the user wants proof that a page loads in a browser or wants you to inspect the UI directly instead of inferring from code alone.

## What To Do

1. Resolve the target URL first.
   Prefer an explicit URL from the user.
   If the user only gives a route, combine it with the active local origin.
   If you must guess a default local origin, try `http://127.0.0.1:3000`.

2. Make sure the page is reachable.
   Reuse an already-running local server when possible.
   If you need to start one, use the repo's normal dev command, wait until the page responds, and stop the server before finishing unless the user explicitly asked to keep it running.

3. Capture visual evidence with Playwright.
   Save screenshots outside the repo, normally under `/tmp/job-helper-verify-page/`.
   Headless browser capture is the default.
   Prefer a full-page screenshot with a desktop viewport.
   For unpacked extension verification, prefer bundled Chromium over Google Chrome because Chromium reliably honors extension-loading flags.
   If Playwright cannot reach MV3 service workers or extension pages cleanly, use Chromium plus CDP while staying headless.
   Use `--wait-for-selector` when the page has a stable landmark worth waiting for.

4. Inspect the screenshot directly after capture.
   Open the saved image in Codex so you actually look at the rendered UI.
   Check for blank screens, framework error overlays, redirects to the wrong page, clipped content, missing sections, and obvious layout regressions.

5. Report what you observed, not just whether the command exited successfully.

## Default Commands

Quick smoke check:

```bash
mkdir -p /tmp/job-helper-verify-page
npx playwright screenshot --browser chromium --full-page --viewport-size "1440,2200" "http://127.0.0.1:3000/dashboard" "/tmp/job-helper-verify-page/dashboard.png"
```

Wait for a specific element before the screenshot:

```bash
npx playwright screenshot --browser chromium --full-page --viewport-size "1440,2200" --wait-for-selector "[data-testid='dashboard-shell']" "http://127.0.0.1:3000/dashboard" "/tmp/job-helper-verify-page/dashboard.png"
```

Reuse saved auth state when needed:

```bash
npx playwright screenshot --browser chromium --full-page --load-storage /tmp/job-helper-verify-page/auth.json "http://127.0.0.1:3000/dashboard" "/tmp/job-helper-verify-page/dashboard.png"
```

Useful flags:

- `--wait-for-timeout 2000` when the page animates in or data settles shortly after load.
- `--device "iPhone 13"` when you need a mobile rendering check.
- `--save-har /tmp/job-helper-verify-page/page.har` when network details matter.

## What Counts As Verified

Only say the page was verified when all of these are true:

- The URL loaded in a real browser.
- A screenshot was saved successfully.
- You visually inspected the screenshot.
- You called out any blocking issue or uncertainty you noticed.

## Constraints

- Do not treat `curl`, HTML, or build output alone as visual verification.
- Do not claim the UI looks correct unless you inspected the screenshot.
- Do not switch to a headed browser unless the surface truly depends on browser chrome or focus behavior that a headless browser cannot expose.
- Do not leave a local dev server running unless the user asked for that explicitly.
- Keep screenshots and temporary browser artifacts out of git-tracked paths unless the user asks otherwise.
- If Playwright is missing a browser install, auth state, or another prerequisite, say exactly what is missing.

## Final Response

Include:

- the URL you checked
- whether it loaded visually
- the screenshot path
- any obvious UI issues or uncertainty
- whether you started and stopped a local server
