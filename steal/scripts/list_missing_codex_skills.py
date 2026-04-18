#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


CLAUDE_ROOT = Path.home() / ".claude" / "skills"
CODEX_ROOT = Path.home() / ".codex" / "skills"
CODEX_BUILTIN_PARITY_NAMES = {"skill-creator"}


def normalize(name: str) -> str:
    name = name.strip()
    if name.startswith("/"):
        name = name[1:]
    name = name.lower()
    name = re.sub(r"[^a-z0-9]+", "-", name)
    name = re.sub(r"-{2,}", "-", name).strip("-")
    return name


def collect_skill_map(root: Path) -> dict[str, list[Path]]:
    skill_map: dict[str, list[Path]] = {}
    if not root.exists():
        return skill_map

    for skill_md in root.rglob("SKILL.md"):
        skill_map.setdefault(skill_md.parent.name, []).append(skill_md)

    return {
        name: sorted(paths, key=lambda path: str(path))
        for name, paths in sorted(skill_map.items())
    }


def split_codex_paths(paths: list[Path]) -> tuple[list[Path], list[Path]]:
    custom_paths: list[Path] = []
    builtin_paths: list[Path] = []

    for path in paths:
        if path.parent.parent == CODEX_ROOT:
            custom_paths.append(path)
        else:
            builtin_paths.append(path)

    return custom_paths, builtin_paths


def build_default_candidates(
    claude_skills: dict[str, list[Path]], codex_skills: dict[str, list[Path]]
) -> tuple[list[str], list[str]]:
    candidate_names = {name for name in claude_skills if name != "steal"}
    ignored_codex_only_builtins: list[str] = []

    for name, paths in codex_skills.items():
        if name == "steal":
            continue

        custom_paths, builtin_paths = split_codex_paths(paths)
        if custom_paths or name in CODEX_BUILTIN_PARITY_NAMES:
            candidate_names.add(name)
        elif builtin_paths and name not in claude_skills:
            ignored_codex_only_builtins.append(name)

    return sorted(candidate_names), sorted(ignored_codex_only_builtins)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Report skill parity gaps between Claude and Codex."
    )
    parser.add_argument(
        "skills",
        nargs="*",
        help="Optional skill names to limit the comparison. Accepts names like /foo or Foo Bar.",
    )
    args = parser.parse_args()

    claude_skills = collect_skill_map(CLAUDE_ROOT)
    codex_skills = collect_skill_map(CODEX_ROOT)

    requested = [normalize(skill) for skill in args.skills]
    requested = [skill for skill in requested if skill]

    if requested:
        candidate_names = sorted(
            {
                skill
                for skill in requested
                if skill in claude_skills or skill in codex_skills
            }
        )
        ignored_codex_only_builtins: list[str] = []
        not_found_anywhere = sorted(
            {
                skill
                for skill in requested
                if skill not in claude_skills and skill not in codex_skills
            }
        )
    else:
        candidate_names, ignored_codex_only_builtins = build_default_candidates(
            claude_skills, codex_skills
        )
        not_found_anywhere = []

    missing_in_codex = []
    missing_in_claude = []
    present_in_both = []

    for name in candidate_names:
        claude_paths = claude_skills.get(name, [])
        codex_paths = codex_skills.get(name, [])
        custom_codex_paths, builtin_codex_paths = split_codex_paths(codex_paths)

        in_claude = bool(claude_paths)
        in_codex = bool(codex_paths)

        if in_claude and in_codex:
            present_in_both.append(
                {
                    "name": name,
                    "claude_skill_md": [str(path) for path in claude_paths],
                    "codex_skill_md": [str(path) for path in codex_paths],
                    "codex_satisfied_by_builtin": bool(
                        builtin_codex_paths and not custom_codex_paths
                    ),
                }
            )
            continue

        if in_claude:
            missing_in_codex.append(
                {
                    "name": name,
                    "source_skill_md": str(claude_paths[0]),
                    "target_dir": str(CODEX_ROOT / name),
                }
            )
            continue

        if in_codex:
            preferred_codex_source = (
                custom_codex_paths[0] if custom_codex_paths else builtin_codex_paths[0]
            )
            missing_in_claude.append(
                {
                    "name": name,
                    "source_skill_md": str(preferred_codex_source),
                    "source_kind": "custom" if custom_codex_paths else "builtin",
                    "target_dir": str(CLAUDE_ROOT / name),
                }
            )

    report = {
        "claude_root": str(CLAUDE_ROOT),
        "codex_root": str(CODEX_ROOT),
        "requested": requested,
        "codex_builtin_parity_names": sorted(CODEX_BUILTIN_PARITY_NAMES),
        "candidate_names": candidate_names,
        "missing_in_codex": missing_in_codex,
        "missing_in_claude": missing_in_claude,
        "present_in_both": present_in_both,
        "ignored_codex_only_builtins": ignored_codex_only_builtins,
        "not_found_anywhere": not_found_anywhere,
    }
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
