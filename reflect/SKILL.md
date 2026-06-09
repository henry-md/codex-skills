---
name: reflect
description: "Use when the user invokes /reflect or asks Codex to review recent complex feature work and decide whether a focused refactor is objectively worthwhile. This skill is a conservative post-implementation maintainability pass: inspect the chat context, changed code, and nearby architecture; recommend or apply cleanup only when it is likely to reduce lines of code, duplication, conceptual load, or future maintenance risk without changing behavior."
---

# Reflect

Run a conservative maintainability pass after one or more relatively complex features have reached a working version. The goal is to save the user from explaining this preference every time: look for objectively worthwhile cleanup, with a high threshold, and avoid refactors for their own sake.

## Workflow

1. Reconstruct what was just implemented.
   Read the current chat context, `git diff`, touched files, and nearby code. If the repo has local instructions such as `AGENTS.md` or `agent-docs`, read the relevant parts before judging code shape.

2. Name the working feature boundary.
   Identify what behavior now works, which files own it, which adjacent systems it touches, and what must remain unchanged.

3. Look for objective refactor opportunities.
   Favor cleanup that:
   - reduces lines of code without hiding behavior
   - removes duplicated logic, state, branches, or rendering paths
   - simplifies control flow, data flow, props, effects, or async handling
   - moves code into an existing local abstraction or convention
   - deletes dead/debug scaffolding or unnecessary compatibility layers
   - makes a future developer less likely to break the feature while editing it

4. Apply a high bar.
   Recommend a refactor only when all are true:
   - the current code works, but has a clear maintainability cost
   - the improvement is concrete, explainable, and not merely aesthetic
   - behavior can be preserved and verified
   - the change is small enough to review confidently
   - the likely result is less code, less duplication, less branching, or clearer ownership

5. Prefer no refactor over marginal churn.
   If the best cleanup idea is subjective, broad, risky, or would mostly move code around, say `No refactor recommended`. Name the future trigger that would justify revisiting it, such as another similar call site appearing or a file growing past a reasonable size.

6. If acting, keep edits focused.
   Do not combine reflection with new feature work. Preserve the working behavior. Use existing project patterns over new abstractions unless the new shape is plainly smaller and clearer.

7. Verify any edit.
   Run the relevant lint, tests, build, or UI checks for changed code. If no refactor is made, validation is optional unless inspection reveals a possible bug.

## Output

Lead with one of:
- `No refactor recommended`
- `Refactor recommended`
- `Refactor applied`

Then include:
- files or components inspected
- strongest cleanup candidates considered
- why each candidate passed or failed the high bar
- validation performed, if code changed

Keep the answer concise. The value of this skill is disciplined judgment, not a long architecture essay.
