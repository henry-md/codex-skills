---
name: suggest-reflection
description: Audit local Codex Desktop tabs and suggest currently unarchived tabs where the code appears positively worth a /reflect refactor. Use when the user asks which Codex tabs, threads, or ongoing work might benefit from reflection, refactoring, architecture cleanup, decomposition, or a second pass on complex functionality. If invoked with the optional keyword `auto`, such as `/suggest-reflection auto` or `/suggestreflection auto`, run the suggestion workflow and then immediately perform the /reflect workflow for each suggested refactor without asking for additional permission.
---

# Suggest Reflection

## Purpose

Identify unarchived Codex tabs where `/reflect` looks positively worth running, especially tabs touching complex, tangled, or recently expanded code. Treat this as a suggestion workflow by default: gather tab evidence, inspect the relevant code when useful, then report only the systems where a refactor is likely to improve maintainability.

Do not present loose "candidates." A suggestion should mean: after transcript triage and code inspection, you believe there is a concrete code-quality problem and a plausible focused refactor path.

When invoked with `auto` as the optional second keyword, treat that keyword as the user's permission to continue past suggestions and run the `/reflect` workflow for each suggested refactor, one by one.

## Workflow

1. Decide the scope.
   - If the user names a repo or you are in a repo, prefer that repo unless they ask across all Codex tabs.
   - Resolve repo scope with `git rev-parse --show-toplevel` and pass the absolute path as `--cwd`.
   - If the user asks "all tabs" or similar, do not pass `--cwd`.

2. Run the helper script:

   ```bash
   python3 /Users/Henry/.codex/skills/suggest-reflection/scripts/suggest_reflection_candidates.py --cwd /absolute/repo/root
   ```

   Useful options:
   - `--limit N` to inspect more or fewer unarchived tabs.
   - `--json` when you want machine-readable output for follow-up parsing.
   - Omit `--cwd` to inspect all unarchived tabs.

3. Read the triage evidence.
   - Treat `archived = 0` as "currently active/open" for this skill, even when the last event is `done-open`.
   - Prefer tabs whose transcript signals complex implementation work, repeated bug-fix loops, architectural uncertainty, cross-cutting file changes, or large newly built systems.
   - Do not recommend tabs solely because they are open. A finished, narrow CSS tweak or one-file typo fix is usually not `/reflect` material.

4. Inspect code before suggesting.
   - For each plausible tab, open a few mentioned files or search by feature terms from the transcript.
   - Look for concrete refactor signals: duplicated logic, oversized components/functions, unclear ownership boundaries, tangled state/effects, ad hoc parsing, mixed UI/data concerns, brittle tests, or TODO-style follow-up comments.
   - Decide what is inefficient, fragile, or bad practice about the current code at a high level. Examples: one component owns too many responsibilities, similar geometry logic is duplicated, UI state and network persistence are coupled, parsing is ad hoc instead of centralized, or tests do not cover the brittle behavior.
   - If the code looks simple and cohesive after inspection, omit it even if the tab sounded complex.

5. Report a ranked suggestion list.
   Include only suggestions you believe are positively worth a refactor. For each suggestion include:
   - tab title and workspace `cwd`
   - status from the last transcript event, updated time, and transcript path when helpful
   - the high-level code-quality issue: what is inefficient, fragile, overly complex, or bad practice about the current implementation
   - why `/reflect` is likely to help, grounded in transcript and code evidence
   - specific files or system areas to point `/reflect` at
   - a confidence level: `high`, `medium`, or `low`

6. If `auto` was not given, stop after the suggestion list.

7. If `auto` was given, run the `/reflect` workflow for each suggested refactor, one by one.
   - Do not ask for extra permission before starting; `auto` is the permission.
   - Process suggestions in ranked order unless a clear dependency suggests otherwise.
   - Before each suggestion, briefly state which tab/system area you are reflecting on and the high-level code-quality problem you observed.
   - Use `/reflect`'s high bar. If reflection says no refactor is warranted, leave code unchanged and move to the next suggestion.
   - If a refactor is warranted, make only the focused cleanup for that suggestion, verify it, then continue.
   - Keep each suggestion's changes conceptually separate in your reporting so the user can see what happened where.

8. End with a brief "not recommended" note only when useful.
   Mention obvious open tabs you intentionally skipped when the reason matters, such as "narrow docs change" or "no code surface found".

## Recommendation Heuristics

Favor `/reflect` when one or more are true:
- The tab built or changed a feature spanning several modules.
- The transcript shows repeated attempts, reversions, or uncertainty about architecture.
- The code mixes domain logic, persistence, network calls, and UI/state in one place.
- A file or component appears central and has grown hard to reason about.
- The user asked for cleanup, refactoring, simplification, "make this sane", or similar language.
- There is a plausible path to reduce lines, duplication, branching, or future maintenance risk.
- You can state a specific code-quality problem in plain language. If the only reason is "this sounds complex," do not suggest it.

Avoid recommending `/reflect` when:
- The tab is archived, missing, or unrelated to the requested scope.
- The likely change is small, mechanical, docs-only, config-only, or already well factored.
- The transcript has no actionable code area and code inspection does not reveal one.
- The work is still mid-command or clearly blocked in a way `/reflect` would not help.

## Constraints

- Use local Codex state only; do not claim visual/frontmost tab knowledge.
- Keep the workflow read-only unless the user explicitly asks for code changes or invokes this skill with `auto`.
- Do not run `/reflect` in normal recommendation mode; only suggest where it may help.
- In `auto` mode, run `/reflect` only for suggestions you actually made. Do not refactor skipped or low-evidence tabs just because they are open.
- Do not overfit to script scores. Use them as triage hints, then apply engineering judgment.
