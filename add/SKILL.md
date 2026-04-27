---
name: add
description: Surgically stage only the current chat's relevant changes while leaving unrelated work untouched. Use when the user explicitly invokes `add` to rebuild the index for this conversation only, including earlier chat context. By default it stages the chat-scoped result and suggests a commit message. `/add push` additionally commits only that work plus the minimum already-modified diff required for a successful Railway build, pushes checked-out `main`, then watches the resulting Railway deployment. If Railway fails for a generated or build-support artifact reason that can be fixed without editing developer-authored source files, regenerate the needed artifacts, amend the just-pushed commit, and force-push with lease instead of creating a separate fix commit. This skill never creates branches or opens PRs.
---

# Add

Use this skill when the user wants a clean, chat-scoped commit boundary without scooping up unrelated local work.

This skill is for surgical staging and optional commit/push only. It works only on checked-out `main`, does not create branches or PRs, and does not rewrite developer-authored code to make staging easier. In `/add push`, it may regenerate build-support artifacts such as lockfiles or other generated files when that is the smallest change needed to make the just-pushed commit build on Railway.

## Hard rules

- Rebuild the index from scratch for this chat.
- Treat the scope as the full current chat, not just the latest message.
- `/add` stages only and suggests commit message(s).
- `/add push` stages only the chat-scoped changes plus the minimum already-modified Railway-build-critical supporting diff, commits them on checked-out `main`, and pushes `main`.
- After `/add push`, watch the Railway deployment for the pushed commit instead of treating `git push` alone as success.
- Prefer commit slices of roughly 500 changed lines when the work can be split cleanly.
- Never push any single commit over 2,000 changed lines.
- Use partial-file staging whenever a file mixes in-scope and out-of-scope work.
- Never push from any branch other than the currently checked out `main`.
- If Railway fails and the fix only requires regenerating or reinstalling generated/build-support artifacts, amend the just-pushed commit and use `git push --force-with-lease origin main` rather than creating a follow-up fix commit.
- If Railway fails and the fix would require editing developer-authored source files, stop and report the blocker instead of making more code changes under `/add push`.

## Invocation modes

- `/add`
  Rebuild the staged set for this chat only, then stop and suggest commit message(s).
- `/add push`
  Rebuild the staged set for this chat only, then commit and push it on checked-out `main`. The task is not complete unless all intended commits succeed, the push succeeds, and the resulting Railway deployment reaches a satisfactory outcome or a clearly-reported blocker.

## Workflow

1. Run `git branch --show-current` and stop unless it is exactly `main`.
2. Run `git restore --staged .` to clear any pre-existing staged changes.
3. Determine what belongs to this chat. In `/add push` mode, also identify the minimum already-modified extra hunks required for a successful Railway build.
4. Plan one or more commit slices. Prefer slices around 500 changed lines when practical. If any required slice cannot be split safely below 2,000 changed lines, stop instead of forcing a jumbo push.
5. Stage fully relevant files with `git add <path>`. Stage mixed files with `git add -p <path>`, splitting or patch-editing hunks as needed. If the relevant parts cannot be isolated safely, stop instead of over-staging.
6. Review `git diff --cached --stat` and `git diff --cached` to confirm the index contains only this chat plus any Railway-build-critical supporting diff.
7. Write one commit message per planned slice using the repo's style, such as `feat(scope): ...`, `fix(scope): ...`, `refactor(scope): ...`, or `chore(scope): ...`.
8. In plain `/add`, stop there and report that the result was staged only, including the suggested commit message. If `/add push` would be better split into multiple commits, say so.
9. In `/add push`, commit one slice or a short logical series, restaging between commits as needed.
10. Push explicitly from checked-out `main`, for example `git push origin main`.
11. After pushing in `/add push`, identify the Railway deployment for the pushed commit and poll deployment-specific status and logs until it succeeds, fails, or a short bounded wait makes further polling unreasonable.
12. If Railway succeeds, the job is done.
13. If Railway fails, inspect the deployment-specific logs and decide whether the failure can be fixed without editing developer-authored source files. Allowed recovery work includes reinstalling dependencies and regenerating generated/build-support artifacts such as lockfiles or other derived files that should have accompanied the commit.
14. If that generated-artifact recovery is enough, make only those artifact changes, verify locally with the failing Railway command, amend the just-pushed commit, force-push with lease, and then watch the new Railway deployment again.
15. If the Railway failure would require editing developer-authored source files or any non-generated product logic, stop and report the blocker clearly instead of pushing a separate fix commit.
16. If staging, commit, or push fails, stop and report the blocker clearly.

## Staging rules

- Never use broad staging such as `git add .`, `git add -A`, or directory-wide adds.
- Never commit or push in plain `/add` mode.
- Never create or switch branches automatically.
- Never edit product code, generated files, config, or other source files just to make the commit boundary cleaner.
- After a Railway failure in `/add push`, you may update generated/build-support artifacts that are a direct consequence of the already-committed chat-scoped changes, but do not edit developer-authored source files.
- Prefer exact file paths whenever the whole file belongs to this chat.
- Treat `git add -p` as the normal tool for mixed files.
- When a file contains both this chat's work and unrelated edits, default to partial staging rather than whole-file staging.
- If two nearby hunks are both part of this chat and belong in one commit, stage them together.
- Never include extra diff beyond this chat unless that exact change is already present and required for Railway to build successfully.
- If a required build input such as a lockfile, config file, build script, or dependency change is already present and needed for Railway to build successfully, include only the minimum hunks required.
- If Railway would still build without a nearby change, leave that change out even if it feels related.
- When splitting into multiple commits, prefer an order that keeps Railway buildable when realistic. If that is not realistic, do not split purely for aesthetics.
- Do not pull in unrelated earlier work just to make the diff feel tidier.

## Final response requirements

- In plain `/add`, explicitly say the result was staged only and provide the suggested commit message.
- In `/add push`, explicitly say whether the result was committed, pushed, and Railway-verified, and include the final commit hash or hashes if available.
- If `/add push` had to amend and force-push the just-pushed commit to repair generated/build-support artifacts, explicitly say so.
- If blocked, explicitly say it was blocked before completion and explain why.

## One-line summary

`/add` means: rebuild the index surgically for this chat on `main`, then suggest a commit message.

`/add push` means: do the same surgical staging on checked-out `main`, include only the minimum extra diff required for Railway to build successfully, prefer commit slices around 500 changed lines, never push a commit over 2,000 changed lines, commit and push `main`, then watch Railway and only rewrite the just-pushed commit when a generated-artifact-only fix is enough.
