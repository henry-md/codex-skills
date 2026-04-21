---
name: doctor
description: Review an existing Codex skill for structure, verbosity, triggering quality, and overall fit with Codex skill best practices. Use when the user explicitly invokes `/doctor` with an existing skill name, or otherwise asks for a serious skill health check before rewriting a skill. This skill is review-only on the first pass and requires explicit follow-up consent before editing any files.
---

# Doctor

## Overview

Use this skill to decide whether an existing skill actually needs a rework.
Understand the skill deeply first, then surface only meaningful structural or verbosity problems instead of nitpicking wording.

## Resolve The Target

- Treat the second argument after `/doctor` as the name of an existing skill.
- Resolve the target skill before reviewing it.
- Prefer the user-provided path when available.
- Otherwise search the normal skills locations that are relevant to the current environment, such as `$CODEX_HOME/skills`, `~/.codex/skills`, and bundled system skills if needed.
- If the skill cannot be found, stop and tell the user.
- If multiple plausible matches exist, stop and ask the user which one to review.

## Review Workflow

1. Understand the skill before judging its markdown.
   Read `SKILL.md` first.
   Read `agents/openai.yaml` if it exists.
   Read scripts, references, or other bundled files only when they are needed to understand how the skill actually works.
2. Judge the skill against Codex skill best practices.
   Check the trigger description, structure, progressive disclosure, resource usage, and whether the instructions are actually useful to another Codex instance.
3. Look for meaningful problems.
   Focus on bad structure, buried instructions, weak or misleading frontmatter, stale companion metadata, duplication, contradictions, missing guidance, and verbosity that adds token cost without adding execution value.
4. Treat verbosity as a real issue when it is real.
   Call out bloated sections, repeated explanations, or content that belongs in references or scripts instead of `SKILL.md`.
5. Avoid low-value critique.
   Do not nitpick tone, tiny wording choices, or cosmetic edits when the skill is already structurally sound.
   Do not invent rewrite work just to have something to say.

## Review Standard

- Prefer a small number of high-leverage findings over a long punch list.
- Say explicitly when the skill is healthy and does not need a rewrite.
- If changes are warranted, distinguish between:
  - targeted cleanup
  - deeper rewrite
- Explain why the rewrite would materially improve the skill instead of merely changing the wording.

## Response Shape

- Summarize the overall verdict first.
- Then list the highest-value findings, ordered by impact.
- Include concrete examples of what is wrong when needed, but keep the review concise.
- End by saying you can make the changes if the user wants.
- If no substantial problems are found, say so clearly and do not pad the answer.

## Consent Rule

- Treat `/doctor` as review-only.
- Never edit a skill during the initial `/doctor` response.
- Treat the `/doctor` invocation itself as insufficient consent to edit.
- Only edit after the user explicitly approves a follow-up rewrite.
- If the user approves the edits, then update the relevant skill files and validate the result.
