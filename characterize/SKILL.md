---
name: characterize
description: Reviews all staged, unstaged, and untracked changes in the working tree and groups them into logical buckets that likely belong in separate commits or parallel tasks. Use when the user wants to understand a dirty tree before staging or committing, split local changes into coherent chunks, or explicitly asks for a `push` mode that stages and commits each bucket locally, verifies the stack, then pushes once.
---

# Characterize

Review the current working tree and explain how its changes cluster into coherent tasks.

## Arguments

- Default: characterize the working tree and stop.
- `push`: characterize first, then stage and commit each bucket locally, verify the full commit stack, and push once without waiting for another prompt.

When the user later says something like "commit all these and push" after a non-`push` characterize run, treat that as entering the same `push` workflow below. Do not infer permission to change branches from that follow-up alone.

## What to do

1. Run `git rev-parse --show-toplevel` and treat that path as the current repo root.
2. Use `$check-codex-tabs` scoped to the repo root to identify the current repo's non-archived Codex tabs and their status. Treat that skill as the source of truth for which tabs are still active versus already closed.
3. Keep only the tabs that `$check-codex-tabs` reports as closed but still unarchived. Exclude every tab it reports as active or otherwise in-flight. Do not let active tabs influence bucketing, staging, commit planning, or file ownership.
4. For each remaining closed tab, open the linked transcript and skim for gist rather than reading every token: prefer the main user asks, major assistant conclusions, and any clear feature names or bug labels. Use those closed tabs as one input into how the working tree should be bucketed.
5. Run `git status --short`, `git diff --stat`, `git diff --numstat`, and `git diff HEAD` to capture staged, unstaged, and untracked changes. Use stats first to understand size and shape, then inspect hunks selectively for intent.
6. Calculate changed lines as insertions plus deletions from `git diff --numstat` or `git diff --cached --shortstat`. Treat binary files as separate noted artifacts, not line-count evidence.
7. Group the work into however many buckets the changes genuinely call for. Do not aim for a target count just because the skill asked for one. One bucket is fine when the work is tightly coupled. There is no maximum bucket count; create as many buckets as needed for each bucket to tell one honest, reviewable story.
8. Let the closed tabs influence the split when they reflect genuinely separate streams of work, but do not overfit to thread boundaries when the code changes are tightly coupled and belong in one commit. If a change appears tied only to an active tab, leave it out of the characterized buckets and call out that it was intentionally left alone because it is still in flight.
9. For each bucket, provide:
   - a short label in kebab-case
   - the files that belong to it
   - the estimated changed-line count
   - a `3-5` sentence plain-English summary of what changed and why
   - one conventional-commit style message
10. If any changed files were intentionally left out because they appear to belong to active tabs, say so briefly after the bucket list.
11. If the user did not ask for `push`, stop after presenting the buckets.
12. If the user asked for `push`, run the workflow below for each bucket in order.

## Branch Safety

Branch handling must be explicit and conservative:

1. Before the first commit in push mode, run `git branch --show-current` and `git status --short --branch`.
2. The currently checked out branch is the commit target and the push target by default. Stay on that branch unless the user explicitly asks to create, switch to, or push a different branch.
3. Never create a new branch proactively for safety, cleanliness, reviewability, or personal preference. If the user is on `main`, then by default you commit on `main` and push `main`.
4. Never reinterpret ambiguous wording as branch permission. Phrases like "off main", "working off main", "based on main", or "from main" are ambiguous. Do not act on them silently. Restate the exact branch name using the words "on branch `<name>`" and "push `<name>`" before you commit.
5. In the first push-mode progress update, say exactly which branch you are on and exactly which branch you will push. Example: `I'm on branch main and will commit these buckets on main, then push main.`
6. If the user explicitly asks a branch question and there is any ambiguity, answer with the literal current branch name and your exact intended push target. Do not answer with loose phrasing like "working off main" or "off main".
7. If you realize you misread the user's branch intent before pushing, stop and ask instead of inventing a recovery path. Do not quietly move commits to another branch to be "safer".

## Resist Over-Splitting

The common failure mode is turning one feature into several fake buckets. Merge related edits when they share a feature name, a domain concept, or a clear dependency chain such as a route, helper, and test that only make sense together.

Do not split work just to make commits tiny. Commits in the `500` or `1000` line range are acceptable when the logic is closely tied and the resulting commit still tells one coherent story. In push mode, `2000` changed lines is the default maximum for a commit. Do not commit or push a bucket over `2000` changed lines unless it fits the narrow generated-file exception below.

Generated-file exception: a commit may exceed `2000` changed lines when the oversized portion is exactly one machine-managed file that is not user-authored code, such as `package-lock.json`, `pnpm-lock.yaml`, `yarn.lock`, `bun.lockb`, `poetry.lock`, `Cargo.lock`, a generated schema snapshot, or another generated artifact. Keep this exception tiny: the commit should contain only that generated file, or that generated file plus the smallest required companion manifest such as `package.json`. It must not include user-authored source, docs, tests, UI, migrations, or unrelated config changes. The commit message should name the generated/dependency artifact honestly.

When a bucket approaches or exceeds `2000` changed lines, actively look for honest split points before committing. Split by product surface, API route, data model, UI component, dependency churn, tests, or fallback behavior when those pieces can be understood or reverted separately. If a commit has to exceed `2000` changed lines under the generated-file exception, its summary must explicitly say which generated file accounts for the size.

Also resist making docs-only buckets by default. Markdown files, including `agent-docs/`, are usually supporting changes that belong with a feature or fix bucket rather than their own commit. If a docs change is feature-agnostic, fold it into the closest relevant bucket instead of creating a separate docs commit. Only split pure Markdown files into their own bucket in rare cases, such as when the user explicitly asked for docs-only work or the docs themselves are the primary deliverable.

## Output Format

For each bucket:

**[Bucket name]**
Label: `bucket-label`
[3-5 sentences describing what changed and why, written for someone who has not seen the diff.]
Files: `path/a.ts`, `path/b.ts`
Changed lines: `1234`
Commit: `feat(scope): short description`

After listing all buckets, end with one short sentence telling the user they can refer to a bucket by its label in the next prompt if they want help staging or committing it.

## Push Mode Workflow

Before the first commit, write a concise bucket plan that includes each bucket's label, files, estimated changed-line count, commit message, and any generated-file exception. In push mode, continue without waiting for approval unless a bucket violates the sizing or cohesion rules.

Create all commits locally first, then verify the whole stack before pushing:

1. Run `git branch --show-current` and `git status --short --branch`. State the exact current branch and exact push target in plain language before you stage anything.
2. Run `git restore --staged .` to clear the index.
3. Stage only that bucket's files with targeted `git add <path>` commands. Use `git add -p <path>` when only part of a file belongs to the bucket.
4. Run `git diff --cached --stat`, `git diff --cached --numstat`, and `git diff --cached --shortstat`. Confirm the staged files and changed-line count match one coherent bucket. If the staged diff is over `2000` changed lines and does not meet the generated-file exception above, stop and split the bucket before committing.
5. Commit with the bucket's suggested commit message.
6. Run `git show --stat --oneline HEAD` and confirm the commit title honestly describes the whole staged diff, not just the smallest or most recent fix inside it. If the title is misleading, amend before pushing.
7. Repeat steps 2-6 for every bucket. Do not push between buckets.
8. After all commits are created, run `git branch --show-current`, `git status --short`, `git log --oneline --stat <base>..HEAD`, and whatever validation commands are appropriate for the changed areas.
9. Confirm every commit still satisfies the `2000` line rule or generated-file exception, every title matches its diff, the working tree has no accidental leftovers, and the current branch still matches the branch you told the user you would push. If anything is wrong, fix the local commits before pushing.
10. Push once with `git push` to the branch you explicitly named earlier. Do not switch branches right before pushing unless the user explicitly asked for that branch change.
11. Report the branch pushed, commit hashes, validation result, and push result.

If any step fails, stop immediately and report the error. Do not continue to later buckets.

## Constraints

- Do not stage, commit, or push anything unless the user explicitly asked for `push`.
- Never use broad staging commands such as `git add .` or `git add -A`.
- Prefer coherent buckets over many tiny ones.
- Do not create, switch, or push a different branch unless the user explicitly asked for that branch behavior.
- Never include work from tabs that `$check-codex-tabs` reports as active or otherwise in flight.
