---
name: checks
description: Iteratively implement and visually verify a requested UI or product change by repeatedly visiting the target page, comparing real screenshots against the user's request, editing code, and looping until the result matches spec or a real blocker remains. Use when the user invokes `/checks`, wants you to keep checking a page until it looks right, or expects an autonomous edit, screenshot, compare, and fix loop rather than a single verification pass.
---

# Checks

Use this skill when one screenshot is not enough and the job is to keep iterating until the page actually matches what the user wants.

## Workflow

1. Start from the existing `$check` workflow.
   Open [SKILL.md](/Users/Henry/.codex/skills/check/SKILL.md) and reuse its auth, route-resolution, and screenshot capture flow instead of rebuilding it.
   Treat `$checks` as a persistent outer loop around `$check`, not as a separate screenshot system.
   If the repo already has a headless verification harness, that is the default loop.
   Prefer bundled Chromium for unpacked extension verification, and use CDP while staying headless when Playwright alone cannot control the necessary extension targets.
   Do not switch to headed just because the task is iterative.

2. Resolve the target route and success criteria.
   If the user invokes `/checks /some-path`, treat that as the page route or URL to check.
   If the user invokes `/checks` without a path, infer the route and any necessary in-app navigation from the current task context.
   Translate the user's request into concrete visual or behavioral expectations before editing anything.

3. Capture a baseline screenshot immediately.
   Reuse the Henry-authenticated `$check` flow first so you can see the current state of the page before making changes.
   Inspect the screenshot directly in Codex. Do not trust code inspection alone.

4. Compare the screenshot against the request and identify the smallest next change.
   List the specific mismatch you are fixing next.
   Prefer the smallest code change that materially moves the page toward the requested result.

5. Edit the code and run the relevant validations.
   Make the change in the repo.
   Run the relevant local checks for the code you touched.
   If the repo has required final checks such as `npm run lint` or `npm run build`, run them before claiming the loop is done.

6. Revisit the page and verify again.
   Use the same target route unless the request or the product flow clearly requires another route.
   For intermediate passes, you may verify with a fresh screenshot, the full logged-in DOM, Playwright locators, native parsing, or other direct page inspection methods.
   Compare what you observe against the request again, not against your intent.
   For extension UIs, prefer the repo's headless persistent Chromium path plus the extension page surrogate such as `chrome-extension://<extension-id>/index.html` or `options.html` unless the bug is specifically about the docked browser shell.
   If Playwright cannot reach MV3 service workers or extension pages cleanly, use CDP target attachment and keep the loop headless.

7. Repeat until one of two conditions is true.
   Stop only when a final fresh screenshot shows the requested result closely enough to satisfy the user's ask.
   Otherwise keep looping as long as another reasonable fix attempt exists.

8. Every 5-10 verification cycles, pause and re-evaluate the approach.
   Ask explicitly whether the current loop is converging or whether you need to fundamentally rethink the plan, such as changing the diagnosis, route, state setup, selector strategy, or implementation path.
   This self-evaluation checkpoint does not require taking a screenshot every single time if other direct verification methods are more efficient.

9. Escalate only on real blockers.
   If auth cannot be refreshed, the needed data does not exist locally, the requested state is not addressable, or the request conflicts with the codebase in a meaningful way, explain the blocker clearly.
   If a product refactor such as a deep-linkable tab or route would make the verification possible or more reliable, ask the user explicitly before changing product code.

## Operating Rules

- Use screenshots as the source of truth for completion.
- Do not stop after one pass just because the code looks correct.
- Do not declare success until you have inspected a fresh screenshot from the relevant route.
- Headless browsers are the default. Use them first, keep using them when possible, and only escalate to a headed browser when the bug is truly about browser chrome, windowing, or focus behavior that headless Chromium plus Playwright/CDP cannot expose.
- For unpacked extension automation, prefer bundled Chromium over Google Chrome.
- During long-running loops, do not mindlessly repeat the same check pattern; every 5-10 verification cycles, ask whether the approach itself should change.
- Intermediate self-evaluations do not require a screenshot if the logged-in DOM, locator assertions, or other direct inspection methods can tell you whether you are moving in the right direction.
- Prefer Henry-authenticated verification when the page is user-specific.
- If the capture flow breaks, fix the global `$check` skill or its per-repo runtime before giving up.
- Never refactor the product code to make tabs, views, or flows deep-linkable without the user's explicit sign-off.
- If the route is omitted, infer it from context and proceed.
- If several pages are plausible, choose the strongest candidate, say which one you chose, and continue.
- If you choose headed instead of an available headless path, state the reason in your commentary so the tradeoff is explicit.
- Keep going until the result is visibly right or you can explain concretely why the request is impossible in the current environment.

## Final Response

Always end with one of these outcomes:

- Success: include the route checked, whether the Henry session was reused or refreshed, a short summary of what changed, and an inline screenshot preview using Markdown image syntax with the absolute file path.
- Blocked: explain why the request could not be completed, what you verified, and what would need to change for the loop to succeed.

When useful, also mention how many edit/check loops you performed.
