---
name: branch
description: Create a dedicated Git working branch and make it the durable branch requirement for every coding agent in a project. Use when the user invokes /branch or asks to start, switch to, or enforce a named branch across Codex, Claude, Cursor, or other agent sessions. Require an explicit decision before moving any existing worktree changes onto the new branch.
---

# Branch

Create a named local branch, make the current project directory use it, and persist that requirement in every active agent-instruction entrypoint. Treat `main` as cleanup mode: switch to it and remove this skill's managed instructions. Treat this as branch setup, not permission to commit the user's work.

## Inputs and preflight

1. Require one branch name. Use it exactly as supplied; let Git reject invalid names rather than silently rewriting it.
2. Run `git rev-parse --show-toplevel`. Stop if the directory is not a Git worktree.
3. Record the current branch with `git branch --show-current`. If HEAD is detached, ask the user which branch should retain any existing work before proceeding.
4. If the requested branch is `main`, require that local `main` exists and use cleanup mode. Otherwise, check whether the requested local branch already exists; if it does, stop and ask whether to switch to it or use a different name; do not silently reuse it as a “new” branch.
5. Inspect the complete worktree with `git status --short`, including staged, unstaged, and untracked files. Treat any output as a dirty worktree.

## Dirty-worktree decision

If the worktree is dirty, do not create or switch branches yet. Ask exactly this decision in clear terms and wait for an unambiguous answer:

> The worktree has staged, unstaged, or untracked changes. Should **all** of these changes go with branch `<branch>`? Reply `yes` to move them to that branch, or `no` to preserve them on the current branch in a separate worktree.

Do not infer an answer from context, and do not discard, commit, reset, or partially select the changes. A `no` must preserve every change; a `yes` means preserve every change on the requested branch, still without committing the user's changes.

## Switch branches and update the instructions

Use a temporary stash only to keep the branch-rule commit separate from user changes. Include untracked files. Never drop a stash after a conflict.

Use `git switch -c <branch>` for a requested non-main branch. Use `git switch main` for requested `main`; never create a new `main` branch.

### Clean worktree

1. Switch to the requested target.
2. Update or remove the agent-entrypoint instructions as described below, and commit only those edits.

### User answered yes

1. Run `git stash push --include-untracked -m "branch-skill: carry work to <branch>"`.
2. Switch to the requested target.
3. Update or remove the agent-entrypoint instructions and commit only those edits.
4. Run `git stash pop` to restore all original worktree changes on `<branch>`.
5. If the pop conflicts, leave the stash intact, stop, and report the conflicts. Do not claim the user's changes were restored until they are.

### User answered no

1. Run `git stash push --include-untracked -m "branch-skill: preserve work on <old-branch>"`.
2. Switch to the requested target.
3. Update or remove the agent-entrypoint instructions and commit only those edits.
4. Create a sibling worktree on the original branch at a clear, unused path such as `<repo-parent>/<repo-name>-<old-branch>-wip`: `git worktree add <path> <old-branch>`.
5. Run `git -C <path> stash pop` to restore the saved work there.
6. If the pop conflicts, leave the stash intact, stop, and give the user the worktree path and conflict status. Otherwise, keep the current project directory on `<branch>` and report where the preserved work lives.

## Agent entrypoints

Find all existing, repository-owned agent instruction files. Always include root `AGENTS.md`, `CLAUDE.md`, and `.cursor/agents.md` when they exist; also include established equivalents such as `GEMINI.md`, `.cursorrules`, `.windsurfrules`, and `.github/copilot-instructions.md`, plus nested instruction files that apply to a project subtree. Exclude `.git`, dependencies, build output, and vendored/generated directories. Do not create inactive tool configuration files merely to add this rule.

For a non-main branch, create root `AGENTS.md` with the rule only if the project has no agent instruction file. For requested `main`, never create an entrypoint during cleanup.

For a non-main branch, add or replace the following managed block near the beginning of every selected entrypoint. Preserve all unrelated content:

```markdown
**BRANCHES: For all user requests, work off branch <branch>.**
**Refuse to edit on a non-main branch while the `main` worktree has uncommitted changes, and refuse to edit on `main` while any non-main branch worktree has uncommitted changes.**
**Ask the user how to resolve this state before proceeding.**
```

Replace existing managed branch rules rather than duplicating them. For requested `main`, remove this exact three-line managed block from every selected entrypoint instead of adding or replacing it; remove an otherwise-empty file only when it was created solely by this skill. Stage and commit only these entrypoint edits, using `chore: set working branch to <branch>` for a non-main branch or `chore: clear working branch requirement` for `main`. If a clean, isolated commit cannot be made, stop and explain why; never absorb the user's changes into it.

## Verify and hand off

Before finishing, verify all of the following:

1. `git branch --show-current` reports `<branch>` in the current project directory.
2. For a non-main branch, every selected entrypoint contains all three managed branch instructions with `<branch>`; for `main`, none contains the managed block.
3. If entrypoint edits were needed, the instruction-update commit contains only those edits.
4. For a dirty worktree, the user's changes are either restored on `<branch>` after `yes`, or restored in the reported sibling worktree on `<old-branch>` after `no`.

Report the active branch, the entrypoint files changed, the configuration commit, and—when applicable—the location or status of preserved user changes.
