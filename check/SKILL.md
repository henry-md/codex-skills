---
name: check
description: Capture and inspect a page from a reusable signed-in browser session, then take a real screenshot. Default to an anonymous per-thread local account so `/check` runs do not interfere with each other. Only use Henry Deutsch's real account when the user explicitly asks for Henry-specific data or asks to inspect `henrymdeutsch@gmail.com`.
---

# Check

Use this skill to see a page from a signed-in perspective instead of from an anonymous browser session.
Default to an anonymous per-thread local account. Only connect to Henry's real account when the user explicitly asks for Henry-specific verification.
Here, "anonymous" means a signed-in local `/check` user that is isolated from Henry's real account and from other Codex threads.

## Workflow

1. Read repo-local check docs first when they exist.
   Prefer repo docs such as `agent-docs/coding-conventions.md` and any architecture notes that describe how the product should support visual verification.
   Keep runtime config, notes, screenshots, and saved auth state under this skill's per-repo folder at `repos/<repo-key>/`.
   If the repo is not configured yet, run the global setup script first so the per-repo folder is created automatically before continuing.
   Treat repo-local data-safety instructions as hard guardrails. Do not delete existing user data, saved tailoring jobs, or other persisted records just to reset a test environment unless the repo docs explicitly allow it for the exact artifacts you created during the current verification run.

2. Choose the account mode before opening the browser.
   Default to the repo's anonymous local `/check` account when the user asks for ordinary verification, CRUD-heavy repros, or anything that does not specifically require Henry's real data.
   Only target Henry's real account when the user explicitly asks for Henry's account, Henry-specific data, or the signed-in state for `henrymdeutsch@gmail.com`.
   When a repo supports anonymous per-thread accounts, prefer that mode so separate Codex tabs do not share cookies or app data.

3. Prefer an existing auth state for the chosen account before asking for a fresh login.
   The default state file should live in this skill's per-repo folder.
   For anonymous accounts, prefer a thread- or session-specific state file over one shared auth file.
   Verify the saved session before trusting it.

4. Refresh the chosen account's auth state without using Google login automation when possible.
   Prefer the global `scripts/ensure-auth-state.sh` flow plus repo config.
   When the app uses database-backed NextAuth with Prisma, prefer the global `scripts/seed-nextauth-prisma-state.mjs` helper.
   When the repo supports anonymous local users, prefer auto-creating or reseeding that local user over driving a third-party Google sign-in flow.
   Only fall back to interactive sign-in if the app truly requires it, such as when the real Henry account must be used and no local session-seeding path can produce it.

5. Resolve the target page from the user's request.
   If the user invokes `/check /some-path`, treat that path as the page route or URL to open, not as a filesystem path.
   If the user invokes `/check` without a path, infer the route and any in-app navigation from the current task context, prioritizing the feature or surface you were just changing.
   If several views are plausible, choose the one that best matches the current work and say which one you checked.

6. Prefer the existing headless harness when the repo already has one.
   Headless browser automation is the default, not the fallback.
   For extension repos or other browser-heavy products that already have a persistent Playwright or Chromium harness, use that headless path first instead of reaching for a headed browser by habit.
   For unpacked Chrome extension verification, prefer bundled Chromium over Google Chrome because Chromium reliably honors extension-loading flags while Google Chrome may ignore them.
   If a high-level Playwright flow cannot reach MV3 service workers, `chrome-extension://` pages, or other extension internals cleanly, drop to Chromium plus the Chrome DevTools Protocol while staying headless.
   Treat a headed browser as an escalation path only for real browser-chrome issues such as docked side-panel shell behavior, focus quirks, or window integration that headless Chromium plus Playwright/CDP cannot faithfully inspect.
   If you choose headed instead of an available headless path, say what specifically blocked headless verification.

7. Capture the target page with the saved auth state.
   Reuse the global `scripts/check-page.sh` helper to take a screenshot of the requested route or URL.
   Before doing slow browser-only setup such as repeated uploads, form typing, or modal-clicking, look for repo-local `/check` helpers that can safely pre-create deterministic test state for the anonymous account.
   Prefer doing reversible setup through repo-local helpers, direct storage writes, or first-party app APIs when that lets the browser focus on the actual proof points the user asked for.
   If the page requires extra navigation after load, extend the skill or add the smallest repo-side product change needed so the skill can perform that flow autonomously next time.
   Save screenshots under the per-repo folder inside this skill so the workflow stays centralized.
   When responding to the user, prefer rendering the screenshot inline with Markdown image syntax using the absolute file path so the Codex desktop app shows a preview instead of just a file card.
   For extension verification, prefer the extension's own page target such as `chrome-extension://<extension-id>/index.html` or `options.html` when the real browser shell is not directly targetable, and treat that surrogate as the default UI surface unless the bug is specifically about the shell itself.
   When extension pages are hard to reach through a high-level library, use CDP target discovery/attachment rather than abandoning headless verification too early.
   When the user asks for an "in-flight" screenshot, capture the first clearly visible running-state artifact that appears reliably, such as a toast, spinner, status pill, or progress step, instead of waiting for a richer client-only surface that may render later or inconsistently in headless mode.

8. Call out when the product surface is not directly addressable.
   If a feature lives behind client-only tabs, modal state, or other non-addressable UI state, say that a small refactor such as a deep-linkable query param or route would make `/check` much more useful.
   Ask the user explicitly whether you should make that refactor before touching the product code.

9. Open the saved screenshot in Codex and inspect it directly.
   Do not treat command success or HTML output as visual verification.
   Call out whether the requested data or UI is actually visible from the chosen account's perspective.
   DOM assertions, locator checks, and other direct page inspection can support the diagnosis, but a screenshot is still the completion artifact for `/check`.

10. Patch the skill and repo-local helpers when the workflow breaks.
   If a missing step, flaky command, or auth edge case shows up during real use, update this skill first and keep repo-local additions minimal before trying again.
   If a `/check` run spends most of its time manually reaching the state to verify instead of proving the state itself, add or improve a repo-local prep helper so the next run can jump straight to the visual assertion.

## Repo Pattern

When the current repo needs persistent support files for this skill:

- Create or reuse `repos/<repo-key>/` inside this skill.
- Keep new runtime artifacts under `repos/<repo-key>/` so the root `~/.codex/skills/.gitignore` continues to exclude them from git by default.
- Keep repo-specific runtime config in `repos/<repo-key>/config.env`.
- Keep per-repo notes in `repos/<repo-key>/workflow.md` when needed.
- Keep generated screenshots and saved auth state there too.
- If this skill ever needs a new persistent runtime path outside `repos/<repo-key>/`, update the root `~/.codex/skills/.gitignore` before writing those files.
- Do not create `agent-docs/check` or any other repo-local `/check` runtime folder unless the user explicitly asks for a repo-local exception.

## Constraints

- Henry's canonical signed-in email is `henrymdeutsch@gmail.com`.
- Default to an anonymous local `/check` account when the user does not explicitly ask for Henry's account.
- Do not connect to Henry's real account unless the user explicitly asks for Henry-specific data, Henry's account, or the signed-in state for `henrymdeutsch@gmail.com`.
- When a repo supports thread-local anonymous accounts, treat that as the normal `/check` mode.
- Prefer `http://127.0.0.1:3000` for local auth capture unless repo-local docs say otherwise.
- Treat saved storage state as a secret.
- Only delete artifacts that the current `/check` run created itself. If a clean-slate repro appears to require deleting older user-visible data, pause and ask the user what to do instead of wiping that data automatically.
- When using Henry's real account, never delete, clear, archive, overwrite, or otherwise mutate Henry-owned user-visible data unless Henry explicitly gives permission for that exact destructive action.
- When using Henry's real account, be conservative even with "cleanup" operations. Prefer preserving stale objects over deleting the wrong thing.
- When using an anonymous `/check` account, it is acceptable to create, update, and delete artifacts freely as needed for the repro unless repo-local docs say otherwise.
- Do not claim Henry-authenticated verification unless Henry's session verification passed and you visually inspected the screenshot.
- When `/check` is invoked without a path, do not stop just because the user omitted it; infer the most relevant page from context and proceed.
- Prefer local session seeding over third-party auth automation when the app uses database-backed sessions.
- When a repo already has a working headless browser harness, use it first and only escalate to headed with an explicit reason.
- Prefer bundled Chromium over Google Chrome for unpacked extension automation.
- Prefer staying headless even when you need to drop below Playwright and use CDP directly.
- Prefer moving reusable shell, Python, and Node automation into this global skill instead of duplicating it inside individual repos.
- Never refactor the product code to make tabs or views deep-linkable without the user's explicit sign-off.
- If the user needs a logged-in screenshot and the session is stale, keep iterating until the login capture flow works or you hit a real blocker that requires Henry to act.

## Final Response

Report:

- which account mode you used: anonymous `/check` account or Henry's real account
- whether that session was reused or refreshed
- which route or URL you checked, and whether it was inferred from context
- the screenshot path
- an inline screenshot preview using Markdown image syntax with the absolute file path, unless the user asks for text-only output
- whether the requested account-specific data was visible
- any remaining auth or page-load uncertainty
