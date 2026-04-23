---
name: characterize-codex
description: Applies the `characterize` push workflow to the fixed git repo at `/Users/Henry/.codex/skills` (`~/.codex/skills`) so Codex skill changes are grouped into safe commit buckets, committed locally, verified as a stack, and pushed once. Use when the user explicitly invokes `characterize-codex` to publish Codex skill changes from the skills repo rather than from the current working directory.
---

# Characterize Codex

Publish changes from `/Users/Henry/.codex/skills`, regardless of the caller's current working directory.

This skill is a thin wrapper around `/Users/Henry/.codex/skills/characterize/SKILL.md`. Before grouping, staging, committing, or pushing, open that file and apply its `push` workflow as the source of truth for bucketing, changed-line accounting, the `2000` line rule, the generated-file exception, commit-message validation, stack verification, output format, and push-once behavior.

This skill only overrides the target repo, permission model, branch handling, and skills-repo-specific bucketing hints below. If shared workflow guidance here ever conflicts with `characterize`, follow `characterize`. If repo-safety guidance here conflicts with anything else, follow this skill.

## Invocation Behavior

- Any explicit invocation of `characterize-codex` is permission to run `characterize` in `push` mode for `/Users/Henry/.codex/skills`.
- Do not ask for a second confirmation before committing or pushing. The command itself is permission enough.
- Work only inside the currently checked out branch of `/Users/Henry/.codex/skills`. Do not create or switch branches as part of this skill.
- If the skills repo already has local commits ahead of upstream, include them in the final stack verification and push them too.

## Fixed Repo Rule

1. Set the target repo to `/Users/Henry/.codex/skills`.
2. Run `git -C /Users/Henry/.codex/skills rev-parse --show-toplevel` and verify it resolves to exactly `/Users/Henry/.codex/skills`.
3. Run `git -C /Users/Henry/.codex/skills branch --show-current` and ensure the result is a normal branch name. Stop if the repo is missing or in detached HEAD.
4. Use `git -C /Users/Henry/.codex/skills ...` for every git command unless the current shell is already in `/Users/Henry/.codex/skills`.
5. Never characterize, stage, commit, or push the caller's current project just because the user invoked this skill from there.

## What To Do

1. Open `/Users/Henry/.codex/skills/characterize/SKILL.md` and treat its `push` mode as the shared workflow to execute.
2. Run `git -C /Users/Henry/.codex/skills fetch --all --prune`.
3. Follow `characterize`'s discovery and bucketing process with `/Users/Henry/.codex/skills` as `<repo_root>`. When querying Codex's local thread index, use rows where `cwd = '/Users/Henry/.codex/skills'`.
4. Translate every git command from `characterize` to the target repo by adding `-C /Users/Henry/.codex/skills`.
5. Show the bucket plan, then execute it immediately using the `characterize` push workflow without waiting for another prompt.
6. If there are no uncommitted changes and no local commits ahead of upstream, say the skills repo is already fully pushed and stop.
7. If there are no uncommitted changes but the branch is ahead of upstream, skip local commit creation, run the final stack verification from `characterize`, then push once.

## Skills Repo Bucketing Hint

Prefer one bucket per skill or per tightly coupled workflow change. Edits inside one skill folder usually belong together, including `SKILL.md` and `agents/openai.yaml`, unless `characterize`'s sizing or cohesion rules require a split.

A new skill plus a small fix to an existing skill usually deserves separate buckets. Split work when commit messages would naturally describe different user-visible skill changes.

## Constraints

- Never make commits in the caller's current directory unless it is already `/Users/Henry/.codex/skills`.
- Never use broad staging commands such as `git add .` or `git add -A`.
- Never ask for permission to commit or push once this skill has been explicitly invoked.
- Never create or switch branches as part of this skill.
- Stop immediately on the first discovery, staging, commit, validation, or push failure and report the blocker clearly.
