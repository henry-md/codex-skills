#!/usr/bin/env python3
"""Swap AI-upscaled image files into original paths while preserving originals."""

from __future__ import annotations

import argparse
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SwapPair:
    original: Path
    generated: Path
    backup: Path


def backup_path_for(original: Path) -> Path:
    return original.with_name(f"{original.stem}_orig{original.suffix}")


def parse_pair(raw: str) -> tuple[Path, Path]:
    if "=" not in raw:
        raise argparse.ArgumentTypeError("pairs must use ORIGINAL=GENERATED")
    original, generated = raw.split("=", 1)
    if not original or not generated:
        raise argparse.ArgumentTypeError("both ORIGINAL and GENERATED are required")
    return Path(original).expanduser().resolve(), Path(generated).expanduser().resolve()


def validate(raw_pairs: list[tuple[Path, Path]], overwrite_backup: bool) -> list[SwapPair]:
    swaps: list[SwapPair] = []
    seen_originals: set[Path] = set()
    seen_backups: set[Path] = set()

    for original, generated in raw_pairs:
        backup = backup_path_for(original)
        if original in seen_originals:
            raise ValueError(f"duplicate original path: {original}")
        if backup in seen_backups:
            raise ValueError(f"duplicate backup path: {backup}")
        if original == generated:
            raise ValueError(f"generated path must differ from original: {original}")
        if original.stem.endswith("_orig"):
            raise ValueError(f"refusing to upscale an _orig backup: {original}")
        if not original.is_file():
            raise ValueError(f"original file does not exist: {original}")
        if not generated.is_file():
            raise ValueError(f"generated file does not exist: {generated}")
        if backup.exists() and not overwrite_backup:
            raise ValueError(f"backup already exists: {backup}")

        swaps.append(SwapPair(original=original, generated=generated, backup=backup))
        seen_originals.add(original)
        seen_backups.add(backup)

    return swaps


def describe(swaps: list[SwapPair]) -> None:
    for swap in swaps:
        print(f"{swap.original} -> {swap.backup}")
        print(f"{swap.generated} -> {swap.original}")


def perform(swaps: list[SwapPair], overwrite_backup: bool) -> None:
    moved_originals: list[SwapPair] = []
    moved_generated: list[SwapPair] = []

    try:
        for swap in swaps:
            if overwrite_backup and swap.backup.exists():
                swap.backup.unlink()
            shutil.move(str(swap.original), str(swap.backup))
            moved_originals.append(swap)

        for swap in swaps:
            shutil.move(str(swap.generated), str(swap.original))
            moved_generated.append(swap)
    except Exception:
        print("Swap failed; attempting rollback.", file=sys.stderr)

        for swap in reversed(moved_generated):
            if swap.original.exists() and not swap.generated.exists():
                shutil.move(str(swap.original), str(swap.generated))

        for swap in reversed(moved_originals):
            if swap.backup.exists() and not swap.original.exists():
                shutil.move(str(swap.backup), str(swap.original))

        raise


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Rename originals to *_orig and move generated upscales into the original paths."
    )
    parser.add_argument(
        "--pair",
        action="append",
        type=parse_pair,
        required=True,
        metavar="ORIGINAL=GENERATED",
        help="Original repo image path and temporary generated image path.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print planned moves without changing files.")
    parser.add_argument(
        "--overwrite-backup",
        action="store_true",
        help="Allow replacing an existing *_orig backup. Use only with explicit user permission.",
    )
    args = parser.parse_args()

    try:
        swaps = validate(args.pair, args.overwrite_backup)
        describe(swaps)
        if args.dry_run:
            return 0
        perform(swaps, args.overwrite_backup)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
