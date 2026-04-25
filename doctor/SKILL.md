---
name: doctor
description: Review a codebase and suggest high-leverage refactors that improve modularity, reduce multiple sources of truth, and clarify ownership boundaries. Use when the user explicitly invokes `/doctor`, or asks for a code health review, architecture cleanup pass, oversized-file audit, modularization suggestions, duplicated-logic review, or help identifying shared functionality that should be centralized. This skill is review-only on the first pass and should recommend incremental, behavior-preserving refactors rather than rewrites.
---

# Doctor

## Overview

Use this skill to inspect a codebase and surface the most valuable refactor opportunities.
Prioritize changes that reduce bugs, simplify future edits, and make ownership boundaries clearer.

## Review Workflow

1. Build context before judging structure.
   Inspect the repo layout, identify the largest and highest-churn areas you need to understand, and read the files that appear central to the user's request.
   Treat files over 1000 lines as strong signals to inspect, not as automatic split candidates.
2. Look for high-leverage refactors.
   Focus on problems that meaningfully improve maintainability, correctness, or changeability when fixed.
3. Prefer refactors that reduce drift.
   Prioritize multiple sources of truth, duplicated business logic, duplicated schemas or types, inconsistent transforms, and duplicated state over cosmetic cleanup.
4. Recommend the smallest change that solves the underlying issue.
   Prefer incremental, behavior-preserving refactors over rewrites.
5. Stay selective.
   Prefer a short list of high-confidence suggestions over a long list of speculative nits.

## What To Look For

- Files that mix too many responsibilities, even when they are below 1000 lines.
- Files over 1000 lines whose size appears to come from mixed concerns rather than one cohesive responsibility.
- Duplicate business logic across routes, services, hooks, utilities, components, or background jobs.
- Duplicate types, schemas, constants, parsing logic, validation logic, or transformation logic that should come from one shared definition.
- Inconsistent data models or data-shaping logic across layers.
- UI components that contain domain logic or workflow logic that should live in shared helpers or server-side modules.
- Server/client boundary problems such as duplicated fetching, duplicated auth or session handling, or the same business rule enforced in multiple layers without a shared source.
- Tight coupling between modules that makes reuse, testing, or safe edits harder.
- Hidden dependencies or implicit contracts between files that should become explicit interfaces or shared modules.
- Repeated branching or policy logic that should be centralized.
- Repeated configuration, magic strings, or copied lookup tables that should become shared constants or helpers.
- State that is duplicated in multiple places and can drift out of sync.
- Dead code, stale abstractions, wrappers that no longer buy clarity, or utility files that have become catch-alls.
- Refactors that would materially improve testability, not just readability.

## Heuristics

- Treat `>1000` lines as a signal to investigate cohesion, not as a mandatory split threshold.
- Prioritize multiple sources of truth above pure modularization.
- Prioritize refactors that reduce future bugs or unblock future edits.
- Prefer extracting shared domain logic before extracting presentational helpers.
- Prefer introducing a shared type, schema, interface, or transform before moving large amounts of code around when drift is the core problem.
- Prefer clearer ownership boundaries so each module has one obvious reason to change.

## Guardrails

- Ignore generated files, vendored code, build artifacts, lockfiles, and migrations unless the user explicitly asks for them.
- Do not recommend splitting a file purely because it is large if the file is still cohesive.
- Do not suggest abstractions only to remove tiny duplication when the result would be harder to read.
- Do not recommend product changes when a behavior-preserving refactor is the real need.
- Do not pad the review with low-value style feedback.

## Response Shape

- Start with the overall verdict.
- Then list the highest-priority refactor suggestions in impact order.
- For each suggestion, include:
  - the problem
  - why it matters
  - the recommended refactor direction
  - rough scope or risk
  - whether it should happen now, later, or only when touching that area
  - concrete file references
- If the codebase looks healthy, say so clearly and do not invent work.

## Consent Rule

- Treat `/doctor` as review-only on the first pass.
- Do not edit files during the initial `/doctor` response.
- Only refactor after the user explicitly asks for implementation help on a chosen suggestion.
