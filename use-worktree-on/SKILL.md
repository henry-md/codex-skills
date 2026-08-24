---
name: use-worktree-on
description: Use when the user invokes `/use-worktree-on branch-name` or asks Codex to work from the existing worktree for a specific branch. Resolve the already-created git worktree that is checked out on that branch, use that worktree as the working directory for all subsequent repo work, and do not switch the main checkout to that branch or create another worktree.
---

# Use Worktree On

Treat this skill as shorthand for:

> Work off the existing worktree that is already on branch X. Do not switch the main repo checkout to X, and do not create another worktree.

## Workflow

1. Parse the branch name from the token after `/use-worktree-on`.
   - Example: `/use-worktree-on new-style-1` means branch `new-style-1`.
   - If no branch name is provided, ask the user for the branch before editing.

2. From the current repo or any known checkout of the repo, inspect existing worktrees:

   ```bash
   git worktree list --porcelain
   ```

3. Find a worktree whose `branch` entry is exactly `refs/heads/<branch>`.
   - Use that worktree path as the repo root for this task.
   - Before editing, confirm with `pwd`, `git branch --show-current`, and `git status --short`.
   - Set every subsequent shell command, file read, file edit, test, and git command to use that worktree path as `workdir`.

4. Do not run `git switch <branch>`, `git checkout <branch>`, or `git worktree add` to satisfy this skill.
   - If no existing worktree is already on the requested branch, stop and tell the user.
   - If more than one existing worktree is on the requested branch, stop and ask which path to use.
   - Do not remove, prune, or delete worktrees unless the user explicitly asks for cleanup.

5. In the first user-facing update after resolving the path, state the exact worktree path being used.
