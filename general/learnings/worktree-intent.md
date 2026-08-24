# Worktree intent

- Infer the required starting state from the dispatched request, but default all repo work to the user's current checkout and current branch. Never create or switch a branch, create or remove a worktree, or detach `HEAD` without explicit user authorization for that exact operation.
- Workflows that inspect or push current dirty changes, such as `characterize push`, must use `working-tree` so uncommitted files remain in the current checkout. If the task tool cannot preserve that checkout, ask rather than selecting `main`, a detached state, or a new worktree.
- Verify the dispatched task's actual checkout path and branch immediately; stop on any mismatch.
