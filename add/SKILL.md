---
name: add
description: Stage only the current chat's relevant changes while leaving unrelated work in the tree untouched. Use when the user explicitly invokes the add skill to rebuild the staged set from this conversation only, including earlier messages in the same chat. By default it suggests a commit message without committing or pushing, and `/add push` additionally commits and pushes the staged result.
---

# Add

Use this skill when the user wants the current chat's relevant changes staged while leaving unrelated work in the tree untouched.

Treat the scope as everything discussed in the full chat history, not just the most recent message. In most cases, that scope should map to one cohesive set of changes.

Invocation modes:

- `/add`: Clear any pre-existing staged changes, then rebuild the staged set for this chat and suggest a commit message.
- `/add push`: Do the same surgical staging work, then use the suggested commit message as the actual commit message, commit the staged changes, and push that commit.

## What to do

- First clear any pre-existing staged changes so the index is rebuilt only from this chat's scope.
- Stage files that are fully part of this chat with targeted `git add <path>` commands.
- For files that contain both relevant and unrelated edits, stage only the relevant blocks with `git add -p <path>`.
- Finish by producing one commit message that describes only the changes staged by this skill and matches the repository's existing commit style.
- When invoked as `/add push`, use that commit message for the real commit and then push it.

## Workflow

1. First run `git restore --staged .` so any previously staged work is removed before rebuilding the index for this chat.
2. Use the current chat context and the files changed in this task to decide what belongs in scope.
3. For a file where every unstaged change is part of this chat, run `git add <path>`.
4. For a file where only some hunks belong to this chat, run `git add -p <path>` and stage only the relevant hunks.
5. If a hunk mixes relevant and unrelated edits, split it and stage only the blocks that belong to this chat.
6. If the relevant logic cannot be isolated safely with `git add -p`, stop and tell the user instead of staging too much.
7. Write one commit message for only the staged changes, using conventions such as `feat(scope): ...`, `fix(scope): ...`, `test(scope): ...`, or `feat: ...`.
8. If the invocation is plain `/add`, stop after staging and suggest that commit message in the final response.
9. If the invocation is `/add push`, commit only the staged changes with that message and then push the current branch.

## Constraints

- Always clear the staged set first with `git restore --staged .` before staging anything for this skill.
- After that initial unstage step, use only `git add <path>` and `git add -p <path>` to rebuild the staged set for this chat.
- Never use broad staging such as `git add .`, `git add -A`, or directory-wide adds that could scoop up unrelated work.
- Do not stage changes from earlier or parallel work that are not part of the current chat.
- Be especially careful with partially related files: stage only the relevant blocks, never the whole file by default.
- Unless the user explicitly invoked `/add push`, do not commit anything and do not push anything.
- In `/add push` mode, commit only the surgically staged changes and push only that commit.
