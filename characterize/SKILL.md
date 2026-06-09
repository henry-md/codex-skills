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
4. For each remaining closed tab, open the linked transcript and skim for gist rather than reading every token: prefer the main user asks, the user's own phrasing for the work, recurring lines of questioning, major assistant conclusions, and any clear feature names or bug labels. Use those closed tabs as one input into how the working tree should be bucketed.
5. Run `git status --short`, `git diff --stat`, `git diff --numstat`, and `git diff HEAD` to capture staged, unstaged, and untracked changes. Use stats first to understand size and shape, then inspect hunks selectively for intent.
6. Calculate changed lines as insertions plus deletions from `git diff --numstat` or `git diff --cached --shortstat`. Treat binary files as separate noted artifacts, not line-count evidence.
7. Group the work into however many buckets the changes genuinely call for, with a bias toward smaller reviewable commits when there are honest split points. Prefer multiple medium buckets over one umbrella bucket when closed tabs, product surfaces, or diff seams support the split.
8. Let the closed tabs influence the split when they reflect genuinely separate streams of work, and treat them as strong candidate boundaries unless the code is clearly inseparable. Heavily group commits around the lines of questioning the user asked Codex for in those tabs: if the user repeatedly framed a topic, feature, bug, or investigation in a certain way, prefer that framing as the bucket boundary and the bucket language. If a change appears tied only to an active tab, leave it out of the characterized buckets and call out that it was intentionally left alone because it is still in flight.
9. For each bucket, provide:
   - a short label in kebab-case, using the user's own topic words when they are clear and commit-message-safe
   - the files that belong to it
   - a `1-4` sentence plain-English summary of what distinct feature, fix, or supporting change that commit includes, preferring `1-2` and staying concise; echo the user's language from the relevant closed tab when it describes the work accurately
   - one conventional-commit style message with the approximate changed-line count on the same line, preserving the user's terminology where it fits conventional-commit style
   - present it in the final answer as one top-level bullet whose first line is that commit message
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

## Bias Toward Smaller Reviewable Buckets

The common failure modes are under-splitting broad work into umbrella commits and over-splitting one tiny feature into fake micro-buckets. Merge related edits when they share a feature name, a domain concept, or a clear dependency chain such as a route, helper, and test that only make sense together.

When there are honest split points, prefer commits around `200-300` changed lines. Treat that range as the healthy default for user-authored work. Commits under `100` changed lines are fine when they are naturally small fixes, and commits in the `300-500` changed-line range are acceptable only when the code is tightly coupled and splitting would make review harder.

Treat `500` changed lines as a strong ceiling for user-authored commits, not a casual target. Once a bucket approaches `400` changed lines, actively look for cleaner splits by product surface, runtime versus UI, behavior versus presentation, tests versus implementation, API contract versus caller wiring, styling versus logic, or one closed-tab thread versus another. If a bucket would exceed `500` changed lines, split it before committing unless there is no defensible smaller boundary. In push mode, do not commit or push a user-authored bucket over `500` changed lines without first making and documenting a serious split attempt in the progress/update text.

The language of the buckets should feel like it came from the user's own Codex tabs, not from a generic code-review taxonomy. When closed tabs show the user asking a sequence of questions such as "why is X happening?", "make Y work", "clean up Z", or "push the A/B flow", use that line of questioning as a strong organizing principle for commit boundaries, labels, summaries, and commit messages. Prefer the user's nouns and verbs over invented names unless the user's wording is ambiguous, too long, or misleading for the actual diff.

Generated-file exception: a commit may exceed `500` changed lines when the oversized portion is exactly one machine-managed file that is not user-authored code, such as `package-lock.json`, `pnpm-lock.yaml`, `yarn.lock`, `bun.lockb`, `poetry.lock`, `Cargo.lock`, a generated schema snapshot, or another generated artifact. Keep this exception tiny: the commit should contain only that generated file, or that generated file plus the smallest required companion manifest such as `package.json`. It must not include user-authored source, docs, tests, UI, migrations, or unrelated config changes. The commit message should name the generated/dependency artifact honestly.

If a bucket lands between `400` and `500` changed lines, explicitly sanity-check whether it should be split before keeping it whole. If a user-authored bucket has to exceed `500` changed lines, its summary must explain why smaller reviewable boundaries were not defensible. If a commit exceeds `500` changed lines under the generated-file exception, its summary must explicitly say which generated file accounts for the size.

Also resist making docs-only buckets by default. Markdown files, including `agent-docs/`, are usually supporting changes that belong with a feature or fix bucket rather than their own commit. If a docs change is feature-agnostic, fold it into the closest relevant bucket instead of creating a separate docs commit. Only split pure Markdown files into their own bucket in rare cases, such as when the user explicitly asked for docs-only work or the docs themselves are the primary deliverable.

## Output Format

For each bucket, use a top-level bullet whose first line is the commit message:

- `feat(scope): short description` · `~1234 changed lines`
  Label: `bucket-label`
  Files: `path/a.ts`, `path/b.ts`
  [1-4 concise sentences describing what distinct feature, fix, or supporting change this commit includes, preferring 1-2.]

After listing all buckets, end with one short sentence telling the user they can refer to a bucket by its label in the next prompt if they want help staging or committing it.
In push mode, use the same `~1234 changed lines` notation in both the pre-commit bucket plan and the final pushed-commits report. Do not omit it.

## Push Mode Workflow

Before the first commit, write a concise bucket plan as a top-level bulleted list with one bullet per planned commit message, plus each bucket's label, files, concise `1-4` sentence explanation, and any generated-file exception. In push mode, continue without waiting for approval unless a bucket violates the sizing or cohesion rules.

Create all commits locally first, then verify the whole stack before pushing:

1. Run `git branch --show-current` and `git status --short --branch`. State the exact current branch and exact push target in plain language before you stage anything.
2. Run `git restore --staged .` to clear the index.
3. Stage only that bucket's files with targeted `git add <path>` commands. Use `git add -p <path>` when only part of a file belongs to the bucket.
4. Run `git diff --cached --stat`, `git diff --cached --numstat`, and `git diff --cached --shortstat`. Confirm the staged files and changed-line count match one coherent bucket. If the staged diff is over `500` changed lines and does not meet the generated-file exception above, stop and split the bucket before committing. For staged diffs between `400` and `500` changed lines, do one explicit split sanity-check before committing.
5. Commit with the bucket's suggested commit message.
6. Run `git show --stat --oneline HEAD` and confirm the commit title honestly describes the whole staged diff, not just the smallest or most recent fix inside it. If the title is misleading, amend before pushing.
7. Repeat steps 2-6 for every bucket. Do not push between buckets.
8. After all commits are created, run `git branch --show-current`, `git status --short`, `git log --oneline --stat <base>..HEAD`, and whatever validation commands are appropriate for the changed areas.
9. Confirm every commit still satisfies the `500` line rule or generated-file exception, every title matches its diff, the working tree has no accidental leftovers, and the current branch still matches the branch you told the user you would push. If anything is wrong, fix the local commits before pushing.
10. Push once with `git push` to the branch you explicitly named earlier. Do not switch branches right before pushing unless the user explicitly asked for that branch change.
11. Report the branch pushed, commit hashes, approximate changed-line count for each pushed commit, validation result, and push result.

If any step fails, stop immediately and report the error. Do not continue to later buckets.

## Constraints

- Do not stage, commit, or push anything unless the user explicitly asked for `push`.
- Never use broad staging commands such as `git add .` or `git add -A`.
- Prefer the smallest coherent buckets over umbrella commits, but do not invent fake micro-buckets.
- Do not create, switch, or push a different branch unless the user explicitly asked for that branch behavior.
- Never include work from tabs that `$check-codex-tabs` reports as active or otherwise in flight.

## Sample Output

```md
I'm on branch main and will commit these buckets on main, then push main.

Bucket plan:

- `fix(assistant): prefer a healthy local backend and trim env vars` · `~252 changed lines`
  Label: `assistant-backend-hardening`
  Files: `apps/extension/src/service-worker.js`, `apps/web/src/app/api/assistant/route.ts`
  Keeps the extension pointed at a healthy backend and trims env-derived values so local config works reliably.

- `fix(sidepanel): simplify chat chrome and restore rules on cancel` · `~41 changed lines`
  Label: `sidepanel-cleanup`
  Files: `apps/extension/src/sidepanel.css`, `apps/extension/src/sidepanel.js`
  Simplifies the chat chrome and sends Cancel back to the rules tab so the sidepanel stays tidy and predictable.

I left `apps/extension/pnpm-lock.yaml` out because it looks like stray local dependency artifact work rather than part of a closed bucket.

You can refer to a bucket by its label in the next prompt if you want help staging or committing it.

After pushing, report it like this:

Pushed `main` with:
- `3c021a4` `fix(assistant): prefer a healthy local backend and trim env vars` · `~252 changed lines`
  Keeps the extension pointed at a healthy backend and trims env-derived values so local config works reliably.
- `6546a20` `fix(sidepanel): simplify chat chrome and restore rules on cancel` · `~41 changed lines`
  Simplifies the chat chrome and sends Cancel back to the rules tab so the sidepanel stays tidy and predictable.

`npm run lint` passed, and `git push` updated `origin/main` from `abc1234` to `6546a20`.
```
