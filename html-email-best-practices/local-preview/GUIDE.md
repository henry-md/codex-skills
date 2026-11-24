# Local email previews on this Mac

Use Gmail web, Outlook web and Apple Mail for Mac as a small, warm feedback loop. Windows clients are deferred. These are actual clients; opening the HTML in an ordinary browser tab is a separate layout check.

This workflow uses the agent's existing computer-use tools and Chrome DevTools. It does not require a separate UI automation service. Keep the clients open and signed in between revisions so repeated checks do not include setup time.

## Current verification status

Apple Mail and Gmail web were verified on this Mac on November 24, 2026. Mail opened prepared `.eml` messages with the unique subject and raw `Message-ID`/source-hash headers matched to the run. Gmail returned HTTP 200 from `users.messages.insert`; the opened received-message DOM matched the API message ID and unique subject, all six images loaded, the ending was present and inspection was untruncated. Native screenshots covered the top and footer in both clients. Gmail token refresh also returned HTTP 200 using privately stored insertion-only authorization.

Outlook.com also opened the prepared `.eml` in its native reading popup. The exact subject and complete ending matched, all six images loaded, the hero background displayed, and DOM inspection was untruncated. The account uses a separate warm private-browser context; sign-in across browser restarts has not been tested.

## Saved-code-to-feedback benchmark

Measured November 24, 2026 with three visible revisions of the North Square email. Each pair used identical HTML bytes/hashes, the same 600px desktop email canvas and light mode. Exact stages, matched hashes, artifacts and failures are in ignored `.state/e2e-20261124T225722Z/comparison.json`.

The clock starts immediately before saving revised HTML and includes preparation/encoding, file selection/navigation, submission/upload, waiting/polling, retrieval and tool overhead. It ends when a fresh image or DOM is available on this Mac to inspect. Local web totals also include automated current-message/assets/evidence checks; EmailQA's column ends at full-PNG download, with later verification reported separately. Those downloaded images were subsequently confirmed valid.

| Mac client, light mode | Local artifact available, runs 1 / 2 / 3 | EmailQA full PNG downloaded, runs 1 / 2 / 3 |
| --- | --- | --- |
| Gmail web | Full message DOM: 3.557 / 2.453 / 2.385 s | 16.561 / 15.926 / 16.948 s |
| Outlook.com web | Full message DOM: 5.693 / 3.071 / 3.095 s | 29.840 / 31.815 / 28.984 s |
| Apple Mail | Full accessibility text + first image: 59.619 / 6.435 / 7.767 s | 49.451 / 49.196 / 59.957 s |

This measures an already configured edit loop: accounts, apps and browser connections were open/authorized; sign-in, OAuth refresh and startup are excluded. Local hosted assets were warm. EmailQA reported `cached: false` for all nine focused single-client jobs; underlying asset-cache state is unknown. Polling was once per second. Nine included credits were used (221 → 230 used, 2,770 remaining, no overage).

The artifacts differ. Local web returns full-message DOM, computed styles and geometry, with exact marker/ending, all six images loaded and clear truncation flags. Mail returns accessibility text plus an initial viewport image; it does not expose a browser CSS model. EmailQA returns a full-message PNG. EmailQA labels these targets Mac but hides exact app/OS/browser versions, so they are closest client-family matches rather than pixel-identical configurations. Local web used Chrome 157; Mail was 16.0 on macOS 27.2.1.

Local web viewport images arrived at 3.798 / 2.666 / 2.612 seconds for Gmail and 5.870 / 3.243 / 3.270 seconds for Outlook. Mail's full accessibility text arrived at 59.619 / 6.335 / 7.624 seconds; trial 3's overlapping image panels reached the ending at 9.560 seconds. The other Mail trials lack a successful timed full-message image set.

Preserve these failures:

- Mail trial 1 hit a native capture error at 2.174 seconds. Actual agent/tool recovery brought its first image at 59.619 seconds from the original start. This delay stays in the table and was slower than EmailQA's first image.
- Mail trial 2 returned valid first feedback, then supplemental full-message capture failed at 7.368 seconds. Its original `ok: false` remains preserved; that flag does not erase the earlier 6.435-second image. The current helper separates these outcomes.
- A narrow-window Mail preflight took 3.766 seconds but used the wrong desktop width. Its result is retained and excluded from comparison.

EmailQA's automated PNG decoding/marker/ending checks finished at 17.347 / 16.474 / 17.351 seconds for Gmail and 30.212 / 32.229 / 29.367 seconds for Outlook. Mail's three PNGs decoded correctly, but OCR missed their top-edge markers; the original failures remain. Actual manual verification completed at 108.282 / 78.785 / 92.485 seconds from each original start, including recovery delay. All nine original PNGs were visually checked for exact marker, six images, hero background and ending. An offline OCR fix later passed all nine originals and rejected a stale marker; it did not rerender jobs or replace these timing records.

Use this full clock to choose among clients that reproduce the bug. Earlier opening-only/submit-only records cannot rank saved-code-to-feedback speed. Three revisions from one email/session give a small reference, not a latency guarantee.

### Repeat the benchmark

Use shared marked source revisions and a private manifest. Discover current session/page IDs after connecting; do not reuse example IDs or assume private context names persist.

- [benchmark-web.py](benchmark-web.py): pass `--benchmark`, `--session-id`, `--client gmail-web|outlook-web`, and `--mail-page`. Gmail also requires a clean, preauthorized `--api-page`; the insertion token stays in browser memory. `--screenshot` times an extra viewport image. Failed attempts/cumulative recovery are retained; completed trials are skipped on rerun. Ambiguous insertions are not automatically retried.
- [benchmark-emailqa.py](benchmark-emailqa.py): pass `--benchmark`, an existing `--project`, `--clients` and a PNG `--verifier`. It uses the integration's private credential loader, checks included allowance, uploads each revision, polls per-client results and downloads them immediately. Image availability and later verification are separate endpoints.
- [benchmark-mail.cua.mjs](benchmark-mail.cua.mjs): call `benchmarkMailTrial({cua, fs, execFile, base, trial, outputDir})` in CUA's documented runtime. It includes preparation, Finder selection, Mail opening, accessibility retrieval and native capture. Match desktop content width first and keep first-image and supplemental full-message outcomes separate.

Checks passed: 43 Python and 11 Node. The previous 22 browser-fixture checks passed and were not rerun here. This comparison ran six local web trials, three matched-width Mail trials and nine EmailQA jobs. Helper/fixture checks are distinct from native verification.

For later runs, verify the actual client's current message, expected assets and ending. A generated `.eml`, successful API request or fixture inspection does not establish native-client success. DOM/accessibility evidence can establish the properties it actually exposes; use a screenshot when the user requests one or the defect requires visual proof.

## Inputs, state and evidence

Start with the complete current email HTML, including its `<head>`, styles and closing content. `preview.py prepare` freezes those bytes in an ignored run directory and builds `message.eml`. Each run has a unique subject, `Message-ID` and full source SHA-256 hash in `manifest.json` and the message headers. Identify the message by its full run path and unique subject; the basename `message.eml` alone is shared across runs. Use the same MIME content for comparisons across clients.

Prepare a run with the helper, then use the returned `runDir`, `subject` and `messageId` for the live client steps below:

```sh
python3 /Users/Henry/.codex/skills/html-email-best-practices/local-preview/preview.py prepare \
  --html /absolute/path/to/email.html
```

Preparation preserves a single UTF-8 HTML part. The helper reports local/relative assets and unresolved CID references; it does not construct attachment-bearing MIME or deliver/open the message. A CID-based email needs its actual multipart message before this workflow can verify it.

Use absolute HTTPS image URLs that the clients can reach without local cookies. Preserve CID attachments and their MIME relationships when the real email uses them. A local path, `localhost` URL or authenticated asset can work in a raw browser preview and fail in a mail client. Record remote-asset failures separately from layout defects. If an asset changes while its URL stays the same, source HTML hashing alone cannot prove freshness; record the asset revision or use an appropriate versioned URL.

Keep generated messages, temporary browser profiles, OAuth files and tokens in ignored `.state/` or another ignored runtime directory. Prefer the operating system Keychain for long-lived secrets. Never put tokens, passwords, cookies or verification codes in the guide, source control, screenshots or benchmark logs. The folder's `.gitignore` excludes `.state/`; confirm any alternative location is also excluded.

Store durable evidence in the email's `context/` directory, following the parent skill's image and freshness rules. For each capture, record:

- Source hash, run ID, `.eml` basename and exact subject.
- Client, browser or app version, OS version, viewport/window size, zoom and light/dark setting.
- Loading method: Gmail API insertion, Outlook web opened `.eml`, Apple Mail opened `.eml`, or actual delivery.
- Start time, message-visible time, required-assets-ready time and capture time. Label each timing boundary.
- DOM/accessibility evidence path, any screenshot paths and the checks performed, including whether the last content was inspected.

Keep mailbox addresses and unrelated account contents out of durable evidence when they are not needed to identify the test.

## Open the current message

### Fast path for each edit

Keep the selected client and its authorized browser/API session warm. Save the source edit and run `preview.py prepare --html /absolute/path/to/email.html --clients CLIENT`, replacing `CLIENT` with `gmail-web`, `outlook-web` or `apple-mail`. Preparation freezes the complete HTML and creates a fresh saved email file, `message.eml`, with a unique subject and message ID. Rebuild this file after every edit; reopening the previous run cannot verify new code.

Load only the client that reproduces the current defect:

- Gmail: run `gmail.py prepare --run-dir RUN`, insert the complete MIME with the existing insertion-only API grant, then open `https://mail.google.com/mail/u/0/#all/GMAIL_API_ID` in the intended mailbox. `GMAIL_API_ID` is the successful insert response's hex message ID. This direct route was used in the end-to-end benchmark; it avoids an inbox search and result click. Verify it with `inspectInsertedGmail` before accepting the DOM.
- Outlook.com: read the prepared `.eml` bytes, call `openOutlookEML` in the signed-in inbox and inspect the resulting native reading popup with `inspectOpenedOutlook`. This is the verified automated shortcut; use the native drop handler described below.
- Apple Mail: use Finder's Go to Folder field to select the exact run's `message.eml`, open it with Cmd+O, then rebind CUA to Mail's new message window. The benchmark includes Finder selection. Keep a desktop window wide enough for the 600px email canvas.

Inspect the current message, fix the source HTML and repeat that client route. Preserve the HTML hash, native identity, assets/ending checks and any before/after evidence. Reuse the existing authorization and installed helpers. Request additional screenshots only when they help inspect the defect or the user asks for them.

These routes preserve the prepared HTML and exercise the actual client reading view. The tests established that the current revision, required images and ending rendered; they did not compare the shortcuts against production delivery. Gmail insertion bypasses most delivery scanning, and opening `.eml` bypasses transport. For behavior involving sender transformations, delivered headers, filtering or delivery processing, compare with a message produced by the actual sending path before relying on the shortcut.

### Gmail web

Use a dedicated Google test mailbox when one is available, with a persistent isolated browser profile. A Google mailbox is part of the target configuration; Gmail with a non-Google IMAP account is a different target.

Authorize a desktop OAuth client for the test mailbox and request `https://www.googleapis.com/auth/gmail.insert` for inserting test messages. Google's current Personal app mode is limited to the account that created the app, so create that app under the intended test account. Existing Internal/External projects cannot be converted to Personal. Workspace administrator restrictions can still apply. Reuse an existing authorized setup when it meets the task rather than creating another project. See [Google's app audience rules](https://support.google.com/cloud/answer/15549945).

Follow [AUTH.md](AUTH.md) for the tested OAuth, private token storage, refresh and insertion steps. Personal-mode onboarding starts at [Google Auth Platform's Personal setup](https://console.cloud.google.com/auth/overview/personal); the ordinary Get Started route displayed only External/Internal during this setup.

Insert the complete MIME message with [`users.messages.insert`](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages/insert), then find and open its unique subject in Gmail's reading view. This API adds the message only to the authorized mailbox and does not send it. It bypasses most delivery scanning. [`messages.import`](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages/import) applies more delivery scanning but still omits SPF checks; neither method exercises the sending provider's transformations.

Confirm the visible subject and current revision before inspection. Wait for the message body, then inspect its actual Gmail DOM. A compose window, draft or local HTML tab does not verify the received-message view. If the message is clipped, inspect the complete-message view and record that fact.

Load [browser-inspect.js](browser-inspect.js), then [gmail-inspect.js](gmail-inspect.js), into the actual Gmail page through DevTools. Call `inspectInsertedGmail` with `gmailMessageId` from the successful insert response, `expectedSubject` and `sourceSHA256` from the run, and `expectedEnding` set to distinctive final text from this email. The source hash remains supplied provenance. The observer waits for the visible subject and `.adn.ads[data-legacy-message-id] .a3s.aiL` body belonging to that exact Gmail API ID, then checks assets and geometry through the generic inspector and confirms the message did not change during inspection. These selectors were observed in the live Gmail received-message DOM; inspect them again if Gmail changes.

Save the returned JSON as `--inspection` evidence only after checking `ok`, `nativeIdentity`, `readiness.ready` and the truncation flags. This observer avoids accepting the previous message body while Gmail navigation catches up. It does not send mail or change message HTML. Take screenshots when needed for the defect or requested by the user.

### Outlook web

The tested automated opener accepts only a signed-in Outlook.com inbox at `https://outlook.live.com`; Microsoft 365 web mail remains a separate, untested target. A Microsoft account whose username is a Gmail address may first need an Outlook.com alias before it can open an inbox. A separate existing Microsoft account with a new Outlook.com alias worked here; recovery of another account is not a prerequisite. The live test used a private browser context that stays warm while its windows remain open. Prefer a persistent dedicated profile for reuse when its normal sign-in works; the current setup does not establish persistence across browser restarts.

Microsoft [documents opening `.eml` by dropping it onto Outlook web's reading pane](https://support.microsoft.com/en-us/outlook/mail/open-eml-msg-and-oft-files-in-new-outlook-and-outlook-on-the-web). The tested shortcut uses [outlook-preview.js](outlook-preview.js) through Chrome DevTools to pass the exact file bytes to Outlook's native drop handler. Outlook parses the MIME and opens its own reading popup; the helper does not replace the message DOM or send an email. Native Finder-to-browser dragging was blocked by this computer-use tool's cross-window error, so it is not the verified automated route.

Load `outlook-preview.js` in the signed-in inbox and call `openOutlookEML` with `mimeBase64` containing the complete prepared `message.eml`, plus `expectedSubject`, `sourceSHA256`, `expectedMessageId` and `expectedRunId` from its manifest. The opener checks the MIME headers and decoded HTML hash, then dispatches the file to the descendant at the reading pane's center. Keep request files private. Its success means the file was dispatched; it does not mean Outlook finished rendering.

Find the newly opened native popup by the exact unique subject. Load `browser-inspect.js` and `outlook-preview.js` there, then call `inspectOpenedOutlook({expectedSubject, sourceSHA256, expectedEnding, timeoutMs: 15000})`. It waits for the matching popup title and native subject, a unique visible message body and ending, inspects assets and geometry, and rechecks identity afterward. The observed body selector is `div[id^="UniqueMessageBody_"][aria-label="Message body"]`. Save the returned JSON and accept only `ok`, `readiness.ready`, the expected image set and clear truncation flags. The rendered DOM's source hash is supplied provenance linked to the verified MIME, not a hash recovered from Outlook.

If Outlook changes these selectors or ignores the drop, inspect its current UI and record the failure. Do not substitute a draft or inject source HTML into the client. A Microsoft 365 mailbox is a separate configuration and has not been tested by this Outlook.com check.

Confirm that Outlook opened the expected subject and complete message in a reading view. Dropping the file into a compose window attaches it and does not run this test. Record this as an **opened `.eml`** test, because it has not passed through inbox delivery. Compare this shortcut with a delivered message before relying on it for a defect that may depend on server processing.

Microsoft Graph's [create-message API](https://learn.microsoft.com/en-us/graph/api/user-post-messages?view=graph-rest-1.0) creates a draft, including when supplied MIME. Moving or opening such a draft is not a supported substitute for this received-view check.

### Apple Mail for Mac

Open the current `.eml` with Mail, using Finder's Open With action or the normal application file-open route. This Mac's installed Mail app declares `.eml` as a supported viewer format. Verify the actual message window and its subject after opening; an account setup window or an old message window is not a render.

After opening each new message, rebind with `cua.getApp('com.apple.mail')` before reading or capturing it. An existing CUA app handle can remain bound to the previous message window.

Do not assume account setup is required merely to view the file. First inspect whether Mail can open it in the current configuration. If the first-run account screen prevents that, record the exact blocker and use an authorized test account through Mail's normal account interface. Apple [documents account setup](https://support.apple.com/guide/mac-help/mh35565/mac), but does not guarantee an account-free first-run `.eml` workflow in that guide.

Inspect with computer use: accessibility text, controls and available element geometry. Scroll to inspect the ending and take a native screenshot when visual proof is needed or requested. An accessibility tree does not contain the full CSS/layout model. Do not promise Chrome DevTools access to Mail's message body or alter the app to expose it: WebKit's [inspection API requires application opt-in](https://webkit.org/blog/13936/enabling-the-inspection-of-web-content-in-apps/).

Record Mail's remote-content state. [Mail Privacy Protection can fetch remote content in the background, while blocking remote content can leave images unloaded](https://support.apple.com/guide/mail/change-privacy-settings-mlhlae4a4fe6/mac). Use the current message's normal load-content control when needed for an image-loaded test and record the result. Avoid changing a personal account's global privacy preferences just to hide a test failure.

## Inspect and capture

### Debug spacing with the client DOM

Use the live Gmail/Outlook message DOM to locate the element responsible for a gap. First run the client-specific identity/readiness inspector so the subject, native message and ending belong to the current revision. Load `browser-inspect.js` in that page and inspect the narrow message-body root returned by the client inspector. It exposes sanitized HTML, computed padding/margins, dimensions, line height, table attributes, bounding rectangles and text-line rectangles. Use its `querySelector` option for an observed selector when a smaller part of the message is sufficient; include the relevant ancestors in the inspection.

1. Locate the visible text/image next to the unwanted space and inspect its box and the boxes of enclosing `<td>`, `<tr>` and `<table>` elements, stopping at the message root. Measure the actual gap and compare the same elements before/after the edit.
2. Read computed padding and margins on the target and ancestors. Check line height, borders, `height`/`min-height`, vertical alignment, HTML `cellpadding`/`cellspacing`/`height` attributes, spacer rows, empty cells and `<br>` elements. Use a targeted read-only DevTools query for properties the inspector omits, such as `border-spacing` or `border-collapse`.
3. Identify the owning element and the source rule/attribute that causes the space. For example, if the text paragraph has `padding-top: 0` and `margin-top: 0` but the parent `<td>` has `padding-top: 24px`, change that cell's source padding. A client wrapper outside the message root needs a different diagnosis from padding authored in the email.
4. Edit the source, prepare/load a new revision and inspect the same boxes in the same client configuration. Verify the measured gap changed and nearby alignment still works. Do not replace the client message DOM or inject a style override as proof of the source fix.

This DOM workflow applies to Gmail and Outlook web. Apple Mail's accessibility tree exposes text, controls and some geometry, but it does not supply the computed CSS model needed for this procedure. Use native images/accessibility there, and retain a screenshot when the defect requires visual evidence.

### Capture and record evidence

Use CUA for native Mail and file dragging. Read its current tool documentation before acting. For web clients, use the Chrome DevTools MCP tools or the installed `chrome-devtools-cli` skill for authenticated JavaScript, DOM, styles and network inspection. Pass the current task's `--sessionId` explicitly on CLI calls; this installed CLI ignores `CHROME_DEVTOOLS_MCP_SESSION_ID`. Use a dedicated test profile where possible. Attaching a new debugger to Henry's personal Chrome profile requires the approval described in the project instructions; an existing authorized session does not authorize another debugger attachment. See [AUTH.md](AUTH.md) for connection ownership and cleanup.

The CLI's normal sequence is `list_pages`, `take_snapshot`, then an action or `evaluate_script` against the observed page ID. IDs and selectors are session-specific. Discover the current message body from the live snapshot/DOM, and inspect that subtree or its frame. Do not take the entire application's navigation DOM as the email body. Do not replace the client body with source HTML or inject style changes while collecting verification evidence.

For a useful web inspection, collect the relevant client-rendered DOM, computed styles and bounding rectangles. Check image completion and natural dimensions, visible copy and the last expected content. Scope collection to the test message; avoid exporting unrelated inbox contents or authentication state. Take a screenshot of the message or defect region when visual proof is needed. A raw DOM dump does not prove colors, clipping or compositing look correct.

Web clients commonly scroll their reading pane independently of the page. A browser `fullPage` screenshot can capture the application shell while omitting the lower message. Inspect the actual scroll container and verify the ending; use several labeled viewport captures if necessary. For Apple Mail, inspect the first viewport and scroll to the ending, or to the defect region during a focused iteration. Call evidence complete only for the coverage actually inspected.

Before accepting a result, check that the message's full run path/subject matches the current run, the source hash matches the current HTML, required images have loaded or their failure is recorded, and the expected final content is present. Preserve current evidence from the actual client. Fixture generation, MIME validation and asset reachability checks are useful preparation, but must keep their own labels.

`browser-inspect.js` exposes `inspectEmailDOM` for an observed, unique message-body selector. Load it with the DevTools CLI's `evaluate_script --sourcePath` facility, then call it in that same page/frame with `rootSelector`, the run's `sourceSHA256` and a client label. Its hash field records supplied provenance; it does not recover or verify message headers. Its readiness result checks `<img>` completion, the document font-set status and two stable geometry frames. Check CSS background assets and expected fonts separately when they matter, and honor its truncation flags.

Record a client's component-stage start immediately before opening/inserting that revision. This helper clock starts after preparation; use the benchmark's earlier clock for saved-code-to-feedback comparisons:

```sh
python3 /Users/Henry/.codex/skills/html-email-best-practices/local-preview/preview.py record \
  --run-dir /absolute/path/to/run --client apple-mail --status started
```

After inspecting the actual client, use `record --status ready` with fresh UTF-8 DOM or accessibility evidence via `--inspection`, plus `--observed-message-id` and `--observed-source-hash`. A `--screenshot` is optional; repeated `--evidence` paths add supporting files. Establish the observed identity by inspecting available message headers or linking the visible unique subject to the exact prepared message/API insertion result. These arguments attest to that live check; copying manifest values does not perform it. Do not copy an older inspection to give it a newer file timestamp.

The helper records `inspectionElapsedSeconds` and `captureElapsedSeconds` separately. `elapsedSeconds` ends at the earliest available evidence, so identify whether a reported time covers inspection or screenshot capture. These are workflow timings, not a measurement of the client's internal paint time. Use `record --status error --error` for a blocked or failed client.

`validate --run-dir` checks source freshness and recorded evidence integrity and accepts DOM/accessibility evidence without an image. Image `export --run-dir --destination` additionally requires an actual screenshot for every selected client. These commands do not establish that the inspected properties prove the fix, inspect screenshot content or independently identify the native application.

## Use the shortest useful feedback loop

Choose the fastest current client configuration that visibly reproduces the reported defect. A faster client that does not show it provides no fix evidence. Keep app, account type, viewport and theme stable between before/after captures. If the user's target differs, verify that target after the focused fix, then run the parent skill's required final client matrix.

Measure warm runs separately from account setup, app launch and browser startup. Start immediately before saving revised HTML and stop when the fresh image or DOM has returned for inspection; include preparation, submission, waiting and retrieval. Record any later verification or supplemental capture separately. Keep failures, timeouts and cumulative recovery in the timing record. Three trials establish a small local reference, not a guaranteed upper bound.

Local insertion and `.eml` opening shorten the loop by bypassing transport. Before final delivery, test the production sending provider's actual output and use the vendor matrix for clients this Mac does not cover, including Windows and mobile apps. A Gmail web or Apple Mail result cannot establish Gmail iPhone dark-mode behavior.
