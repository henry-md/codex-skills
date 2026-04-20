---
name: characterize-codex
description: Reviews the git repo at `/Users/Henry/.codex/skills` (`~/.codex/skills`), groups its staged, unstaged, and untracked changes into coherent commit buckets, and automatically stages, commits, and pushes anything there that is not already pushed. Use when the user explicitly invokes `characterize-codex` to publish Codex skill changes from the skills repo rather than from the current working directory. This skill assumes `~/.codex/skills` has its own `.git` directory and may be invoked while the current chat is sitting in some other project.
---

# Characterize Codex

Use this skill to characterize and publish work in `/Users/Henry/.codex/skills`, not in the repo for the current chat.

`/Users/Henry/.codex/skills` is the intended target repo and it has its own `.git` directory. Treat that path as the only repo this skill may inspect, stage, commit, or push.

This skill will probably be invoked while the current working directory is some other project. That is expected. Navigate to `/Users/Henry/.codex/skills` first or use `git -C /Users/Henry/.codex/skills ...` for every git command. Never make commits in the caller's current directory unless that directory is already `/Users/Henry/.codex/skills`.

## Invocation Behavior

- Any explicit invocation of `characterize-codex` is permission to stage, commit, and push changes in `/Users/Henry/.codex/skills`.
- Do not ask for a second confirmation before committing or pushing. The command itself is permission enough.
- There is no separate `auto` mode. This skill is always auto.
- Work only inside the currently checked out branch of `/Users/Henry/.codex/skills`. Do not create or switch branches as part of this skill.
- If the skills repo already has local commits that are ahead of upstream, push them too.

## Fixed Repo Rule

1. Set the target repo to `/Users/Henry/.codex/skills`.
2. Run `git -C /Users/Henry/.codex/skills rev-parse --show-toplevel` and verify it resolves to exactly `/Users/Henry/.codex/skills`.
3. Run `git -C /Users/Henry/.codex/skills branch --show-current` and ensure the result is a normal branch name. Stop if the repo is missing or in detached HEAD.
4. Never run bare `git add`, `git commit`, or `git push` against the caller's current directory unless that directory is already `/Users/Henry/.codex/skills`.
5. Never characterize, stage, commit, or push the current project just because the user invoked this skill from there.

## What To Do

1. Run `git -C /Users/Henry/.codex/skills fetch --all --prune`.
2. Read Codex's local thread index before grouping changes. Use `~/.codex/state_5.sqlite` as the source of truth for unarchived chats and query the `threads` table for rows where `archived = 0` and `cwd = '/Users/Henry/.codex/skills'`, ordered by `updated_at_ms DESC`. Read the `title` and `rollout_path` columns from that query.
3. For each returned chat, open the JSONL transcript at `rollout_path` and skim for gist rather than reading every token. Prefer the main user asks, major assistant conclusions, and any clear skill names or workflow labels.
4. If `~/.codex/state_5.sqlite` is unavailable, fall back to `~/.codex/session_index.jsonl` for titles and `~/.codex/sessions/` for active transcript files, but still scope the search to `/Users/Henry/.codex/skills`.
5. Run `git -C /Users/Henry/.codex/skills status --short --branch`, `git -C /Users/Henry/.codex/skills diff HEAD`, and `git -C /Users/Henry/.codex/skills ls-files --others --exclude-standard`.
6. If the branch has an upstream, inspect what is already not pushed with `git -C /Users/Henry/.codex/skills log --oneline @{upstream}..HEAD`.
7. Group the uncommitted work into however many buckets the diff genuinely calls for. Use the skills-repo chats as one signal, not a quota.
8. For each bucket, write:
   - a short label in kebab-case
   - the files that belong to it
   - a short plain-English summary of what changed and why
   - one conventional-commit style message
9. Show the bucket plan briefly, then execute it immediately without waiting for another prompt.
10. If there are no uncommitted changes and no local commits ahead of upstream, say the skills repo is already fully pushed and stop.
11. If there are no uncommitted changes but the branch is ahead of upstream, skip straight to pushing the existing local commits.

## Bucketing Guidance

The common failure mode is over-splitting one skill change into too many commits. Prefer one bucket per skill or per tightly coupled workflow change.

Several edits inside one skill folder usually belong together, including `SKILL.md` and `agents/openai.yaml`. A new skill plus a small fix to some other existing skill usually deserves two buckets. Split work when the commit messages would naturally describe different user-visible changes, not just because the diff is large.

## Auto Publish Workflow

Process buckets one at a time in the order listed:

1. Run `git -C /Users/Henry/.codex/skills restore --staged .` to clear the index.
2. Stage only that bucket's files with targeted `git -C /Users/Henry/.codex/skills add <path>` commands. Use `git -C /Users/Henry/.codex/skills add -p <path>` when only part of a file belongs to the bucket.
3. Commit with the bucket's suggested commit message using `git -C /Users/Henry/.codex/skills commit -m "<message>"`.
4. Push the current branch with `git -C /Users/Henry/.codex/skills push`.
5. Report the commit hash and push result before moving to the next bucket.

After all new buckets are committed, if the branch is still ahead of upstream for any reason, push again so everything local that is not already pushed is published.

## Constraints

- Never make commits in the caller's current directory unless it is already `/Users/Henry/.codex/skills`.
- Never use broad staging commands such as `git add .` or `git add -A`.
- Never ask for permission to commit or push once this skill has been explicitly invoked.
- Never create or switch branches as part of this skill.
- Stop immediately on the first staging, commit, or push failure and report the blocker clearly.

## Output Format

For each bucket:

**[Bucket name]**
Label: `bucket-label`
[2-4 sentences describing what changed and why.]
Files: `path/a`, `path/b`
Commit: `feat(scope): short description`

After that, continue straight into execution updates and end with the commit hashes and push results.
