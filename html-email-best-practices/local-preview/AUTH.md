# Gmail authorization and insertion

Use this runbook with [GUIDE.md](GUIDE.md). The Python helpers prepare files and receive a localhost callback. Run Google API requests through the configured Chrome DevTools tools on a clean API page. Prefer a dedicated browser profile when sign-in works there. Account setup, consent and native Gmail inspection still use the agent's browser tools.

On November 24, 2026, Google blocked sign-in in the isolated automated profile and that attempt was stopped. Henry explicitly authorized a temporary DevTools connection to his already signed-in personal Chrome profile for these tests. The working route used that existing connection through `--autoConnect`, without copying credentials or session cookies. Reuse the authorized connection within that scope; a new personal-profile debugger attachment remains subject to the project instructions.

Pass `--sessionId` explicitly on every DevTools CLI call. This installed CLI ignores the `CHROME_DEVTOOLS_MCP_SESSION_ID` environment variable; relying on it can address a different daemon. In the examples below, set the shell variable `preview_session_id` to the current task-owned connection's ID. Discover it from that connection's setup, and never copy a past task's ID into this guide. Keep the same browser and clean API page alive between revision checks.

Reuse a suitable Google Cloud project and desktop OAuth client for the intended test mailbox. The Gmail API and the app's audience/consent setup must be ready before authorization. Complete required account or terms decisions within the user's authorization. A prepared OAuth URL does not establish that setup succeeded.

For a new Personal-mode app, start at [Personal setup](https://console.cloud.google.com/auth/overview/personal). The ordinary Get Started route displayed only External/Internal during the verified setup. Personal mode can authorize only its creator's Google Account, and a Workspace administrator can still restrict access. See [Google's audience rules](https://support.google.com/cloud/answer/15549945). The verified authorization requested only `gmail.insert`; insertion and token refresh both returned HTTP 200, and the opened native Gmail message was checked against the insertion result. This first setup did not measure render latency.

Use one Google Cloud project named `Local Email Preview`, with the same app name in Google Auth Platform → Branding. Reuse its existing Personal-mode project, desktop client and saved `gmail.insert` authorization. Start Personal onboarding directly; do not create a standard project first. If Google uses `personal-mode-app`, rename the project in Project settings and the app in Branding while preserving the client, grant and scope. Outlook uses Microsoft sign-in and needs no second Google project. The unused initial standard project was shut down on November 24, 2026 and remains restorable for 30 days.

Keep private files under the ignored `.state/` directory. Helper outputs contain paths and safe status fields; private authorization URLs, callbacks and token files must not be printed, copied into chat or included in screenshots. Use the password manager and existing sessions through their normal interfaces. Do not ask the user to copy an authorization code.

## Receive the callback

Start the listener in a long-running execution session. It binds only `127.0.0.1`, chooses an available port and waits up to 15 minutes. The optional `--runtime-dir` must be a new directory. Without it, the helper creates a unique directory automatically.

```sh
python3 /Users/Henry/.codex/skills/html-email-best-practices/local-preview/oauth.py listen \
  --state-dir /Users/Henry/.codex/skills/html-email-best-practices/local-preview/.state/oauth \
  --timeout 900
```

Its first stdout JSON safely supplies `redirectUri`, `sessionFile`, `callbackFile` and `readyFile`. Keep that execution session alive while completing authorization. The same information is saved in private `ready.json`. Shorter positive timeouts, a fixed `--port` and a different `--path` are supported. The default port is `0`, meaning the operating system chooses it.

Import the downloaded **desktop** OAuth client JSON. Pass its file path, never its contents:

```sh
python3 /Users/Henry/.codex/skills/html-email-best-practices/local-preview/oauth.py import-client \
  --state-dir /Users/Henry/.codex/skills/html-email-best-practices/local-preview/.state/oauth \
  --download /absolute/path/to/downloaded-desktop-client.json
```

The importer accepts Google's current or legacy downloaded authorization URI and normalizes it to `https://accounts.google.com/o/oauth2/v2/auth`. Keep the downloaded client intact; do not edit credentials into prose or command arguments.

Create the PKCE session using the listener's exact `redirectUri` and `sessionFile`. The redirect URI contains no code or token. Replace the example port and session path with the safe listener output:

```sh
python3 /Users/Henry/.codex/skills/html-email-best-practices/local-preview/oauth.py authorize \
  --state-dir /Users/Henry/.codex/skills/html-email-best-practices/local-preview/.state/oauth \
  --redirect-uri http://127.0.0.1:12345/oauth/callback \
  --session-file /absolute/path/from/listener/session.json
```

The default scope is `https://www.googleapis.com/auth/gmail.insert`. If the task needs API read-back verification, request both insertion and read-only explicitly with two `--scope` arguments. The helper refuses other scopes. Its output names `authorizationUrlFile`; the URL stays inside that private file.

## Open the private authorization URL

Use the installed [Chrome DevTools CLI skill](/Users/Henry/.codex/skills/chrome-devtools-cli/SKILL.md). Discover page IDs with `chrome-devtools list_pages --sessionId "$preview_session_id"`. Reuse the existing authorized connection. In the verified setup this was the temporary personal-profile `--autoConnect` connection described above; attaching a new debugger to a personal profile requires the approval described in the project instructions.

To navigate without exposing the private URL in a command or tool result, open a blank authorization page, create a file input, upload `authorizationUrlFile`, then navigate from its contents. Replace the example page ID and input UID with observed values:

```sh
: "${preview_session_id:?Set the current task DevTools session ID}"
chrome-devtools new_page about:blank --sessionId "$preview_session_id"
chrome-devtools evaluate_script --sessionId "$preview_session_id" '() => {
  const input = document.createElement("input");
  input.type = "file";
  input.dataset.localPreviewAuthorization = "url";
  document.body.appendChild(input);
  return {ready: true};
}' --pageId 1
chrome-devtools take_snapshot 1 --sessionId "$preview_session_id"
chrome-devtools upload_file 1 INPUT_UID /absolute/path/to/authorization-url.txt --sessionId "$preview_session_id"
python3 - "$preview_session_id" <<'PY'
import json
import subprocess
import sys

script = '''async () => {
  const input = document.querySelector("input[data-local-preview-authorization=url]");
  const url = new URL((await input.files[0].text()).trim());
  if (url.origin !== "https://accounts.google.com" || url.pathname !== "/o/oauth2/v2/auth") {
    throw new Error("Unexpected authorization destination.");
  }
  location.assign(url.href);
  return {navigationStarted: true};
}'''
result = subprocess.run(["chrome-devtools", "evaluate_script", script, "--pageId", "1",
                         "--waitForStableDom", "false", "--sessionId", sys.argv[1]],
                        capture_output=True, text=True)
print(json.dumps({"navigationCommandSucceeded": result.returncode == 0}))
raise SystemExit(result.returncode)
PY
```

The wrapper discards the CLI's full stdout/stderr and returns a safe status. DevTools navigation metadata can contain the full destination URL even when `--waitForStableDom false` or `--filePath` is set. Keep the final consent click's output private too, because it can redirect to a URL containing the code. For an observed consent-button UID, use this pattern:

```sh
python3 - "$preview_session_id" <<'PY'
import json
import subprocess
import sys

result = subprocess.run(["chrome-devtools", "click", "1", "CONSENT_BUTTON_UID",
                         "--sessionId", sys.argv[1]],
                        capture_output=True, text=True)
print(json.dumps({"consentActionSucceeded": result.returncode == 0}))
raise SystemExit(result.returncode)
PY
```

Complete sign-in and consent through the browser's normal UI, keeping navigation output private. The listener validates the exact callback path, redirect URI, state and session expiry. Invalid or unrelated requests do not stop it. A matching code callback is saved atomically in `callbackFile`, mode `0600`, and the listener stops. A matching provider error is saved with final `status: "declined"`; process exit `0` alone does not mean authorization succeeded. Timeout exits with an error and closes the port. The listener's normal output contains no code or state.

Read only the safe final `ready.json` status. Avoid snapshots, URL dumps or network-body inspection of the callback page, whose URL contains the code. Navigate that page away once the listener has captured the response.

## Exchange the code through DevTools

Prepare the token request from the private session and callback files:

```sh
python3 /Users/Henry/.codex/skills/html-email-best-practices/local-preview/oauth.py exchange-payload \
  --state-dir /Users/Henry/.codex/skills/html-email-best-practices/local-preview/.state/oauth \
  --session /absolute/path/from/listener/session.json \
  --callback-file /absolute/path/from/listener/callback.txt
```

The result names `payloadFile`, `setupScript` and `requestScript`. The payload contains the code and PKCE verifier. The scripts contain no credentials. Use a clean, dedicated API page rather than executing token-handling scripts in a mailbox application:

```sh
chrome-devtools new_page https://gmail.googleapis.com/ --sessionId "$preview_session_id"
chrome-devtools evaluate_script --pageId 2 --sessionId "$preview_session_id" \
  --sourcePath /absolute/path/to/exchange/setup-file-input.js --format function
chrome-devtools take_snapshot 2 --sessionId "$preview_session_id"
chrome-devtools upload_file 2 INPUT_UID /absolute/path/to/exchange/token-request.json --sessionId "$preview_session_id"
chrome-devtools evaluate_script --pageId 2 --sessionId "$preview_session_id" \
  --sourcePath /absolute/path/to/exchange/execute-token-request.js --format function
```

Replace page `2` and `INPUT_UID` with observed values. Use the generated paths from `exchange-payload`. A successful execution returns only `ok`, `httpStatus`, `expiresIn`, `hasRefreshToken` and `tokenType`. Tokens remain in the page's non-enumerable `globalThis.__localPreviewGoogleTokens` value. Respect browser security/CORS denials; record the concrete error rather than switching transports to evade it.

Persist that response with the CLI's **file-only output** option. Never run this expression without `--filePath`; that would print tokens. The installed CLI writes the output file with owner-only permissions and returns its path:

```sh
chrome-devtools evaluate_script --sessionId "$preview_session_id" '() => {
  const value = globalThis.__localPreviewGoogleTokens;
  if (!value?.access_token) throw new Error("No successful token response is available.");
  return value;
}' --pageId 2 \
  --filePath /Users/Henry/.codex/skills/html-email-best-practices/local-preview/.state/oauth/token-response.json \
  --waitForStableDom false
python3 /Users/Henry/.codex/skills/html-email-best-practices/local-preview/oauth.py store-tokens \
  --state-dir /Users/Henry/.codex/skills/html-email-best-practices/local-preview/.state/oauth \
  --response-file /Users/Henry/.codex/skills/html-email-best-practices/local-preview/.state/oauth/token-response.json
```

`store-tokens` validates the response and saves private `tokens.json`, including its expiry. It preserves an existing refresh token if Google omits a replacement. Keep the clean API page alive for insertion, or load a new access token by the refresh flow below. Do not inspect token request/response bodies or export browser state.

## Refresh access

Generate a refresh request from the saved private client and tokens:

```sh
python3 /Users/Henry/.codex/skills/html-email-best-practices/local-preview/oauth.py refresh-payload \
  --state-dir /Users/Henry/.codex/skills/html-email-best-practices/local-preview/.state/oauth
```

Run the returned `setupScript`, upload the returned `payloadFile` to its observed input UID, then run `requestScript` on the clean API page. Use the same three DevTools commands as the exchange step, substituting the refresh artifact paths. Save the browser-memory response with the same `--filePath` command and run `store-tokens` again. The request helper fails clearly if no refresh token was saved; complete a new authorized consent flow in that case.

## Insert the prepared message

Prepare a current preview run with `preview.py prepare`, then build its verified Gmail payload:

```sh
python3 /Users/Henry/.codex/skills/html-email-best-practices/local-preview/gmail.py prepare \
  --run-dir /absolute/path/to/current/run
```

The result names `payloadFile`, `setupScript`, `requestScript` and `metadataFile`. The helper checks the current HTML, frozen HTML, complete MIME hash, headers and exact decoded HTML before generating the request. It defaults to `INBOX` and `UNREAD` labels.

Immediately before insertion, start the client clock:

```sh
python3 /Users/Henry/.codex/skills/html-email-best-practices/local-preview/preview.py record \
  --run-dir /absolute/path/to/current/run --client gmail-web --status started
chrome-devtools evaluate_script --pageId 2 --sessionId "$preview_session_id" \
  --sourcePath /absolute/path/to/current/run/gmail/setup-file-input.js --format function
chrome-devtools take_snapshot 2 --sessionId "$preview_session_id"
chrome-devtools upload_file 2 INPUT_UID /absolute/path/to/current/run/gmail/insert-payload.json --sessionId "$preview_session_id"
chrome-devtools evaluate_script --pageId 2 --sessionId "$preview_session_id" \
  --sourcePath /absolute/path/to/current/run/gmail/execute-insert.js --format function
```

The insert script reads the access token from browser memory. Its safe response contains `ok`, `httpStatus` and, on success, Gmail `messageId`, `threadId` and `labelIds`. These Gmail IDs differ from the RFC `Message-ID` in the MIME headers. An HTTP success establishes insertion only; it does not establish a visible render. Do not automatically retry an ambiguous insertion, because a second POST can create another mailbox item.

Open the `gmailSearchUrl` in private `metadataFile`, using the intended test account's mailbox. Load [browser-inspect.js](browser-inspect.js), followed by [gmail-inspect.js](gmail-inspect.js), in that actual Gmail page. Call `inspectInsertedGmail` with the insert response's Gmail `messageId` as `gmailMessageId`, `manifest.message.subject` as `expectedSubject`, `manifest.source.sha256` as `sourceSHA256`, and a distinctive `expectedEnding` from the current email. The observer waits for the visible subject and exact native `data-legacy-message-id`, inspects only that received-message body and checks that navigation did not replace it mid-inspection. This Gmail API ID is separate from the MIME header ID used by `preview.py record --observed-message-id`.

Check `ok`, `nativeIdentity`, `readiness.ready`, image state and truncation before saving the JSON as current DOM inspection evidence. Record the result and any optional screenshots as described in [GUIDE.md](GUIDE.md). The supplied source hash and record identity arguments attest to the prepared-message link; they do not independently extract a hash from Gmail's transformed DOM. Insertion adds the message to the authorized mailbox and does not send it.

After use, remove temporary token-response/request/callback files when no longer needed, clear the private API page's in-memory tokens and uploaded file inputs, and close task-owned pages. Preserve only the private client/session/token state needed for the authorized workflow. Detach only the task-owned DevTools connection, addressing it with its explicit `--sessionId`; never stop another task's daemon or quit the user's browser. Preserve Chrome's prior remote-debugging setting. `--autoConnect` can attach when that setting is already enabled and does not require toggling it for each run.
