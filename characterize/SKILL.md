---
name: characterize
description: Reviews all staged, unstaged, and untracked changes in the working tree and groups them into logical buckets that likely belong in separate commits or parallel tasks. Use when the user wants to understand a dirty tree before staging or committing, split local changes into coherent chunks, or explicitly asks for an `auto` mode that stages, commits, and pushes each bucket in sequence.
---

# Characterize

Review the current working tree and explain how its changes cluster into coherent tasks.

## Arguments

- Default: characterize the working tree and stop.
- `auto`: characterize first, then stage, commit, and push each bucket in order without waiting for another prompt.

## What to do

1. Run `git rev-parse --show-toplevel` and treat that path as the current repo root.
2. Read Codex's local thread index before grouping changes. Use `~/.codex/state_5.sqlite` as the source of truth for unarchived chats and query the `threads` table for rows where `archived = 0` and `cwd = <repo_root>`, ordered by `updated_at_ms DESC`. Read the `title` and `rollout_path` columns from that query.
3. For each returned chat, open the JSONL transcript at `rollout_path`. These are typically under `~/.codex/sessions/...`. Skim for gist rather than reading every token: prefer the main user asks, major assistant conclusions, and any clear feature names or bug labels. Use the split between chats as one input into how the working tree should be bucketed.
4. If `~/.codex/state_5.sqlite` is unavailable, fall back to `~/.codex/session_index.jsonl` for titles and `~/.codex/sessions/` for active transcript files, but prefer the SQLite query whenever possible because it gives the clean unarchived set for the current repo.
5. Run `git diff HEAD` and `git status --short` to capture staged, unstaged, and untracked changes.
6. Skim for intent rather than every line. Focus on file paths, symbols, feature names, and why the edits belong together.
7. Group the work into however many buckets the changes genuinely call for. Do not aim for a target count just because the skill asked for one. One bucket is fine when the work is tightly coupled, and it generally should not exceed `8` buckets unless the user explicitly asks for a finer split.
8. Let the chats influence the split when they reflect genuinely separate streams of work, but do not overfit to thread boundaries when the code changes are tightly coupled and belong in one commit. Active chats are a useful signal, not a quota.
9. For each bucket, provide:
   - a short label in kebab-case
   - the files that belong to it
   - a `3-5` sentence plain-English summary of what changed and why
   - one conventional-commit style message
10. If the user did not ask for `auto`, stop after presenting the buckets.
11. If the user asked for `auto`, run the workflow below for each bucket in order.

## Resist Over-Splitting

The common failure mode is turning one feature into several fake buckets. Merge related edits when they share a feature name, a domain concept, or a clear dependency chain such as a route, helper, and test that only make sense together.

Do not split work just to keep the diff size down. Commits in the `500`, `1000`, or even `2000` line range are acceptable when the logic is closely tied and the resulting commit still tells one coherent story. Optimize for conceptual cohesion over small patch size.

Also resist making docs-only buckets by default. Markdown files, including `agent-docs/`, are usually supporting changes that belong with a feature or fix bucket rather than their own commit. If a docs change is feature-agnostic, fold it into the closest relevant bucket instead of creating a separate docs commit. Only split pure Markdown files into their own bucket in rare cases, such as when the user explicitly asked for docs-only work or the docs themselves are the primary deliverable.

## Output Format

For each bucket:

**[Bucket name]**
Label: `bucket-label`
[3-5 sentences describing what changed and why, written for someone who has not seen the diff.]
Files: `path/a.ts`, `path/b.ts`
Commit: `feat(scope): short description`

After listing all buckets, end with one short sentence telling the user they can refer to a bucket by its label in the next prompt if they want help staging or committing it.

## Auto Mode Workflow

Process buckets one at a time in the order listed:

1. Run `git restore --staged .` to clear the index.
2. Stage only that bucket's files with targeted `git add <path>` commands. Use `git add -p <path>` when only part of a file belongs to the bucket.
3. Commit with the bucket's suggested commit message.
4. Push with `git push`.
5. Report the commit hash and push result before moving to the next bucket.

If any step fails, stop immediately and report the error. Do not continue to later buckets.

## Constraints

- Do not stage, commit, or push anything unless the user explicitly asked for `auto`.
- Never use broad staging commands such as `git add .` or `git add -A`.
- Prefer coherent buckets over many tiny ones.
