---
name: add
description: Surgically stage only the current chat's relevant changes while leaving unrelated work untouched. Use when the user explicitly invokes the add skill to rebuild the index from this conversation only, including earlier messages in the same chat. By default it stages the chat-scoped result and suggests a commit message. `/add push` additionally commits only that chat-scoped work plus the minimum already-modified diff required for a successful Railway build, then pushes `main` directly from `main`. This skill always operates on `main`, never creates a branch, and never opens a PR.
---

# Add

Use this skill when the user wants a clean, chat-scoped commit boundary without scooping up unrelated local work.

This skill is for surgical staging and optional commit/push only. It does not create branches. It does not open pull requests. It does not rewrite code to make staging easier.

Treat the scope as everything discussed in the full current chat, not just the latest message. In most cases that should collapse into one cohesive staged set and one commit message. In `/add push` mode, only include the chat-scoped work plus the minimum already-present supporting diff required for Railway to build successfully. When the chat-scoped diff alone is over roughly 500 changed lines and the work can be cleanly described as two or more separate pieces of functionality, prefer a short series of commits instead of forcing one oversized commit.

## Core behavior

- Always rebuild the index from scratch for this chat's scope.
- Always operate on `main`.
- Never create or switch to a feature branch as part of this skill.
- Default `/add` behavior is staging plus a suggested commit message only.
- `/add push` means stage only the chat-scoped changes plus the minimum already-modified supporting diff required for a successful Railway build, commit them, and push `main`.
- Prefer one commit by default, but if the chat-scoped diff is over roughly 500 changed lines and clearly splits into multiple functional slices, prefer multiple commits.
- Partial-file staging is expected. When a file mixes in-scope and out-of-scope work, stage only the relevant hunks.
- Never push from a workspace branch or any branch other than the currently checked out `main`.

## Invocation modes

- `/add`
  Rebuild the staged set for this chat only, then stop and suggest one commit message.
- `/add push`
  Rebuild the staged set for this chat only, then commit it on `main` and push `main`. The task is not complete unless all intended commits and the push succeed.

## What this skill must do

- Clear any pre-existing staged changes first so the index reflects only this chat.
- Determine whether the chat-scoped diff is over roughly 500 changed lines and cleanly separable into multiple functional slices.
- Stage fully relevant files with explicit `git add <path>` commands.
- Stage partially relevant files with `git add -p <path>` and accept only the hunks that belong to this chat.
- Split hunks when needed so mixed files can be staged surgically instead of wholesale.
- In `/add push` mode, include only the minimum already-modified extra hunks needed for a successful Railway build.
- Produce one commit message for each intended commit that describes only that staged result and matches the repo's style.
- In `/add push` mode, use those messages for the real commit or commit series and then push `main`.

## What this skill must never do

- Never create a branch.
- Never switch branches automatically.
- Never open a PR.
- Never use broad staging such as `git add .`, `git add -A`, or directory-wide adds.
- Never commit or push in plain `/add` mode.
- Never push from a workspace branch, feature branch, or detached HEAD.
- Never edit product code, generated files, config, or other source files just to make the commit boundary cleaner.
- Never include extra diff beyond the chat unless that exact change is required for a successful Railway build.
- Never silently include unrelated work just because it is nearby in the same file.

## Branch rule

This skill always works off `main`.

1. Check the current branch immediately.
2. If the current branch is not exactly `main`, stop and tell the user this skill only runs on `main` and never pushes from a separate workspace branch.
3. Do not create a new branch.
4. Do not switch to `main` automatically if the worktree is dirty.

## Workflow

1. Run `git branch --show-current` and verify the branch is `main`. If not, stop and report that blocker.
2. Run `git restore --staged .` so the index is cleared before rebuilding it for this chat.
3. Inspect the current chat and the changed files to determine what belongs in scope. In `/add push` mode, also identify the minimum already-modified extra hunks required for a successful Railway build.
4. Estimate the size of the chat-scoped diff. If it is over roughly 500 changed lines and the work cleanly separates into multiple functional slices, make a short commit plan instead of forcing one jumbo commit.
5. For any file where all current edits for the current slice belong in scope, run `git add <path>`.
6. For any file that mixes chat-related and unrelated edits, run `git add -p <path>` and stage only the relevant hunks.
7. If a hunk mixes relevant and unrelated lines, split it. If needed, use patch-editing behavior to isolate only the chat-related block.
8. If the relevant parts of a file cannot be isolated safely with patch staging, stop and tell the user instead of over-staging.
9. After rebuilding the staged set for the current slice, review `git diff --cached --stat` and `git diff --cached` to confirm the index matches only this chat plus any Railway-build-critical supporting diff.
10. Write one commit message per planned slice. Prefer the repository's existing style such as `feat(scope): ...`, `fix(scope): ...`, `refactor(scope): ...`, or `chore(scope): ...`.
11. If the invocation is plain `/add`, stop there. Report that the result was staged only, and include the suggested commit message. If a split would be better in `/add push` mode, say so explicitly.
12. If the invocation is `/add push` and one commit is planned, commit with that message.
13. If the invocation is `/add push` and multiple commits are planned, commit each staged slice separately in logical order, restaging between commits as needed.
14. In `/add push` mode, push explicitly from the checked out `main`, for example `git push origin main`.
15. If commit or push fails for any reason, stop and report the blocker clearly.

## Staging guidance

- Prefer exact file paths whenever the whole file belongs to this chat.
- Treat `git add -p` as the normal tool for mixed files, not as an edge case.
- When a file contains both this chat's work and unrelated edits, the default assumption should be partial staging, not whole-file staging.
- If two nearby hunks are both part of this chat and belong in one commit, stage them together.
- If a required build input such as a lockfile, config file, build script, or dependency change is already present in the diff and is needed for Railway to build successfully, include only the minimum hunks required.
- If Railway would still build without a nearby change, leave that change out even if it feels related.
- When splitting into multiple commits, prefer an order where each commit keeps Railway buildable. If that is not realistic, do not split purely for aesthetics.
- Do not pull in unrelated earlier work just to make the diff feel tidier.

## Push behavior

- `/add push` commits only the surgically staged index or staged series.
- `/add push` pushes only `main`, and it must do so while checked out on `main`.
- `/add push` never commits on a separate workspace branch and then pushes `main` from somewhere else.
- `/add push` is incomplete until all intended commits and the push succeed.
- Surface blockers immediately, especially auth failures, non-fast-forward pushes, index locks, merge conflicts, or cases where relevant hunks cannot be isolated safely.

## Final response requirements

- In plain `/add`, explicitly say the result was staged only and provide the suggested commit message.
- In `/add push`, explicitly say the result was committed and pushed, and include the commit hash or hashes if available.
- If blocked, explicitly say it was blocked before completion and explain why.

## One-line summary

`/add` means: rebuild the index surgically for this chat on `main`, then suggest a commit message.

`/add push` means: do the same surgical staging on `main`, include only the minimum extra diff required for a successful Railway build, then commit on `main` and push `main`, using multiple commits when the chat-scoped diff is large and cleanly separable.
