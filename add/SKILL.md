---
name: add
description: Surgically stage only the current chat's relevant changes while leaving unrelated work untouched. Use when the user explicitly invokes `add` to rebuild the index for this conversation only, including earlier chat context. By default it stages the chat-scoped result and suggests a commit message. `/add push` additionally commits only that work plus the minimum already-modified diff required for a successful Railway build, then pushes checked-out `main`. This skill never creates branches or opens PRs.
---

# Add

Use this skill when the user wants a clean, chat-scoped commit boundary without scooping up unrelated local work.

This skill is for surgical staging and optional commit/push only. It works only on checked-out `main`, does not create branches or PRs, and does not rewrite code to make staging easier.

## Hard rules

- Rebuild the index from scratch for this chat.
- Treat the scope as the full current chat, not just the latest message.
- `/add` stages only and suggests commit message(s).
- `/add push` stages only the chat-scoped changes plus the minimum already-modified Railway-build-critical supporting diff, commits them on checked-out `main`, and pushes `main`.
- Prefer commit slices of roughly 500 changed lines when the work can be split cleanly.
- Never push any single commit over 2,000 changed lines.
- Use partial-file staging whenever a file mixes in-scope and out-of-scope work.
- Never push from any branch other than the currently checked out `main`.

## Invocation modes

- `/add`
  Rebuild the staged set for this chat only, then stop and suggest commit message(s).
- `/add push`
  Rebuild the staged set for this chat only, then commit and push it on checked-out `main`. The task is not complete unless all intended commits and the push succeed.

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
11. If staging, commit, or push fails, stop and report the blocker clearly.

## Staging rules

- Never use broad staging such as `git add .`, `git add -A`, or directory-wide adds.
- Never commit or push in plain `/add` mode.
- Never create or switch branches automatically.
- Never edit product code, generated files, config, or other source files just to make the commit boundary cleaner.
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
- In `/add push`, explicitly say the result was committed and pushed, and include the commit hash or hashes if available.
- If blocked, explicitly say it was blocked before completion and explain why.

## One-line summary

`/add` means: rebuild the index surgically for this chat on `main`, then suggest a commit message.

`/add push` means: do the same surgical staging on checked-out `main`, include only the minimum extra diff required for Railway to build successfully, prefer commit slices around 500 changed lines, never push a commit over 2,000 changed lines, then commit and push `main`.
