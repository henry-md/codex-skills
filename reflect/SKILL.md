---
name: reflect
description: "Use when the user invokes /reflect or asks Codex to review recent complex feature work and decide whether a focused refactor is objectively worthwhile. This skill is a conservative post-implementation maintainability pass: inspect the chat context, changed code, and nearby architecture; recommend or apply cleanup only when it is likely to reduce lines of code, duplication, conceptual load, or future maintenance risk without changing behavior. Put special pressure on deleting unnecessary code, plumbing, branches, adapters, and scaffolding that were useful during bug fixes or earlier iterations but are no longer needed after the logic settled somewhere else. When recommending cleanup, also name the regression tests or $checks workflow coverage needed to prove touched functionality still works."
---

# Reflect

Run a conservative maintainability pass after one or more relatively complex features have reached a working version. The goal is to save the user from explaining this preference every time: look for objectively worthwhile cleanup, with a high threshold, and avoid refactors for their own sake.

An important part of this pass is subtraction. Complex work often leaves behind extra plumbing, compatibility paths, intermediate state, helper layers, or defensive branches that made sense during bug fixes or earlier iterations, but became unnecessary once the final logic moved in another direction. Actively look for that residue and prefer deleting it when behavior is already covered by the settled path.

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
   - removes leftover plumbing, adapters, temporary state, feature flags, or branching created during earlier iterations
   - collapses obsolete bug-fix paths once the final logic makes them redundant
   - makes a future developer less likely to break the feature while editing it

4. Apply a high bar.
   Recommend a refactor only when all are true:
   - the current code works, but has a clear maintainability cost
   - the improvement is concrete, explainable, and not merely aesthetic
   - behavior can be preserved and verified
   - the change is small enough to review confidently
   - the likely result is less code, less duplication, less branching, or clearer ownership
   - deleted plumbing is provably no longer part of the active behavior, not merely unfamiliar

5. Prefer no refactor over marginal churn.
   If the best cleanup idea is subjective, broad, risky, or would mostly move code around, say `No refactor recommended`. Name the future trigger that would justify revisiting it, such as another similar call site appearing or a file growing past a reasonable size.

6. Pair recommended edits with regression coverage.
   When recommending cleanup, also identify:
   - the core functionality and user flows the edits would touch
   - the specific regression tests, browser routes, states, or workflows that should be checked afterward
   - what should be verified with the `$checks` workflow so the refactor does not regress behavior

7. If acting, keep edits focused.
   Do not combine reflection with new feature work. Preserve the working behavior. Use existing project patterns over new abstractions unless the new shape is plainly smaller and clearer.

8. Verify any edit.
   Run the relevant lint, tests, build, or UI checks for changed code. If no refactor is made, validation is optional unless inspection reveals a possible bug.
   If the user gives the go-ahead with `auto` or explicitly asks Codex to apply the recommended refactor, the job is not done until the functionality named in step 6 has been verified with the `$checks` workflow, unless a real blocker prevents it.

## Output

Lead with one of:
- `No refactor recommended`
- `Refactor recommended`
- `Refactor applied`

Then include:
- files or components inspected
- strongest cleanup candidates considered
- why each candidate passed or failed the high bar
- regression coverage suggested for each recommended or applied refactor
- validation performed, if code changed

Keep the answer concise. The value of this skill is disciplined judgment, not a long architecture essay.
