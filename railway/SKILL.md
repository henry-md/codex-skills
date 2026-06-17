---
name: railway
description: Investigate a failed Railway deployment when the user explicitly invokes the railway skill or asks to debug a Railway deployment failure. Anchor the work to a specific failed deployment ID, read the full deployment-specific logs, reproduce the failing Railway command locally, make the smallest relevant fix, verify locally, stage only the Railway-related changes without committing or pushing, and self-improve this skill when reusable learnings would save significant time in future Railway investigations.
---

# Railway

Use this skill only when the Railway-linked service has a failed deployment to investigate.

## What To Do

1. Connect to Railway and identify the exact failed deployment first.
   Use deployment-specific status and logs, not just the latest successful-looking output.
   If there is no failed Railway deployment, say so and stop.
   For old failures with missing runtime logs, use `railway deployment list --json` on the deployment ID; `meta.configFile` and `meta.serviceManifest.deploy` can show whether `railway.json` was applied.

2. Read the full logs for that failed deployment.
   Check build logs and deploy/runtime logs for the same deployment ID.
   Prefer full logs over filtered snippets when the failure stage is unclear.
   When logs may contain dashboard URLs or tokens, redact secret-looking query params and environment values before printing them into the transcript.

3. Reproduce the failing step locally with the same command Railway uses.
   For this repo, prefer exact commands such as `pnpm install --frozen-lockfile --prefer-offline`, `pnpm run build`, and any relevant start/runtime checks.

4. Fix the issue locally with the smallest relevant change set.
   Leave unrelated work in the tree alone.
   If the failure reveals a repeatable project gotcha, add or update a short note under `agent-docs/bug-fixes/`.

5. Re-verify locally after the fix.
   Re-run the failing Railway command locally, then run any follow-up verification needed to confirm the deployment should pass.

6. Self-document durable learnings.
   This skill is intentionally self-documenting and self-improving. When using it reveals a reusable Railway investigation shortcut, a recurring CLI/logging gotcha, a repo-specific deployment command, or a failure pattern that would save significant time in a future run, update this skill without waiting for explicit user direction.
   Keep self-updates concise, generalizable, and free of secrets, tokens, private URLs, noisy one-off logs, and user-specific incident details.
   If the learning is project-specific rather than Railway-skill-specific, prefer a short note under that repo's `agent-docs/bug-fixes/` or architecture docs instead of bloating this skill.

7. Stage only the files relevant to this Railway task.
   First run `git restore --staged .`.
   Then use targeted `git add <path>` and `git add -p <path>` to stage only the Railway-fix changes from this chat.
   If you updated this Railway skill itself, do not stage that skill change in the target app repo; leave it as a separate skills-repo change unless the user explicitly asks to publish skill updates.
   Do not commit or push.

## Constraints

- Do not use this skill unless a failed Railway deployment exists.
- Always anchor the investigation to a specific failed deployment ID.
- Do not trust partial logs when Railway can provide deployment-specific full logs.
- Do not stage unrelated local edits.
- Do not commit anything yourself.
- Do not add raw deployment logs, secrets, tokens, or incident-only details to this skill.

## Final Response

Report:
- the failed deployment ID and what actually failed
- the root cause
- what you changed
- what you verified locally
- which files were staged
- whether this skill or repo docs were updated with reusable learnings
- one suggested commit message
