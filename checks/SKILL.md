---
name: checks
description: First reproduce and screenshot the reported UI or product issue, then iteratively verify, stress, and fix it by using screenshots and direct browser inspection to generate bug hypotheses, probe likely breaking routes or states, edit code for confirmed issues, and loop until the feature is visibly right and no obvious adjacent breakage remains. Use when the user invokes `/checks`, wants you to keep checking a page until it looks right, or expects an autonomous bug-hunting, screenshot, compare, edit, and fix loop rather than a single passive verification pass.
---

# Checks

Use this skill when one screenshot is not enough and the job is to first reproduce the reported issue, then actively hunt for problems introduced by the current work, fix the confirmed bugs, and keep iterating until the feature actually works in the relevant product context.

## Workflow

1. Start from the existing `$check` workflow.
   Open [SKILL.md](/Users/Henry/.codex/skills/check/SKILL.md) and reuse its auth, route-resolution, and screenshot capture flow instead of rebuilding it.
   Treat `$checks` as a persistent outer loop around `$check`, not as a separate screenshot system.
   If the repo already has a headless verification harness, that is the default loop.
   Prefer bundled Chromium for unpacked extension verification, and use CDP while staying headless when Playwright alone cannot control the necessary extension targets.
   Do not switch to headed just because the task is iterative.

2. Resolve the target route, success criteria, and feature context.
   If the user invokes `/checks /some-path`, treat that as the page route or URL to check.
   If the user invokes `/checks` without a path, infer the route and any necessary in-app navigation from the current task context.
   Translate the user's request and the recent chat context into concrete visual, behavioral, and workflow expectations before editing anything.
   Identify the new or changed feature being verified, what user journey it belongs to, and which nearby routes, states, roles, data shapes, responsive sizes, or edge cases could plausibly break because of it.
   Define the metric of success before fixing anything: what screenshot, DOM state, console/network condition, workflow outcome, or artifact evidence would prove the issue is fixed.
   If there is no observable success metric, stop and explain the missing verification target instead of entering a fix loop.

3. Reproduce the reported issue before editing anything.
   The first job is verification: use the resolved route, state setup, and `$check` capture flow to make the bug happen in the current environment.
   Capture screenshot evidence that shows the reported bug or mismatch. For temporal issues such as loading, streaming, animation, or state transitions, capture enough screenshots to prove the bad progression or stuck state.
   Inspect the screenshot directly in Codex and compare it against the user's report and the success metric.
   Do not move on to diagnosis, bug hypotheses, or code changes until you have screenshot evidence reproducing the issue.
   If you cannot reproduce the issue, do not start fixing speculatively. Report what you tried, include the screenshot or direct evidence you captured, and explain what state, data, credentials, route, timing, or environment detail is missing.

4. Generate the initial bug-hypothesis list only after reproduction.
   Once the issue has been reproduced, write down the most likely failure modes for the feature in this repo, grounded in the screenshot evidence and what the product flow touches.
   Include route-level hypotheses such as broken deep links, missing loading/error/empty states, auth redirects, stale data, responsive layout failures, form validation gaps, console/runtime errors, and regressions on adjacent pages.
   Prioritize hypotheses by user impact, likelihood, and how directly they connect to the reproduced evidence, then choose the first route or state to probe.

5. Probe for confirmed bugs, not just visual mismatches.
   Compare the screenshot and direct browser evidence against the request, the feature context, and the current hypothesis list.
   Try to find breaking routes or states that a real user could hit, especially routes adjacent to the new feature or paths implied by the chat context.
   Use screenshots, console errors, network failures, DOM inspection, Playwright locators, native artifact checks, and in-app navigation as evidence.
   Treat a hypothesis as actionable only when you have reproduced or directly observed the issue.
   List the specific confirmed bug or mismatch you are fixing next.
   Prefer the smallest code change that materially moves the page toward the requested result.

6. Edit the code and run the relevant validations.
   Make the change in the repo.
   Run the relevant local checks for the code you touched.
   If the repo has required final checks such as `npm run lint` or `npm run build`, run them before claiming the loop is done.

7. Revisit the page and verify again.
   Use the same target route unless the request or the product flow clearly requires another route.
   For intermediate passes, you may verify with a fresh screenshot, the full logged-in DOM, Playwright locators, native parsing, or other direct page inspection methods.
   Compare what you observe against the request, the confirmed bug, and the remaining hypotheses, not against your intent.
   For extension UIs, prefer the repo's headless persistent Chromium path plus the extension page surrogate such as `chrome-extension://<extension-id>/index.html` or `options.html` unless the bug is specifically about the docked browser shell.
   If Playwright cannot reach MV3 service workers or extension pages cleanly, use CDP target attachment and keep the loop headless.

8. Expand or prune the hypothesis list as you learn.
   After each probe or fix, update the hypothesis list based on the actual browser evidence.
   Add newly suspected bugs when the page behavior points to them.
   Drop hypotheses that are contradicted by direct inspection.
   Keep moving from the most likely or highest-impact remaining breakage toward less likely edge cases.

9. Repeat until one of two conditions is true.
   Stop only when a final fresh screenshot shows the requested result closely enough to satisfy the user's ask and the high-impact adjacent-route hypotheses have either been checked or reasonably ruled out.
   Otherwise keep looping as long as another reasonable bug hypothesis, route probe, or fix attempt exists.
   If the loop loses its metric of success, stop and re-establish it before making more edits.

10. Every 5-10 verification cycles, pause and re-evaluate the approach.
   Ask explicitly whether the current loop is converging or whether you need to fundamentally rethink the plan, such as changing the diagnosis, route, state setup, selector strategy, or implementation path.
   This self-evaluation checkpoint does not require taking a screenshot every single time if other direct verification methods are more efficient.

11. Escalate only on real blockers.
   If auth cannot be refreshed, the needed data does not exist locally, the requested state is not addressable, or the request conflicts with the codebase in a meaningful way, explain the blocker clearly.
   If a product refactor such as a deep-linkable tab or route would make the verification possible or more reliable, ask the user explicitly before changing product code.

## Operating Rules

- Use screenshots as the source of truth for completion.
- When verifying streaming text, screenshots must prove progression, not just final presence. Capture at least two screenshots from the same stream while it is still in flight: one where the streamed message is partially filled, and a later one where visibly more text has filled. DOM polling, logs, cursor counts, or final screenshots can support the result, but they do not replace those two in-flight screenshots.
- Treat `/checks` as an active bug-hunting and bug-fixing workflow, not a passive screenshot audit.
- Let the recent chat context guide what adjacent routes, states, and user journeys deserve probing.
- Try to find real breakage before declaring success, but do not invent speculative bugs without evidence.
- A blank or mostly blank screenshot of a PDF, resume, document preview, canvas, iframe, or embedded viewer is not a successful visual check.
- When an embedded viewer does not paint in headless Chromium, use native artifact checks such as page count and extracted text as supporting evidence, then escalate to a real/headed browser or rendered-page screenshot before declaring visual success.
- Do not add product-code debug fixtures, mock data, routes, buttons, or other verification-only scaffolding just to make the loop easier; keep temporary setup under the `$check` skill runtime.
- Do not stop after one pass just because the code looks correct.
- Do not declare success until you have inspected a fresh screenshot from the relevant route.
- Do not stop just because the primary route looks correct if nearby high-impact hypotheses remain unchecked and are cheap to probe.
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
- Keep confirmed bug notes concise enough that they can guide the next edit without turning the loop into a separate bug report.

## Final Response

Always end with one of these outcomes:

- Success: include the route checked, whether the Henry session was reused or refreshed, a short summary of what changed, the most important hypotheses or adjacent routes probed, and an inline screenshot preview using Markdown image syntax with the absolute file path.
- Blocked: explain why the request could not be completed, what you verified, and what would need to change for the loop to succeed.

When useful, also mention how many edit/check loops and route/state probes you performed.
