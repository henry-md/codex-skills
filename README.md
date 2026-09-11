# Personal Codex skills

This repository lives at `~/.codex/skills`. The directory
`~/Developer/codex-skills` is a symlink to it, so both paths open the same
working tree and Git history.

Add personal skills as real directories here, each with a `SKILL.md` file.
New personal skills can be reviewed and committed from either path.

Codex manages `.system/`; those installed files are ignored by this repository.
Tenex-managed skills remain symlinked to `~/.tenex/skills`. This Mac excludes
those links through `.git/info/exclude`, which is local Git configuration.
Keep those managed links out of personal skill commits.
