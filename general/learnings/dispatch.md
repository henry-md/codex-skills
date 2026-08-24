# Dispatch logistics

- A successful `create_thread` response only confirms creation. Verify the task with `read_thread` before saying it started.
- The project-task payload is nested: `target: { type: "project", projectId, environment: { type: "worktree", startingState: ... } }`. `projectId` and `type` are not top-level fields.
- When creation returns a `clientThreadId`, setup is still in progress. Never pass that opaque client ID to `read_thread`; resolve the real ID through `list_threads` after a brief wait, then read it once.
- A task in `systemError` did not run. Create a fresh replacement after correcting the rejected model/reasoning setting; a follow-up message may not recover it.
- The current thread-creation API can select a model and reasoning effort but may not expose a Fast-mode setting. Do not claim Fast mode was configured without an explicit control.
- General-level delegation must use user-visible Codex tasks, not temporary subagents. Use a task's own subagents only after the work is inside that visible task.
- Never create a branch or worktree implicitly. Default repo-scoped tasks to the current checkout and current branch. Require explicit authorization for any branch/worktree creation, switching, detaching, or removal, with the exact target named by the user.
- Requests whose job is to characterize or push current uncommitted changes require the current checkout; use `startingState: { type: "working-tree" }` and preserve its current branch. Never silently start from a clean `main` worktree or detached checkout.
- Prefer a completed feature task for a later bug fix to preserve implementation context. Do not interrupt an active task for unrelated work.
- For one continuous visual or code artifact, never assign multiple parallel tasks as writers to different apparent segments of the same shared implementation. Use one integration owner and make segment tasks audit-only; require a settled whole-artifact verification after all local checks.
- If a thread-tool call rejects its arguments, correct the documented payload once and retry; do not make several speculative calls or search the filesystem while the user waits.
