---
name: check
description: Capture and inspect a page from Henry Deutsch's logged-in browser perspective by refreshing or reusing Playwright auth state, then taking a real screenshot. Use when Codex needs to verify a protected route, inspect Henry-specific data, or see what a page looks like for the signed-in user `henrymdeutsch@gmail.com`.
---

# Check

Use this skill to see a page from Henry's perspective instead of from an anonymous browser session.

## Workflow

1. Read repo-local check docs first when they exist.
   Prefer repo docs such as `agent-docs/coding-conventions.md` and any architecture notes that describe how the product should support visual verification.
   Keep runtime config, notes, screenshots, and saved auth state under this skill's per-repo folder at `repos/<repo-key>/`.
   If the repo is not configured yet, run the global setup script first so the per-repo folder is created automatically before continuing.

2. Prefer an existing Henry auth state before asking for a fresh login.
   The default state file should live in this skill's per-repo folder.
   Verify the saved session before trusting it.

3. Refresh Henry's auth state without using Google login automation when possible.
   Prefer the global `scripts/ensure-auth-state.sh` flow plus repo config.
   When the app uses database-backed NextAuth with Prisma, prefer the global `scripts/seed-nextauth-prisma-state.mjs` helper.
   Only fall back to interactive sign-in if the app truly requires it, such as when the Henry user record does not exist locally yet.

4. Resolve the target page from the user's request.
   If the user invokes `/check /some-path`, treat that path as the page route or URL to open, not as a filesystem path.
   If the user invokes `/check` without a path, infer the route and any in-app navigation from the current task context, prioritizing the feature or surface you were just changing.
   If several views are plausible, choose the one that best matches the current work and say which one you checked.

5. Capture the target page with the saved auth state.
   Reuse the global `scripts/check-page.sh` helper to take a screenshot of the requested route or URL.
   If the page requires extra navigation after load, extend the skill or add the smallest repo-side product change needed so the skill can perform that flow autonomously next time.
   Save screenshots under the per-repo folder inside this skill so the workflow stays centralized.
   When responding to the user, prefer rendering the screenshot inline with Markdown image syntax using the absolute file path so the Codex desktop app shows a preview instead of just a file card.

6. Call out when the product surface is not directly addressable.
   If a feature lives behind client-only tabs, modal state, or other non-addressable UI state, say that a small refactor such as a deep-linkable query param or route would make `/check` much more useful.
   Ask the user explicitly whether you should make that refactor before touching the product code.

7. Open the saved screenshot in Codex and inspect it directly.
   Do not treat command success or HTML output as visual verification.
   Call out whether the requested data or UI is actually visible from Henry's perspective.

8. Patch the skill and repo-local helpers when the workflow breaks.
   If a missing step, flaky command, or auth edge case shows up during real use, update this skill first and keep repo-local additions minimal before trying again.

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
- Prefer `http://127.0.0.1:3000` for local auth capture unless repo-local docs say otherwise.
- Treat saved storage state as a secret.
- Do not claim Henry-authenticated verification unless session verification passed and you visually inspected the screenshot.
- When `/check` is invoked without a path, do not stop just because the user omitted it; infer the most relevant page from context and proceed.
- Prefer local session seeding over third-party auth automation when the app uses database-backed sessions.
- Prefer moving reusable shell, Python, and Node automation into this global skill instead of duplicating it inside individual repos.
- Never refactor the product code to make tabs or views deep-linkable without the user's explicit sign-off.
- If the user needs a logged-in screenshot and the session is stale, keep iterating until the login capture flow works or you hit a real blocker that requires Henry to act.

## Final Response

Report:

- whether the Henry session was reused or refreshed
- which route or URL you checked, and whether it was inferred from context
- the screenshot path
- an inline screenshot preview using Markdown image syntax with the absolute file path, unless the user asks for text-only output
- whether Henry-specific data was visible
- any remaining auth or page-load uncertainty
