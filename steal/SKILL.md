---
name: steal
description: Keep Claude and Codex skills in feature parity by comparing `~/.claude/skills` and `~/.codex/skills`, finding missing skills on either side, and reconciling functionality gaps inside matching `SKILL.md` files. Treat matching Codex built-ins such as `skill-creator` as satisfying the Codex side so duplicate custom Codex files are not created. Use when the user wants to sync custom commands across Claude and Codex, mirror one or more named skills between them, or close behavior gaps without copying the entire built-in Codex catalog into Claude.
---

# Steal

Keep Claude and Codex skills in parity.

## Scope

- If the user names one or more skills, normalize those names to kebab-case and sync only that set.
- If the user does not name specific skills, sync the default parity set:
  - every skill under `~/.claude/skills`
  - every top-level custom skill under `~/.codex/skills`
  - a small allowlist of Codex built-ins that should count as user-facing parity targets. Start with `skill-creator`.
- Ignore `steal` during the default full scan unless the user explicitly asks for `steal`.
- Do not mirror the entire Codex built-in or plugin skill catalog into Claude unless the user explicitly asks.

## First Step

Run:

```bash
python3 "$HOME/.codex/skills/steal/scripts/list_missing_codex_skills.py"
```

If the user named specific skills, pass those names to the script.

Read the report as follows:

- `missing_in_codex`: create Codex skill files from Claude sources
- `missing_in_claude`: create Claude skill files from Codex sources
- `present_in_both`: compare the actual skill docs on both sides and reconcile any capability gaps
- `not_found_anywhere`: tell the user

Do not stop just because skill names match. If both missing lists are empty, continue by reviewing every `present_in_both` skill in scope. Only stop early when there are no missing skills and the docs already match in functionality.

## For Each Skill Missing In Codex

1. Read the source Claude `SKILL.md`.
2. Create the target Codex skill with:
   ```bash
   python3 "$HOME/.codex/skills/.system/skill-creator/scripts/init_skill.py" "<skill-name>" --path "$HOME/.codex/skills"
   ```
3. Rewrite the generated Codex `SKILL.md` using heavy inspiration from the Claude skill, but adapt it instead of copying it verbatim.
4. Preserve the original job, workflow, and constraints while translating Claude-specific concepts into Codex-appropriate ones.
5. Keep Codex frontmatter limited to:
   ```yaml
   ---
   name: <skill-name>
   description: <what it does and when to use it>
   ---
   ```
6. Refresh `agents/openai.yaml` so the Codex UI metadata stays in sync with the new or updated skill behavior.
7. If the target Codex installation maintains any aggregate skills markdown or other checked-in skill index outside the skill folder, update that aggregate doc too instead of assuming the new folder is enough. In this Codex setup, the concrete files you can rely on are the skill folder itself and `agents/openai.yaml`; other aggregate skill docs may be installation-specific.
8. Validate the new skill with:
   ```bash
   python3 "$HOME/.codex/skills/.system/skill-creator/scripts/quick_validate.py" "$HOME/.codex/skills/<skill-name>"
   ```
9. If validation cannot run because local Python dependencies are missing, say so and do a manual frontmatter sanity check instead of pretending validation passed.
10. Remind the user that Codex may need a restart before the new skill is picked up.

## For Each Skill Missing In Claude

1. Read the source Codex `SKILL.md`.
2. Create `~/.claude/skills/<skill-name>/SKILL.md`.
3. Rewrite it using heavy inspiration from the Codex skill, but adapt it instead of copying it verbatim.
4. Preserve the original job, workflow, and constraints while translating Codex-specific concepts into Claude slash-command language.
5. Use Claude frontmatter like:
   ```yaml
   ---
   name: <skill-name>
   description: <what it does and when to use it>
   argument-hint: [optional]
   ---
   ```
6. Only add `argument-hint` when the command clearly benefits from a visible argument shape.

## For Each Skill Present In Both

1. Read both platform versions of `SKILL.md` before deciding the skill is already in parity.
2. Compare actual functionality, not just the skill name. Check supported arguments, optional parameters, workflow steps, validation, safety constraints, bundled scripts or references mentioned in the docs, and any examples that imply extra capabilities.
3. Treat clearly stronger or more complete behavior as the baseline. If one side supports an additive improvement such as an optional parameter, stronger safeguards, or a more complete workflow, update the lagging side so both skills support it.
4. Preserve platform-specific syntax while syncing behavior. For example, Claude can use `$ARGUMENTS` and `argument-hint`, while Codex can use `agents/openai.yaml`.
5. If a difference looks like a tradeoff and it is not obvious which version is superior, stop and ask the user which version should become the shared baseline before overwriting either side.
6. When you update the Codex side, refresh `agents/openai.yaml` if the UI metadata now lags behind the skill behavior.
7. If the target Codex installation uses an aggregate skills markdown or similar checked-in index outside the skill folder, update that index too when you change the Codex skill.
8. After the edits, both skills should describe equivalent functionality modulo platform conventions.

## Translation Rules

- Match capability, not wording.
- A matching skill name is only the start of the review, not proof that no work is needed.
- Prefer concise imperative instructions.
- Keep descriptions explicit enough to trigger well on their home platform.
- Remove Claude-only frontmatter fields when syncing to Codex.
- Add Claude-specific details such as `$ARGUMENTS` and `argument-hint` only when they are truly helpful.
- When one side has clearly more advanced functionality, propagate that improvement to the other side instead of flattening both to the weaker version.
- Do not ask the user to choose when one version is plainly more complete, safer, or more ergonomic. Ask only when the better baseline is genuinely unclear.
- Treat allowlisted Codex built-ins such as `skill-creator` as satisfying the Codex side so duplicate custom Codex files are not created.
- Do not overwrite an existing skill blindly. For skills present on both sides, update only the lagging side after you compare the docs and identify the stronger baseline.
- Do not assume Codex skill creation ends at `SKILL.md`. Keep `agents/openai.yaml` in sync, and if that Codex installation has a separate aggregate skills markdown or index, update it too.
- If one side already has a clearly equivalent command under a different name, stop and tell the user instead of creating a duplicate.

## Final Response

End with a compact summary:

- List each skill you created in Codex.
- List each skill you created in Claude.
- List each skill you updated in Codex to catch it up with Claude.
- List each skill you updated in Claude to catch it up with Codex.
- Mention any skills you skipped because they were already in parity, were already satisfied by a Codex built-in, looked like near-duplicates, or need a user decision before choosing a baseline.
