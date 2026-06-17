#!/usr/bin/env python3
"""Capture paired page screenshots and generate visual diff artifacts."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import html
import json
import math
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


DEFAULT_VIEWPORTS = ["desktop:1280x720", "mobile:390x844"]
MASK_COLOR = "#ff00ff"
PAD_COLOR = "#ffffff"


@dataclass
class ViewportSpec:
    label: str
    width: int
    height: int
    dpr: float = 1.0
    device_name: str | None = None


def parse_viewport(spec: str) -> ViewportSpec:
    label = None
    rest = spec.strip()
    if ":" in rest:
        possible_label, possible_rest = rest.split(":", 1)
        if re.fullmatch(r"[A-Za-z0-9_.-]+", possible_label):
            label = possible_label
            rest = possible_rest

    dpr = 1.0
    if "@" in rest:
        rest, raw_dpr = rest.rsplit("@", 1)
        dpr = float(raw_dpr)

    match = re.fullmatch(r"(\d+)x(\d+)", rest)
    if not match:
        raise argparse.ArgumentTypeError(
            f"Invalid viewport '{spec}'. Use name:WIDTHxHEIGHT or name:WIDTHxHEIGHT@DPR."
        )

    width, height = int(match.group(1)), int(match.group(2))
    if width < 1 or height < 1:
        raise argparse.ArgumentTypeError(f"Invalid viewport dimensions in '{spec}'.")

    if label is None:
        label = f"{width}x{height}"
        if dpr != 1:
            label += f"@{dpr:g}"

    return ViewportSpec(label=safe_slug(label), width=width, height=height, dpr=dpr)


def safe_slug(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9_.-]+", "-", value.strip().lower())
    value = re.sub(r"-{2,}", "-", value).strip("-")
    return value or "default"


def skill_dir() -> Path:
    return Path(__file__).resolve().parents[1]


def detect_repo_root(cwd: Path) -> Path:
    try:
        result = subprocess.run(
            ["git", "-C", str(cwd), "rev-parse", "--show-toplevel"],
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        return Path(result.stdout.strip())
    except Exception:
        return cwd


def repo_key(repo_root: Path) -> str:
    slug = safe_slug(repo_root.name)
    digest = hashlib.sha1(str(repo_root).encode("utf-8")).hexdigest()[:12]
    return f"{slug}-{digest}"


def default_output_dir() -> Path:
    root = detect_repo_root(Path.cwd())
    timestamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    return skill_dir() / "repos" / repo_key(root) / "runs" / timestamp


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare a reference page against a candidate page and write screenshots, heatmaps, and reports."
    )
    parser.add_argument("--reference", required=True, help="Public reference URL.")
    parser.add_argument("--candidate", required=True, help="Local or deployed candidate URL.")
    parser.add_argument("--reference-image-dir", default=None, help="Use pre-captured reference screenshots from this directory.")
    parser.add_argument("--candidate-image-dir", default=None, help="Use pre-captured candidate screenshots from this directory.")
    parser.add_argument("--out", help="Output run directory. Defaults to visual-diff/repos/<repo-key>/runs/<timestamp>.")
    parser.add_argument("--viewport", action="append", default=[], help="Viewport spec name:WIDTHxHEIGHT or name:WIDTHxHEIGHT@DPR. Repeatable.")
    parser.add_argument("--device", action="append", default=[], help="Playwright device profile name, such as 'iPhone 13'. Repeatable.")
    parser.add_argument("--viewport-only", action="store_true", help="Capture only the initial viewport instead of the full page.")
    parser.add_argument("--wait-until", default="domcontentloaded", choices=["commit", "domcontentloaded", "load", "networkidle"])
    parser.add_argument("--wait-ms", type=int, default=1500, help="Fixed wait after load and dismissals.")
    parser.add_argument("--lazy-scroll", action="store_true", help="Before full-page screenshots, scroll through the page to trigger lazy-loaded assets.")
    parser.add_argument("--lazy-scroll-step", type=int, default=600, help="CSS pixels to scroll between lazy-load settle waits.")
    parser.add_argument("--lazy-scroll-wait-ms", type=int, default=120, help="Wait after each lazy-scroll step.")
    parser.add_argument("--lazy-scroll-image-timeout-ms", type=int, default=5000, help="Best-effort timeout for image completion after lazy scrolling.")
    parser.add_argument("--timeout-ms", type=int, default=45000)
    parser.add_argument("--navigation-retries", type=int, default=2, help="Retry page navigation this many times before failing.")
    parser.add_argument("--capture-retries", type=int, default=0, help="Retry a full page capture when preparation, waits, or screenshot capture fail.")
    parser.add_argument("--allow-navigation-error", action="store_true", help="Continue after navigation errors instead of failing fast.")
    parser.add_argument("--color-scheme", choices=["light", "dark", "no-preference"], default=None)
    parser.add_argument("--locale", default=None)
    parser.add_argument("--timezone", default=None)
    parser.add_argument("--user-agent", default=None)
    parser.add_argument("--storage-state", default=None, help="Playwright storage state JSON to use for both pages.")
    parser.add_argument("--reference-storage-state", default=None, help="Playwright storage state JSON for the reference page.")
    parser.add_argument("--candidate-storage-state", default=None, help="Playwright storage state JSON for the candidate page.")
    parser.add_argument("--dismiss", action="append", default=[], help="CSS selector to click before capture. Repeatable.")
    parser.add_argument("--dismiss-text", action="append", default=[], help="Visible text to click before capture. Repeatable.")
    parser.add_argument("--dismiss-cycles", type=int, default=3, help="Number of dismissal passes to run before capture.")
    parser.add_argument("--dismiss-wait-ms", type=int, default=500, help="Wait after a successful dismissal click.")
    parser.add_argument("--wait-for", action="append", default=[], help="CSS selector that must appear before capture. Repeatable.")
    parser.add_argument("--wait-for-text", action="append", default=[], help="Visible text that must appear before capture. Repeatable.")
    parser.add_argument("--reference-wait-for", action="append", default=[], help="Reference-only CSS selector that must appear before capture. Repeatable.")
    parser.add_argument("--reference-wait-for-text", action="append", default=[], help="Reference-only visible text that must appear before capture. Repeatable.")
    parser.add_argument("--candidate-wait-for", action="append", default=[], help="Candidate-only CSS selector that must appear before capture. Repeatable.")
    parser.add_argument("--candidate-wait-for-text", action="append", default=[], help="Candidate-only visible text that must appear before capture. Repeatable.")
    parser.add_argument("--wait-for-timeout-ms", type=int, default=10000, help="Timeout for each --wait-for or --wait-for-text condition.")
    parser.add_argument("--fail-on-wait-timeout", action="store_true", help="Fail capture when any wait-for condition is missing.")
    parser.add_argument("--hover", action="append", default=[], help="CSS selector to hover before capture. Repeatable; the final selector remains hovered.")
    parser.add_argument("--reference-hover", action="append", default=[], help="Reference-only CSS selector to hover before capture. Repeatable.")
    parser.add_argument("--candidate-hover", action="append", default=[], help="Candidate-only CSS selector to hover before capture. Repeatable.")
    parser.add_argument("--hover-wait-ms", type=int, default=250, help="Wait after each hover before capture.")
    parser.add_argument("--hover-stability-probe", action="append", default=[], help="CSS selector to sample before and after --hover-stability-ms while hovered. Repeatable.")
    parser.add_argument("--hover-stability-ms", type=int, default=0, help="When positive, wait this long after hover and report movement for --hover-stability-probe selectors.")
    parser.add_argument("--scroll-y", type=int, default=None, help="Scroll both pages to this Y offset before capture.")
    parser.add_argument("--reference-scroll-y", type=int, default=None, help="Reference-only scroll Y offset before capture.")
    parser.add_argument("--candidate-scroll-y", type=int, default=None, help="Candidate-only scroll Y offset before capture.")
    parser.add_argument("--scroll-wait-ms", type=int, default=500, help="Wait after a pre-capture scroll before hovers, clips, and screenshots.")
    parser.add_argument("--hide", action="append", default=[], help="CSS selector to hide with injected CSS before capture. Repeatable.")
    parser.add_argument("--mask", action="append", default=[], help="CSS selector whose bounding boxes should be filled before diffing. Repeatable.")
    parser.add_argument("--mask-rect", action="append", default=[], help="Fixed mask rectangle x,y,w,h in screenshot CSS pixels. Repeatable.")
    parser.add_argument("--clip-selector", default=None, help="Capture only the bounding box for this selector on both pages.")
    parser.add_argument("--reference-clip-selector", default=None, help="Reference-only selector to clip the screenshot to.")
    parser.add_argument("--candidate-clip-selector", default=None, help="Candidate-only selector to clip the screenshot to.")
    parser.add_argument("--zoom-rect", action="append", default=[], help="Write enlarged crop artifacts for label:x,y,w,h in screenshot pixels. Repeatable.")
    parser.add_argument("--zoom-scale", type=int, default=4, help="Integer enlargement factor for --zoom-rect artifacts.")
    parser.add_argument("--color-pick", action="append", default=[], help="Sample color at label:x,y[,radius] in screenshot pixels. Radius samples a square around the point. Repeatable.")
    parser.add_argument("--color-pick-rect", action="append", default=[], help="Sample sorted dominant colors in label:x,y,w,h screenshot rectangle. Repeatable.")
    parser.add_argument("--color-pick-top", type=int, default=8, help="Number of dominant color bins to report for color picks.")
    parser.add_argument("--color-pick-quantum", type=int, default=16, help="RGB quantization step for sorted dominant color bins.")
    parser.add_argument("--freeze-animations", action="store_true", help="Disable CSS animations/transitions before screenshot capture.")
    parser.add_argument("--threshold", type=int, default=5, help="Per-pixel max RGB delta threshold, 0-255.")
    parser.add_argument("--max-mismatch", type=float, default=None, help="Exit non-zero if mismatch percent exceeds this value.")
    parser.add_argument("--no-dom-audit", action="store_true", help="Skip DOM audit JSON files.")
    parser.add_argument("--screenshot-scale", choices=["css", "device"], default="css")
    parser.add_argument("--background", default=PAD_COLOR, help="Canvas padding color for unequal screenshot sizes.")
    return parser.parse_args()


def hex_to_rgb(value: str) -> tuple[int, int, int]:
    value = value.strip()
    if value.startswith("#"):
        value = value[1:]
    if len(value) == 3:
        value = "".join(ch * 2 for ch in value)
    if not re.fullmatch(r"[0-9a-fA-F]{6}", value):
        raise ValueError(f"Invalid color: {value}")
    return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))


def fixed_mask_rects(raw_rects: list[str]) -> list[dict[str, float]]:
    rects = []
    for raw in raw_rects:
        parts = [p.strip() for p in raw.split(",")]
        if len(parts) != 4:
            raise ValueError(f"Invalid --mask-rect '{raw}'. Use x,y,w,h.")
        x, y, w, h = [float(p) for p in parts]
        rects.append({"x": x, "y": y, "width": w, "height": h, "selector": "fixed-rect"})
    return rects


def parse_zoom_rects(raw_rects: list[str]) -> list[dict[str, Any]]:
    rects: list[dict[str, Any]] = []
    for index, raw in enumerate(raw_rects, start=1):
        label = f"zoom-{index}"
        values = raw
        if ":" in raw:
            label, values = raw.split(":", 1)
            label = safe_slug(label)
        parts = [p.strip() for p in values.split(",")]
        if len(parts) != 4:
            raise ValueError(f"Invalid --zoom-rect '{raw}'. Use label:x,y,w,h or x,y,w,h.")
        x, y, w, h = [float(p) for p in parts]
        if w <= 0 or h <= 0:
            raise ValueError(f"Invalid --zoom-rect '{raw}'. Width and height must be positive.")
        rects.append({"label": label or f"zoom-{index}", "x": x, "y": y, "width": w, "height": h})
    return rects


def parse_color_picks(raw_points: list[str]) -> list[dict[str, Any]]:
    picks: list[dict[str, Any]] = []
    for index, raw in enumerate(raw_points, start=1):
        label = f"pick-{index}"
        values = raw
        if ":" in raw:
            label, values = raw.split(":", 1)
            label = safe_slug(label)
        parts = [p.strip() for p in values.split(",")]
        if len(parts) not in (2, 3):
            raise ValueError(f"Invalid --color-pick '{raw}'. Use label:x,y[,radius] or x,y[,radius].")
        x = float(parts[0])
        y = float(parts[1])
        radius = float(parts[2]) if len(parts) == 3 else 0.0
        if radius < 0:
            raise ValueError(f"Invalid --color-pick '{raw}'. Radius must be non-negative.")
        picks.append({"label": label or f"pick-{index}", "x": x, "y": y, "radius": radius})
    return picks


def resolve_storage_state(args: argparse.Namespace, role: str) -> str | None:
    raw = args.reference_storage_state if role == "reference" else args.candidate_storage_state
    raw = raw or args.storage_state
    if not raw:
        return None
    return str(Path(raw).expanduser().resolve())


def context_kwargs(
    spec: ViewportSpec,
    args: argparse.Namespace,
    role: str,
    device: dict[str, Any] | None = None,
) -> dict[str, Any]:
    kwargs: dict[str, Any] = {}
    if device:
        kwargs.update(device)
        kwargs.pop("default_browser_type", None)
    kwargs["viewport"] = {"width": spec.width, "height": spec.height}
    kwargs["device_scale_factor"] = spec.dpr
    if args.color_scheme:
        kwargs["color_scheme"] = args.color_scheme
    if args.locale:
        kwargs["locale"] = args.locale
    if args.timezone:
        kwargs["timezone_id"] = args.timezone
    if args.user_agent:
        kwargs["user_agent"] = args.user_agent
    storage_state = resolve_storage_state(args, role)
    if storage_state:
        kwargs["storage_state"] = storage_state
    return kwargs


def click_locator(locator: Any, timeout: int = 2500) -> bool:
    try:
        count = locator.count()
    except Exception:
        count = 1
    if count == 0:
        return False
    try:
        locator.last.click(timeout=timeout)
        return True
    except PlaywrightTimeoutError:
        pass
    except Exception:
        pass
    try:
        locator.last.evaluate("(element) => element.click()")
        return True
    except Exception:
        return False


def dismiss_page(page: Any, args: argparse.Namespace) -> list[str]:
    clicked: list[str] = []
    cycles = max(1, args.dismiss_cycles)
    for _ in range(cycles):
        clicked_this_cycle = False
        for selector in args.dismiss:
            if click_locator(page.locator(selector)):
                clicked.append(f"selector:{selector}")
                clicked_this_cycle = True
                page.wait_for_timeout(max(0, args.dismiss_wait_ms))

        for text in args.dismiss_text:
            locator = page.get_by_text(text, exact=True)
            clicked_text = click_locator(locator)
            if not clicked_text:
                locator = page.get_by_text(re.compile(f"^{re.escape(text)}$", re.I))
                clicked_text = click_locator(locator)
            if clicked_text:
                clicked.append(f"text:{text}")
                clicked_this_cycle = True
                page.wait_for_timeout(max(0, args.dismiss_wait_ms))

        if not clicked_this_cycle:
            break
    return clicked


def hide_page(page: Any, args: argparse.Namespace) -> list[str]:
    hidden: list[str] = []
    if not args.hide:
        return hidden

    css = "\n".join(
        f"{selector} {{ display: none !important; visibility: hidden !important; opacity: 0 !important; }}"
        for selector in args.hide
    )
    try:
        page.add_style_tag(content=css)
    except Exception:
        pass

    for selector in args.hide:
        try:
            locator = page.locator(selector)
            if locator.count() == 0:
                continue
            locator.evaluate_all(
                """
                elements => {
                  for (const element of elements) {
                    element.style.setProperty('display', 'none', 'important');
                    element.style.setProperty('visibility', 'hidden', 'important');
                    element.style.setProperty('opacity', '0', 'important');
                  }
                }
                """
            )
            hidden.append(selector)
        except Exception:
            pass
    return hidden


def freeze_animations(page: Any) -> None:
    try:
        page.add_style_tag(
            content="""
            *, *::before, *::after {
              animation: none !important;
              animation-delay: 0s !important;
              animation-duration: 0s !important;
              animation-iteration-count: 1 !important;
              animation-play-state: paused !important;
              transition: none !important;
              transition-delay: 0s !important;
              transition-duration: 0s !important;
              scroll-behavior: auto !important;
              caret-color: transparent !important;
            }
            """
        )
    except Exception:
        pass


