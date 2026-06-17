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


def prepare_page(page: Any, url: str, role: str, args: argparse.Namespace) -> dict[str, Any]:
    response_status = None
    response_error = None
    attempts = max(1, args.navigation_retries + 1)
    for attempt in range(1, attempts + 1):
        response_error = None
        try:
            response = page.goto(url, wait_until=args.wait_until, timeout=args.timeout_ms)
            if response is not None:
                response_status = response.status
            break
        except PlaywrightTimeoutError as exc:
            response_error = f"timeout: {exc}"
        except Exception as exc:
            response_error = f"{type(exc).__name__}: {exc}"

        if attempt < attempts:
            page.wait_for_timeout(1000 * attempt)

    if response_error and not args.allow_navigation_error:
        raise RuntimeError(f"Navigation failed for {url}: {response_error}")

    if args.freeze_animations:
        freeze_animations(page)

    page.wait_for_timeout(max(0, args.wait_ms))

    clicked = dismiss_page(page, args)
    hidden = hide_page(page, args)

    page.wait_for_timeout(max(0, args.wait_ms))

    waited_for: list[dict[str, str]] = []
    wait_for_selectors = list(args.wait_for)
    wait_for_text = list(args.wait_for_text)
    if role == "reference":
        wait_for_selectors.extend(args.reference_wait_for)
        wait_for_text.extend(args.reference_wait_for_text)
    else:
        wait_for_selectors.extend(args.candidate_wait_for)
        wait_for_text.extend(args.candidate_wait_for_text)

    for selector in wait_for_selectors:
        try:
            page.locator(selector).first.wait_for(state="visible", timeout=max(0, args.wait_for_timeout_ms))
            waited_for.append({"selector": selector, "status": "visible"})
        except Exception as exc:
            waited_for.append({"selector": selector, "status": f"missing:{type(exc).__name__}"})

    for text in wait_for_text:
        try:
            page.get_by_text(text).first.wait_for(state="visible", timeout=max(0, args.wait_for_timeout_ms))
            waited_for.append({"text": text, "status": "visible"})
        except Exception as exc:
            waited_for.append({"text": text, "status": f"missing:{type(exc).__name__}"})

    if args.fail_on_wait_timeout:
        missing_waits = [item for item in waited_for if item.get("status", "").startswith("missing:")]
        if missing_waits:
            raise RuntimeError(f"Wait condition failed for {url}: {json.dumps(missing_waits)}")

    return {
        "status": response_status,
        "error": response_error,
        "final_url": page.url,
        "title": safe_eval(page, "() => document.title"),
        "clicked": clicked,
        "hidden": hidden,
        "waitedFor": waited_for,
    }


def safe_eval(page: Any, script: str) -> Any:
    try:
        return page.evaluate(script)
    except Exception:
        return None


def lazy_scroll_page(page: Any, args: argparse.Namespace) -> dict[str, Any]:
    if args.viewport_only or not args.lazy_scroll:
        return {"enabled": False}

    initial = safe_eval(
        page,
        """
        () => ({
          scrollHeight: Math.max(document.documentElement.scrollHeight, document.body.scrollHeight),
          innerHeight: window.innerHeight,
          imageCount: document.images.length,
          completeImages: Array.from(document.images).filter(img => img.complete).length
        })
        """,
    ) or {}
    step = max(1, int(args.lazy_scroll_step))
    wait_ms = max(0, int(args.lazy_scroll_wait_ms))
    positions: list[int] = []
    y = 0
    last_max_scroll = -1

    for _ in range(1000):
        metrics = safe_eval(
            page,
            """
            () => ({
              scrollHeight: Math.max(document.documentElement.scrollHeight, document.body.scrollHeight),
              innerHeight: window.innerHeight
            })
            """,
        ) or {}
        scroll_height = int(metrics.get("scrollHeight") or 0)
        inner_height = int(metrics.get("innerHeight") or 0)
        max_scroll = max(0, scroll_height - inner_height)
        if max_scroll == last_max_scroll and y > max_scroll:
            break
        last_max_scroll = max_scroll
        next_y = min(y, max_scroll)
        if not positions or positions[-1] != next_y:
            positions.append(next_y)
            try:
                page.evaluate("(scrollY) => window.scrollTo(0, scrollY)", next_y)
            except Exception:
                pass
            page.wait_for_timeout(wait_ms)
        if y >= max_scroll:
            break
        y += step

    try:
        page.wait_for_function(
            "() => Array.from(document.images).every(img => img.complete)",
            timeout=max(0, int(args.lazy_scroll_image_timeout_ms)),
        )
    except Exception:
        pass

    decode_error = None
    try:
        page.evaluate(
            """
            async () => {
              await Promise.allSettled(
                Array.from(document.images).map(img => img.decode ? img.decode() : Promise.resolve())
              );
            }
            """
        )
    except Exception as exc:
        decode_error = f"{type(exc).__name__}: {exc}"

    try:
        page.evaluate("() => window.scrollTo(0, 0)")
    except Exception:
        pass
    page.wait_for_timeout(max(wait_ms, 100))

    final = safe_eval(
        page,
        """
        () => {
          const images = Array.from(document.images);
          return {
            scrollHeight: Math.max(document.documentElement.scrollHeight, document.body.scrollHeight),
            innerHeight: window.innerHeight,
            imageCount: images.length,
            completeImages: images.filter(img => img.complete).length,
            decodedOrEmptyImages: images.filter(img => !img.currentSrc || img.naturalWidth > 0).length,
            incompleteImages: images
              .filter(img => !img.complete || (img.currentSrc && img.naturalWidth === 0))
              .slice(0, 20)
              .map(img => ({ src: img.currentSrc || img.src || null, alt: img.alt || null }))
          };
        }
        """,
    ) or {}

    return {
        "enabled": True,
        "step": step,
        "waitMs": wait_ms,
        "positions": len(positions),
        "initial": initial,
        "final": final,
        "decodeError": decode_error,
    }


def hover_page(page: Any, role: str, args: argparse.Namespace) -> list[dict[str, Any]]:
    selectors = list(args.hover)
    selectors.extend(args.reference_hover if role == "reference" else args.candidate_hover)
    hovered: list[dict[str, Any]] = []
    for selector in selectors:
        locator = page.locator(selector).first
        try:
            locator.wait_for(state="visible", timeout=max(0, args.wait_for_timeout_ms))
            box = locator.bounding_box(timeout=max(0, args.wait_for_timeout_ms))
            if not box:
                raise RuntimeError("visible element has no bounding box")
            x = box["x"] + box["width"] / 2
            y = box["y"] + box["height"] / 2
            page.mouse.move(x, y)
            page.wait_for_timeout(max(0, args.hover_wait_ms))
            hovered.append(
                {
                    "selector": selector,
                    "status": "hovered",
                    "x": round(x, 2),
                    "y": round(y, 2),
                }
            )
        except Exception as exc:
            raise RuntimeError(f"Hover failed for {role} selector '{selector}': {type(exc).__name__}: {exc}") from exc
    return hovered


def scroll_page(page: Any, role: str, args: argparse.Namespace) -> dict[str, Any]:
    scroll_y = args.reference_scroll_y if role == "reference" else args.candidate_scroll_y
    scroll_y = args.scroll_y if scroll_y is None else scroll_y
    if scroll_y is None:
        return {"enabled": False}
    try:
        page.evaluate("(y) => window.scrollTo(0, y)", int(scroll_y))
        page.wait_for_timeout(max(0, args.scroll_wait_ms))
        actual_y = safe_eval(page, "() => Math.round(window.scrollY)")
        return {"enabled": True, "requestedY": int(scroll_y), "actualY": actual_y, "waitMs": args.scroll_wait_ms}
    except Exception as exc:
        raise RuntimeError(f"Pre-capture scroll failed for {role}: {type(exc).__name__}: {exc}") from exc


def sample_hover_stability(page: Any, args: argparse.Namespace) -> list[dict[str, Any]]:
    if not args.hover_stability_probe or args.hover_stability_ms <= 0:
        return []

    def sample(selector: str) -> dict[str, Any]:
        return page.locator(selector).first.evaluate(
            """
            el => {
              const rect = el.getBoundingClientRect();
              const style = getComputedStyle(el);
              return {
                x: Math.round((rect.left + window.scrollX) * 100) / 100,
                y: Math.round((rect.top + window.scrollY) * 100) / 100,
                width: Math.round(rect.width * 100) / 100,
                height: Math.round(rect.height * 100) / 100,
                transform: style.transform,
                animationPlayState: style.animationPlayState,
                color: style.color
              };
            }
            """
        )

    before: dict[str, dict[str, Any]] = {}
    for selector in args.hover_stability_probe:
        try:
            page.locator(selector).first.wait_for(state="visible", timeout=max(0, args.wait_for_timeout_ms))
            before[selector] = sample(selector)
        except Exception as exc:
            before[selector] = {"error": f"{type(exc).__name__}: {exc}"}

    page.wait_for_timeout(max(0, args.hover_stability_ms))

    results: list[dict[str, Any]] = []
    for selector in args.hover_stability_probe:
        first = before.get(selector) or {}
        try:
            second = sample(selector)
        except Exception as exc:
            second = {"error": f"{type(exc).__name__}: {exc}"}
        dx = None
        dy = None
        if "x" in first and "x" in second:
            dx = round(float(second["x"]) - float(first["x"]), 2)
            dy = round(float(second["y"]) - float(first["y"]), 2)
        results.append(
            {
                "selector": selector,
                "waitMs": args.hover_stability_ms,
                "before": first,
                "after": second,
                "deltaX": dx,
                "deltaY": dy,
                "transformStable": first.get("transform") == second.get("transform"),
            }
        )
    return results


def collect_mask_boxes(page: Any, selectors: list[str], fixed_rects: list[dict[str, float]]) -> list[dict[str, float]]:
    boxes = list(fixed_rects)
    for selector in selectors:
        try:
            found = page.locator(selector).evaluate_all(
                """
                els => els.map(el => {
                  const rect = el.getBoundingClientRect();
                  return {
                    x: rect.left + window.scrollX,
                    y: rect.top + window.scrollY,
                    width: rect.width,
                    height: rect.height
                  };
                }).filter(r => r.width > 0 && r.height > 0)
                """
            )
            for box in found:
                box["selector"] = selector
                boxes.append(box)
        except Exception:
            boxes.append({"selector": selector, "error": "selector lookup failed", "x": 0, "y": 0, "width": 0, "height": 0})
    return boxes


def apply_masks(image_path: Path, boxes: list[dict[str, float]], mask_color: str = MASK_COLOR) -> None:
    if not boxes:
        return
    image = Image.open(image_path).convert("RGB")
    draw = ImageDraw.Draw(image)
    fill = hex_to_rgb(mask_color)
    width, height = image.size
    for box in boxes:
        x = int(round(float(box.get("x", 0))))
        y = int(round(float(box.get("y", 0))))
        w = int(round(float(box.get("width", 0))))
        h = int(round(float(box.get("height", 0))))
        if w <= 0 or h <= 0:
            continue
        left = max(0, x)
        top = max(0, y)
        right = min(width, x + w)
        bottom = min(height, y + h)
        if right <= left or bottom <= top:
            continue
        draw.rectangle([left, top, right, bottom], fill=fill)
    image.save(image_path)


def resolve_clip_box(page: Any, role: str, args: argparse.Namespace) -> tuple[dict[str, float] | None, dict[str, Any] | None]:
    selector = args.reference_clip_selector if role == "reference" else args.candidate_clip_selector
    selector = selector or args.clip_selector
    if not selector:
        return None, None
    try:
        locator = page.locator(selector).first
        locator.wait_for(state="visible", timeout=max(0, args.wait_for_timeout_ms))
        box = locator.bounding_box(timeout=max(0, args.wait_for_timeout_ms))
        if not box:
            raise RuntimeError("visible element has no bounding box")
        scroll = safe_eval(page, "() => ({ x: window.scrollX, y: window.scrollY })") or {"x": 0, "y": 0}
        clip = {
            "x": max(0, float(box["x"])),
            "y": max(0, float(box["y"])),
            "width": max(1, float(box["width"])),
            "height": max(1, float(box["height"])),
        }
        meta = {
            "selector": selector,
            "x": round(clip["x"], 2),
            "y": round(clip["y"], 2),
            "width": round(clip["width"], 2),
            "height": round(clip["height"], 2),
            "docX": round(float(box["x"]) + float(scroll.get("x") or 0), 2),
            "docY": round(float(box["y"]) + float(scroll.get("y") or 0), 2),
        }
        return clip, meta
    except Exception as exc:
        raise RuntimeError(f"Clip selector failed for {role} selector '{selector}': {type(exc).__name__}: {exc}") from exc


def clip_mask_boxes(boxes: list[dict[str, float]], clip_meta: dict[str, Any] | None) -> list[dict[str, float]]:
    if not clip_meta:
        return boxes
    clipped: list[dict[str, float]] = []
    clip_x = float(clip_meta["docX"])
    clip_y = float(clip_meta["docY"])
    clip_w = float(clip_meta["width"])
    clip_h = float(clip_meta["height"])
    for box in boxes:
        x = float(box.get("x", 0)) - clip_x
        y = float(box.get("y", 0)) - clip_y
        w = float(box.get("width", 0))
        h = float(box.get("height", 0))
        left = max(0, x)
        top = max(0, y)
        right = min(clip_w, x + w)
        bottom = min(clip_h, y + h)
        if right <= left or bottom <= top:
            continue
        clipped_box = dict(box)
        clipped_box.update({"x": left, "y": top, "width": right - left, "height": bottom - top})
        clipped.append(clipped_box)
    return clipped


def collect_dom_audit(page: Any) -> dict[str, Any]:
    return safe_eval(
        page,
        """
        () => {
          const visible = el => {
            const r = el.getBoundingClientRect();
            const s = getComputedStyle(el);
            return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none';
          };
          const elements = Array.from(document.querySelectorAll('body *')).filter(visible).slice(0, 800).map((el, index) => {
            const r = el.getBoundingClientRect();
            const s = getComputedStyle(el);
            return {
              index,
              tag: el.tagName.toLowerCase(),
              id: el.id || null,
              className: String(el.className || '').slice(0, 160),
              text: (el.innerText || el.textContent || '').trim().replace(/\\s+/g, ' ').slice(0, 220),
              src: el.currentSrc || el.src || null,
              href: el.href || null,
              x: Math.round((r.left + window.scrollX) * 100) / 100,
              y: Math.round((r.top + window.scrollY) * 100) / 100,
              width: Math.round(r.width * 100) / 100,
              height: Math.round(r.height * 100) / 100,
              fontFamily: s.fontFamily,
              fontSize: s.fontSize,
              fontWeight: s.fontWeight,
              lineHeight: s.lineHeight,
              color: s.color,
              backgroundColor: s.backgroundColor,
              display: s.display,
              position: s.position
            };
          });
          return {
            title: document.title,
            url: location.href,
            devicePixelRatio: window.devicePixelRatio,
            innerWidth: window.innerWidth,
            innerHeight: window.innerHeight,
            visualViewport: window.visualViewport ? {
              width: Math.round(window.visualViewport.width * 100) / 100,
              height: Math.round(window.visualViewport.height * 100) / 100,
              scale: window.visualViewport.scale,
              offsetLeft: Math.round(window.visualViewport.offsetLeft * 100) / 100,
              offsetTop: Math.round(window.visualViewport.offsetTop * 100) / 100
            } : null,
            scrollWidth: document.documentElement.scrollWidth,
            scrollHeight: document.documentElement.scrollHeight,
            bodyText: (document.body.innerText || '').replace(/\\s+/g, ' ').trim().slice(0, 8000),
            elements
          };
        }
        """,
    ) or {}


def collect_page_content(page: Any) -> dict[str, Any]:
    content = safe_eval(
        page,
        """
        () => {
          const attr = (el, name) => el.getAttribute(name);
          const absolute = value => {
            if (!value) return null;
            try { return new URL(value, location.href).href; } catch { return value; }
          };
          const meta = Array.from(document.querySelectorAll('meta')).map(el => ({
            name: attr(el, 'name'),
            property: attr(el, 'property'),
            content: attr(el, 'content')
          })).filter(item => item.name || item.property || item.content);
          const headings = Array.from(document.querySelectorAll('h1,h2,h3,h4,h5,h6')).map(el => ({
            level: el.tagName.toLowerCase(),
            text: (el.innerText || el.textContent || '').trim().replace(/\\s+/g, ' ')
          })).filter(item => item.text);
          const links = Array.from(document.querySelectorAll('a[href]')).map(el => ({
            text: (el.innerText || el.textContent || '').trim().replace(/\\s+/g, ' '),
            href: absolute(attr(el, 'href')),
            target: attr(el, 'target')
          }));
          const images = Array.from(document.querySelectorAll('img')).map(el => ({
            alt: attr(el, 'alt'),
            src: absolute(el.currentSrc || attr(el, 'src')),
            srcset: attr(el, 'srcset'),
            width: el.naturalWidth || null,
            height: el.naturalHeight || null,
            renderedWidth: Math.round(el.getBoundingClientRect().width * 100) / 100,
            renderedHeight: Math.round(el.getBoundingClientRect().height * 100) / 100
          }));
          const media = Array.from(document.querySelectorAll('video,audio,iframe,embed,object,source')).map(el => ({
            tag: el.tagName.toLowerCase(),
            title: attr(el, 'title'),
            src: absolute(attr(el, 'src') || attr(el, 'data-src')),
            type: attr(el, 'type')
          }));
          const stylesheets = Array.from(document.querySelectorAll('link[rel~="stylesheet"], link[as="style"]')).map(el => ({
            href: absolute(attr(el, 'href')),
            media: attr(el, 'media')
          }));
          const scripts = Array.from(document.querySelectorAll('script[src]')).map(el => ({
            src: absolute(attr(el, 'src')),
            type: attr(el, 'type'),
            async: el.async,
            defer: el.defer
          }));
          return {
            title: document.title,
            url: location.href,
            canonical: document.querySelector('link[rel="canonical"]')?.href || null,
            lang: document.documentElement.lang || null,
            meta,
            headings,
            links,
            images,
            media,
            stylesheets,
            scripts,
            text: (document.body.innerText || '').replace(/\\s+\\n/g, '\\n').trim()
          };
        }
        """,
    ) or {}
    try:
        content["html"] = page.content()
    except Exception:
        content["html"] = None
    return content


def _capture_page_once(
    browser: Any,
    url: str,
    spec: ViewportSpec,
    role: str,
    out_dir: Path,
    args: argparse.Namespace,
    device: dict[str, Any] | None = None,
) -> dict[str, Any]:
    context = browser.new_context(**context_kwargs(spec, args, role=role, device=device))
    page = context.new_page()
    prep = prepare_page(page, url, role, args)
    prep["lazyScroll"] = lazy_scroll_page(page, args)
    prep["postLazyDismissed"] = dismiss_page(page, args)
    prep["postLazyHidden"] = hide_page(page, args)
    prep["scroll"] = scroll_page(page, role, args)
    prep["hovered"] = hover_page(page, role, args)
    prep["hoverStability"] = sample_hover_stability(page, args)
    clip_box, clip_meta = resolve_clip_box(page, role, args)
    mask_boxes = clip_mask_boxes(collect_mask_boxes(page, args.mask, fixed_mask_rects(args.mask_rect)), clip_meta)

    screenshot_path = out_dir / f"{spec.label}-{role}.png"
    page.screenshot(
        path=str(screenshot_path),
        full_page=False if clip_box else not args.viewport_only,
        clip=clip_box,
        scale=args.screenshot_scale,
        animations="disabled" if args.freeze_animations else "allow",
    )
    unmasked_screenshot_path = out_dir / f"{spec.label}-{role}-unmasked.png"
    shutil.copyfile(screenshot_path, unmasked_screenshot_path)
    apply_masks(screenshot_path, mask_boxes)

    audit_path = None
    audit_summary = None
    content_paths: dict[str, str] = {}
    content_summary = None
    if not args.no_dom_audit:
        audit = collect_dom_audit(page)
        audit_path = out_dir / f"{spec.label}-{role}-dom.json"
        audit_path.write_text(json.dumps(audit, indent=2), encoding="utf-8")
        audit_summary = {
            "title": audit.get("title"),
            "url": audit.get("url"),
            "devicePixelRatio": audit.get("devicePixelRatio"),
            "innerWidth": audit.get("innerWidth"),
            "innerHeight": audit.get("innerHeight"),
            "visualViewport": audit.get("visualViewport"),
            "scrollWidth": audit.get("scrollWidth"),
            "scrollHeight": audit.get("scrollHeight"),
            "elementCount": len(audit.get("elements", [])),
        }

    page_content = collect_page_content(page)
    content_json_path = out_dir / f"{spec.label}-{role}-content.json"
    content_text_path = out_dir / f"{spec.label}-{role}-text.txt"
    content_html_path = out_dir / f"{spec.label}-{role}.html"
    html_content = page_content.pop("html", None)
    content_json_path.write_text(json.dumps(page_content, indent=2), encoding="utf-8")
    content_text_path.write_text(page_content.get("text") or "", encoding="utf-8")
    if html_content is not None:
        content_html_path.write_text(html_content, encoding="utf-8")
    content_paths = {
        "json": str(content_json_path),
        "text": str(content_text_path),
        "html": str(content_html_path) if html_content is not None else "",
    }
    content_summary = {
        "title": page_content.get("title"),
        "url": page_content.get("url"),
        "headingCount": len(page_content.get("headings", [])),
        "linkCount": len(page_content.get("links", [])),
        "imageCount": len(page_content.get("images", [])),
        "mediaCount": len(page_content.get("media", [])),
        "stylesheetCount": len(page_content.get("stylesheets", [])),
        "scriptCount": len(page_content.get("scripts", [])),
        "textLength": len(page_content.get("text") or ""),
    }

    image_size = Image.open(screenshot_path).size
    context.close()
    return {
        "url": url,
        "screenshot": str(screenshot_path),
        "unmaskedScreenshot": str(unmasked_screenshot_path),
        "domAudit": str(audit_path) if audit_path else None,
        "domSummary": audit_summary,
        "content": content_paths,
        "contentSummary": content_summary,
        "imageWidth": image_size[0],
        "imageHeight": image_size[1],
        "maskBoxes": mask_boxes,
        "clip": clip_meta,
        **prep,
    }


def capture_page(
    browser: Any,
    url: str,
    spec: ViewportSpec,
    role: str,
    out_dir: Path,
    args: argparse.Namespace,
    device: dict[str, Any] | None = None,
) -> dict[str, Any]:
    attempts = max(1, int(args.capture_retries) + 1)
    errors: list[str] = []
    for attempt in range(1, attempts + 1):
        try:
            return _capture_page_once(browser, url, spec, role, out_dir, args, device=device)
        except Exception as exc:
            message = f"{type(exc).__name__}: {exc}"
            errors.append(message)
            if attempt < attempts:
                print(
                    f"Retrying {role} capture for {spec.label} after failed attempt {attempt}/{attempts}: {message}",
                    file=sys.stderr,
                    flush=True,
                )
                continue
            raise RuntimeError(f"Capture failed for {role} {spec.label} {url} after {attempts} attempts: {errors}") from exc


def image_only_capture(
    spec: ViewportSpec,
    role: str,
    source_dir: str,
    out_dir: Path,
    url: str,
) -> dict[str, Any]:
    source_root = Path(source_dir).expanduser().resolve()
    candidates = [
        source_root / f"{spec.label}-{role}.png",
        source_root / f"{spec.label}.png",
        source_root / f"{spec.label}-reference.png",
        source_root / f"{spec.label}-candidate.png",
    ]
    source_path = next((candidate for candidate in candidates if candidate.exists()), None)
    if source_path is None:
        wanted = ", ".join(str(candidate) for candidate in candidates)
        raise FileNotFoundError(f"No pre-captured {role} image for viewport '{spec.label}'. Tried: {wanted}")

    target_path = out_dir / f"{spec.label}-{role}.png"
    if source_path.resolve() != target_path.resolve():
        shutil.copyfile(source_path, target_path)
    unmasked_target_path = out_dir / f"{spec.label}-{role}-unmasked.png"
    if source_path.resolve() != unmasked_target_path.resolve():
        shutil.copyfile(source_path, unmasked_target_path)
    image_size = Image.open(target_path).size
    return {
        "url": url,
        "screenshot": str(target_path),
        "unmaskedScreenshot": str(unmasked_target_path),
        "domAudit": None,
        "domSummary": None,
        "content": {},
        "contentSummary": None,
        "imageWidth": image_size[0],
        "imageHeight": image_size[1],
        "maskBoxes": [],
        "status": None,
        "error": None,
        "final_url": url,
        "title": None,
        "clicked": [],
        "sourceImage": str(source_path),
    }


def padded_rgb(path: Path, size: tuple[int, int], background: str) -> Image.Image:
    image = Image.open(path).convert("RGB")
    canvas = Image.new("RGB", size, hex_to_rgb(background))
    canvas.paste(image, (0, 0))
    return canvas


def estimate_ssim(gray_a: np.ndarray, gray_b: np.ndarray) -> float:
    a = gray_a.astype(np.float64)
    b = gray_b.astype(np.float64)
    mu_a = a.mean()
    mu_b = b.mean()
    var_a = a.var()
    var_b = b.var()
    cov = ((a - mu_a) * (b - mu_b)).mean()
    c1 = (0.01 * 255) ** 2
    c2 = (0.03 * 255) ** 2
    denominator = (mu_a**2 + mu_b**2 + c1) * (var_a + var_b + c2)
    if denominator == 0:
        return 1.0 if np.array_equal(gray_a, gray_b) else 0.0
    return float(((2 * mu_a * mu_b + c1) * (2 * cov + c2)) / denominator)


def make_heatmap(max_delta: np.ndarray, threshold: int) -> Image.Image:
    delta = max_delta.astype(np.float32)
    intensity = np.clip(delta * 3.0, 0, 255).astype(np.uint8)
    heat = np.zeros((*max_delta.shape, 3), dtype=np.uint8)
    heat[..., 0] = 255
    heat[..., 1] = np.clip(255 - intensity, 0, 255)
    heat[..., 2] = np.clip(255 - delta * 6.0, 0, 255).astype(np.uint8)
    background = np.full((*max_delta.shape, 3), 255, dtype=np.uint8)
    mask = max_delta > threshold
    background[mask] = heat[mask]
    return Image.fromarray(background, mode="RGB")


def make_overlay(candidate: Image.Image, max_delta: np.ndarray, threshold: int) -> Image.Image:
    base = candidate.convert("RGBA")
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    alpha = np.zeros(max_delta.shape, dtype=np.uint8)
    changed = max_delta > threshold
    alpha[changed] = np.clip(max_delta[changed].astype(np.uint16) * 2, 96, 220).astype(np.uint8)
    data = np.zeros((*max_delta.shape, 4), dtype=np.uint8)
    data[..., 0] = 255
    data[..., 3] = alpha
    overlay = Image.fromarray(data, mode="RGBA")
    return Image.alpha_composite(base, overlay).convert("RGB")


def default_font(size: int = 18) -> ImageFont.ImageFont:
    for candidate in [
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/Library/Fonts/Arial.ttf",
    ]:
        try:
            return ImageFont.truetype(candidate, size)
        except Exception:
            pass
    return ImageFont.load_default()


def label_strip(images: list[tuple[str, Image.Image]], background: str) -> Image.Image:
    label_h = 38
    gutter = 10
    total_w = sum(image.width for _, image in images) + gutter * (len(images) - 1)
    max_h = max(image.height for _, image in images)
    strip = Image.new("RGB", (total_w, max_h + label_h), hex_to_rgb(background))
    draw = ImageDraw.Draw(strip)
    font = default_font(18)
    x = 0
    for label, image in images:
        draw.rectangle([x, 0, x + image.width, label_h], fill=(20, 20, 20))
        draw.text((x + 12, 9), label, fill=(255, 255, 255), font=font)
        strip.paste(image, (x, label_h))
        x += image.width + gutter
    return strip


def crop_rect(image: Image.Image, rect: dict[str, Any]) -> Image.Image | None:
    left = max(0, int(round(float(rect["x"]))))
    top = max(0, int(round(float(rect["y"]))))
    right = min(image.width, int(round(float(rect["x"]) + float(rect["width"]))))
    bottom = min(image.height, int(round(float(rect["y"]) + float(rect["height"]))))
    if right <= left or bottom <= top:
        return None
    return image.crop((left, top, right, bottom))


def mean_rgb(image: Image.Image) -> dict[str, float]:
    arr = np.asarray(image.convert("RGB"), dtype=np.float64)
    if arr.size == 0:
        return {"r": 0.0, "g": 0.0, "b": 0.0}
    values = arr.reshape(-1, 3).mean(axis=0)
    return {"r": round(float(values[0]), 3), "g": round(float(values[1]), 3), "b": round(float(values[2]), 3)}


def rgb_to_hex(rgb: tuple[int, int, int] | list[int] | np.ndarray) -> str:
    values = [max(0, min(255, int(round(float(v))))) for v in rgb[:3]]
    return "#{:02x}{:02x}{:02x}".format(*values)


def image_color_summary(image: Image.Image, top: int, quantum: int) -> dict[str, Any]:
    arr = np.asarray(image.convert("RGB"), dtype=np.uint8)
    pixels = arr.reshape(-1, 3)
    if pixels.size == 0:
        return {
            "pixelCount": 0,
            "meanRgb": {"r": 0.0, "g": 0.0, "b": 0.0},
            "medianRgb": {"r": 0, "g": 0, "b": 0},
            "dominantColors": [],
        }

    mean_values = pixels.astype(np.float64).mean(axis=0)
    median_values = np.median(pixels, axis=0)
    quantum = max(1, min(255, int(quantum)))
    quantized = (pixels.astype(np.uint16) // quantum) * quantum
    quantized = np.clip(quantized, 0, 255).astype(np.uint8)
    colors, counts = np.unique(quantized, axis=0, return_counts=True)
    order = np.argsort(counts)[::-1][: max(0, int(top))]
    dominant = []
    total = int(pixels.shape[0])
    for idx in order:
        rgb = tuple(int(v) for v in colors[idx])
        count = int(counts[idx])
        dominant.append(
            {
                "rgb": {"r": rgb[0], "g": rgb[1], "b": rgb[2]},
                "hex": rgb_to_hex(rgb),
                "count": count,
                "percent": round((count / total) * 100, 3) if total else 0.0,
            }
        )

    median_rgb = tuple(int(round(float(v))) for v in median_values)
    return {
        "pixelCount": total,
        "meanRgb": {"r": round(float(mean_values[0]), 3), "g": round(float(mean_values[1]), 3), "b": round(float(mean_values[2]), 3)},
        "meanHex": rgb_to_hex(mean_values),
        "medianRgb": {"r": median_rgb[0], "g": median_rgb[1], "b": median_rgb[2]},
        "medianHex": rgb_to_hex(median_rgb),
        "dominantColors": dominant,
    }


def make_color_swatch(
    sample: dict[str, Any],
    out_dir: Path,
    spec: ViewportSpec,
    background: str,
) -> str | None:
    ref_colors = sample.get("reference", {}).get("dominantColors", [])
    cand_colors = sample.get("candidate", {}).get("dominantColors", [])
    if not ref_colors and not cand_colors:
        return None
    rows = max(len(ref_colors), len(cand_colors), 1)
    label_w = 115
    swatch_w = 72
    row_h = 36
    gutter = 16
    width = label_w * 2 + swatch_w * 2 + gutter * 3
    height = row_h * rows + 36
    image = Image.new("RGB", (width, height), hex_to_rgb(background))
    draw = ImageDraw.Draw(image)
    font = default_font(14)
    draw.text((12, 8), "Reference", fill=(20, 20, 20), font=font)
    draw.text((label_w + swatch_w + gutter * 2, 8), "Candidate", fill=(20, 20, 20), font=font)

    def draw_color_column(colors: list[dict[str, Any]], x: int) -> None:
        for row in range(rows):
            y = 32 + row * row_h
            if row >= len(colors):
                continue
            color = colors[row]
            rgb = color.get("rgb", {})
            fill = (int(rgb.get("r", 0)), int(rgb.get("g", 0)), int(rgb.get("b", 0)))
            draw.rectangle([x, y, x + swatch_w - 1, y + row_h - 7], fill=fill, outline=(210, 210, 210))
            draw.text((x + swatch_w + 8, y + 1), color.get("hex", ""), fill=(20, 20, 20), font=font)
            draw.text((x + swatch_w + 8, y + 17), f"{color.get('percent', 0):.1f}%", fill=(70, 70, 70), font=font)

    draw_color_column(ref_colors, 12)
    draw_color_column(cand_colors, label_w + swatch_w + gutter * 2)
    path = out_dir / f"{spec.label}-color-pick-{safe_slug(sample['label'])}-swatches.png"
    image.save(path)
    return str(path)


def resize_for_zoom(image: Image.Image, scale: int) -> Image.Image:
    scale = max(1, int(scale))
    if scale == 1:
        return image.copy()
    return image.resize((image.width * scale, image.height * scale), Image.Resampling.NEAREST)


def make_zoom_artifacts(
    ref: Image.Image,
    cand: Image.Image,
    heatmap: Image.Image,
    overlay: Image.Image,
    max_delta: np.ndarray,
    spec: ViewportSpec,
    out_dir: Path,
    args: argparse.Namespace,
) -> list[dict[str, Any]]:
    zooms: list[dict[str, Any]] = []
    scale = max(1, int(args.zoom_scale))
    for rect in parse_zoom_rects(args.zoom_rect):
        label = safe_slug(rect["label"])
        ref_crop = crop_rect(ref, rect)
        cand_crop = crop_rect(cand, rect)
        heat_crop = crop_rect(heatmap, rect)
        overlay_crop = crop_rect(overlay, rect)
        if not ref_crop or not cand_crop or not heat_crop or not overlay_crop:
            zooms.append({"label": label, "rect": rect, "error": "rect outside screenshot bounds"})
            continue

        left = max(0, int(round(float(rect["x"]))))
        top = max(0, int(round(float(rect["y"]))))
        right = min(max_delta.shape[1], int(round(float(rect["x"]) + float(rect["width"]))))
        bottom = min(max_delta.shape[0], int(round(float(rect["y"]) + float(rect["height"]))))
        crop_delta = max_delta[top:bottom, left:right]
        crop_pixels = int(crop_delta.size)
        crop_mismatch = int((crop_delta > args.threshold).sum()) if crop_pixels else 0
        crop_mismatch_pct = (crop_mismatch / crop_pixels) * 100 if crop_pixels else 0.0

        prefix = f"{spec.label}-zoom-{label}"
        ref_path = out_dir / f"{prefix}-reference.png"
        cand_path = out_dir / f"{prefix}-candidate.png"
        heat_path = out_dir / f"{prefix}-heatmap.png"
        overlay_path = out_dir / f"{prefix}-overlay.png"
        side_path = out_dir / f"{prefix}-side-by-side.png"

        ref_zoom = resize_for_zoom(ref_crop, scale)
        cand_zoom = resize_for_zoom(cand_crop, scale)
        heat_zoom = resize_for_zoom(heat_crop, scale)
        overlay_zoom = resize_for_zoom(overlay_crop, scale)
        ref_zoom.save(ref_path)
        cand_zoom.save(cand_path)
        heat_zoom.save(heat_path)
        overlay_zoom.save(overlay_path)
        label_strip(
            [
                (f"Reference {label} x{scale}", ref_zoom),
                (f"Candidate {label} x{scale}", cand_zoom),
                (f"Heatmap {label} x{scale}", heat_zoom),
            ],
            args.background,
        ).save(side_path)

        zooms.append(
            {
                "label": label,
                "rect": {
                    "x": left,
                    "y": top,
                    "width": right - left,
                    "height": bottom - top,
                },
                "scale": scale,
                "mismatchPixels": crop_mismatch,
                "totalPixels": crop_pixels,
                "mismatchPercent": crop_mismatch_pct,
                "referenceMeanRgb": mean_rgb(ref_crop),
                "candidateMeanRgb": mean_rgb(cand_crop),
                "referenceImage": str(ref_path),
                "candidateImage": str(cand_path),
                "heatmapImage": str(heat_path),
                "overlayImage": str(overlay_path),
                "sideBySideImage": str(side_path),
            }
        )
    return zooms


def color_pick_rect_for_point(pick: dict[str, Any]) -> dict[str, Any]:
    radius = float(pick.get("radius") or 0)
    x = float(pick["x"])
    y = float(pick["y"])
    return {
        "label": pick["label"],
        "x": x - radius,
        "y": y - radius,
        "width": max(1.0, radius * 2 + 1),
        "height": max(1.0, radius * 2 + 1),
        "point": {"x": x, "y": y, "radius": radius},
    }


def make_color_pick_artifacts(
    ref: Image.Image,
    cand: Image.Image,
    spec: ViewportSpec,
    out_dir: Path,
    args: argparse.Namespace,
) -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []
    rects = [color_pick_rect_for_point(pick) for pick in parse_color_picks(args.color_pick)]
    rects.extend(parse_zoom_rects(args.color_pick_rect))
    for rect in rects:
        label = safe_slug(rect["label"])
        ref_crop = crop_rect(ref, rect)
        cand_crop = crop_rect(cand, rect)
        if not ref_crop or not cand_crop:
            samples.append({"label": label, "rect": rect, "error": "sample outside screenshot bounds"})
            continue
        left = max(0, int(round(float(rect["x"]))))
        top = max(0, int(round(float(rect["y"]))))
        right = min(ref.width, int(round(float(rect["x"]) + float(rect["width"]))))
        bottom = min(ref.height, int(round(float(rect["y"]) + float(rect["height"]))))
        sample = {
            "label": label,
            "rect": {"x": left, "y": top, "width": right - left, "height": bottom - top},
            "point": rect.get("point"),
            "quantum": max(1, min(255, int(args.color_pick_quantum))),
            "reference": image_color_summary(ref_crop, args.color_pick_top, args.color_pick_quantum),
            "candidate": image_color_summary(cand_crop, args.color_pick_top, args.color_pick_quantum),
        }
        swatch = make_color_swatch(sample, out_dir, spec, args.background)
        if swatch:
            sample["swatchImage"] = swatch
        samples.append(sample)
    return samples


def compare_images(reference_path: Path, candidate_path: Path, spec: ViewportSpec, out_dir: Path, args: argparse.Namespace) -> dict[str, Any]:
    ref_raw = Image.open(reference_path).convert("RGB")
    cand_raw = Image.open(candidate_path).convert("RGB")
    width = max(ref_raw.width, cand_raw.width)
    height = max(ref_raw.height, cand_raw.height)
    size = (width, height)

    ref = padded_rgb(reference_path, size, args.background)
    cand = padded_rgb(candidate_path, size, args.background)
    arr_ref = np.asarray(ref).astype(np.int16)
    arr_cand = np.asarray(cand).astype(np.int16)
    delta = np.abs(arr_ref - arr_cand)
    max_delta = delta.max(axis=2).astype(np.uint8)
    mask = max_delta > args.threshold
    total_pixels = width * height
    mismatch_pixels = int(mask.sum())
    mismatch_pct = (mismatch_pixels / total_pixels) * 100 if total_pixels else 0.0
    mae = float(delta.mean())
    rmse = float(math.sqrt(np.square(delta.astype(np.float64)).mean()))
    gray_ref = (arr_ref[..., 0] * 0.299 + arr_ref[..., 1] * 0.587 + arr_ref[..., 2] * 0.114).astype(np.uint8)
    gray_cand = (arr_cand[..., 0] * 0.299 + arr_cand[..., 1] * 0.587 + arr_cand[..., 2] * 0.114).astype(np.uint8)
    ssim = estimate_ssim(gray_ref, gray_cand)

    heatmap_path = out_dir / f"{spec.label}-heatmap.png"
    overlay_path = out_dir / f"{spec.label}-overlay.png"
    side_by_side_path = out_dir / f"{spec.label}-side-by-side.png"
    padded_reference_path = out_dir / f"{spec.label}-reference-padded.png"
    padded_candidate_path = out_dir / f"{spec.label}-candidate-padded.png"

    heatmap = make_heatmap(max_delta, args.threshold)
    overlay = make_overlay(cand, max_delta, args.threshold)
    zoom_artifacts = make_zoom_artifacts(ref, cand, heatmap, overlay, max_delta, spec, out_dir, args) if args.zoom_rect else []
    color_picks = make_color_pick_artifacts(ref, cand, spec, out_dir, args) if args.color_pick or args.color_pick_rect else []
    strip = label_strip(
        [
            ("Reference", ref),
            ("Candidate", cand),
            ("Heatmap", heatmap),
        ],
        args.background,
    )

    ref.save(padded_reference_path)
    cand.save(padded_candidate_path)
    heatmap.save(heatmap_path)
    overlay.save(overlay_path)
    strip.save(side_by_side_path)

    return {
        "referenceImage": str(reference_path),
        "candidateImage": str(candidate_path),
        "paddedReferenceImage": str(padded_reference_path),
        "paddedCandidateImage": str(padded_candidate_path),
        "heatmapImage": str(heatmap_path),
        "overlayImage": str(overlay_path),
        "sideBySideImage": str(side_by_side_path),
        "referenceSize": {"width": ref_raw.width, "height": ref_raw.height},
        "candidateSize": {"width": cand_raw.width, "height": cand_raw.height},
        "comparisonSize": {"width": width, "height": height},
        "sameSize": ref_raw.size == cand_raw.size,
        "threshold": args.threshold,
        "mismatchPixels": mismatch_pixels,
        "totalPixels": total_pixels,
        "mismatchPercent": mismatch_pct,
        "mae": mae,
        "rmse": rmse,
        "ssimEstimate": ssim,
        "zoomArtifacts": zoom_artifacts,
        "colorPicks": color_picks,
    }


def make_unmasked_side_by_side(
    reference_path: Path,
    candidate_path: Path,
    spec: ViewportSpec,
    out_dir: Path,
    args: argparse.Namespace,
) -> str:
    ref_raw = Image.open(reference_path).convert("RGB")
    cand_raw = Image.open(candidate_path).convert("RGB")
    size = (max(ref_raw.width, cand_raw.width), max(ref_raw.height, cand_raw.height))
    ref = padded_rgb(reference_path, size, args.background)
    cand = padded_rgb(candidate_path, size, args.background)
    path = out_dir / f"{spec.label}-side-by-side-unmasked.png"
    label_strip([("Reference unmasked", ref), ("Candidate unmasked", cand)], args.background).save(path)
    return str(path)


def rel(path: str | None, base: Path) -> str:
    if not path:
        return ""
    try:
        return os.path.relpath(path, base)
    except Exception:
        return path


def write_reports(report: dict[str, Any], out_dir: Path) -> None:
    json_path = out_dir / "report.json"
    md_path = out_dir / "report.md"
    html_path = out_dir / "report.html"
    report["reportJson"] = str(json_path)
    report["reportMarkdown"] = str(md_path)
    report["reportHtml"] = str(html_path)
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    md_lines = [
        "# Visual Diff Report",
        "",
        f"- Reference: {report['referenceUrl']}",
        f"- Candidate: {report['candidateUrl']}",
        f"- Created: {report['createdAt']}",
        f"- Output: `{out_dir}`",
        "",
        "| Viewport | Ref size | Candidate size | Mismatch | SSIM estimate | Same size |",
        "| --- | --- | --- | ---: | ---: | --- |",
    ]
    for item in report["viewports"]:
        diff = item["diff"]
        md_lines.append(
            f"| {item['label']} | {diff['referenceSize']['width']}x{diff['referenceSize']['height']} | "
            f"{diff['candidateSize']['width']}x{diff['candidateSize']['height']} | "
            f"{diff['mismatchPercent']:.4f}% | {diff['ssimEstimate']:.6f} | {diff['sameSize']} |"
        )
    md_lines.append("")
    for item in report["viewports"]:
        diff = item["diff"]
        md_lines.extend(
            [
                f"## {item['label']}",
                "",
                f"Side by side: `{diff['sideBySideImage']}`",
                "",
                f"![{item['label']} side by side]({rel(diff['sideBySideImage'], out_dir)})",
                "",
                f"Unmasked side by side: `{diff.get('unmaskedSideBySideImage', '')}`",
                "",
                f"![{item['label']} unmasked side by side]({rel(diff.get('unmaskedSideBySideImage'), out_dir)})",
                "",
                f"Heatmap: `{diff['heatmapImage']}`",
                "",
                f"![{item['label']} heatmap]({rel(diff['heatmapImage'], out_dir)})",
                "",
                f"Overlay: `{diff['overlayImage']}`",
                "",
                f"![{item['label']} overlay]({rel(diff['overlayImage'], out_dir)})",
                "",
            ]
        )
        for zoom in diff.get("zoomArtifacts", []):
            if zoom.get("error"):
                md_lines.extend([f"### Zoom: {zoom.get('label', '')}", "", f"Error: `{zoom['error']}`", ""])
                continue
            md_lines.extend(
                [
                    f"### Zoom: {zoom['label']}",
                    "",
                    f"Rect: `{zoom['rect']}`; scale: `{zoom['scale']}`; mismatch: `{zoom['mismatchPercent']:.4f}%`",
                    "",
                    f"Reference mean RGB: `{zoom['referenceMeanRgb']}`; candidate mean RGB: `{zoom['candidateMeanRgb']}`",
                    "",
                    f"Zoom side by side: `{zoom['sideBySideImage']}`",
                    "",
                    f"![{item['label']} {zoom['label']} zoom]({rel(zoom['sideBySideImage'], out_dir)})",
                    "",
                    f"Zoom overlay: `{zoom['overlayImage']}`",
                    "",
                    f"![{item['label']} {zoom['label']} overlay]({rel(zoom['overlayImage'], out_dir)})",
                    "",
                ]
            )
        for sample in diff.get("colorPicks", []):
            if sample.get("error"):
                md_lines.extend([f"### Color Pick: {sample.get('label', '')}", "", f"Error: `{sample['error']}`", ""])
                continue
            md_lines.extend(
                [
                    f"### Color Pick: {sample['label']}",
                    "",
                    f"Rect: `{sample['rect']}`; point: `{sample.get('point')}`; quantum: `{sample['quantum']}`",
                    "",
                    f"Reference mean/median: `{sample['reference'].get('meanHex')}` / `{sample['reference'].get('medianHex')}`",
                    "",
                    f"Candidate mean/median: `{sample['candidate'].get('meanHex')}` / `{sample['candidate'].get('medianHex')}`",
                    "",
                    f"Reference dominant: `{sample['reference'].get('dominantColors', [])}`",
                    "",
                    f"Candidate dominant: `{sample['candidate'].get('dominantColors', [])}`",
                    "",
                ]
            )
            if sample.get("swatchImage"):
                md_lines.extend(
                    [
                        f"Color swatches: `{sample['swatchImage']}`",
                        "",
                        f"![{item['label']} {sample['label']} color swatches]({rel(sample['swatchImage'], out_dir)})",
                        "",
                    ]
                )
        md_lines.extend(
            [
                f"Reference content: `{item['reference'].get('content', {}).get('json', '')}`",
                "",
                f"Candidate content: `{item['candidate'].get('content', {}).get('json', '')}`",
                "",
                f"Unmasked reference screenshot: `{item['reference'].get('unmaskedScreenshot', '')}`",
                "",
                f"Unmasked candidate screenshot: `{item['candidate'].get('unmaskedScreenshot', '')}`",
                "",
            ]
        )
    md_path.write_text("\n".join(md_lines), encoding="utf-8")

    rows = []
    sections = []
    for item in report["viewports"]:
        diff = item["diff"]
        rows.append(
            "<tr>"
            f"<td>{html.escape(item['label'])}</td>"
            f"<td>{diff['referenceSize']['width']}x{diff['referenceSize']['height']}</td>"
            f"<td>{diff['candidateSize']['width']}x{diff['candidateSize']['height']}</td>"
            f"<td>{diff['mismatchPercent']:.4f}%</td>"
            f"<td>{diff['ssimEstimate']:.6f}</td>"
            f"<td>{diff['sameSize']}</td>"
            "</tr>"
        )
        zoom_sections = []
        for zoom in diff.get("zoomArtifacts", []):
            if zoom.get("error"):
                zoom_sections.append(
                    f"""
                    <h3>Zoom: {html.escape(str(zoom.get('label', '')))}</h3>
                    <p><strong>Error:</strong> <code>{html.escape(str(zoom['error']))}</code></p>
                    """
                )
                continue
            zoom_sections.append(
                f"""
                <h3>Zoom: {html.escape(zoom['label'])}</h3>
                <p>Rect: <code>{html.escape(json.dumps(zoom['rect']))}</code>; scale:
                <code>{zoom['scale']}</code>; mismatch: <code>{zoom['mismatchPercent']:.4f}%</code></p>
                <p>Reference mean RGB: <code>{html.escape(json.dumps(zoom['referenceMeanRgb']))}</code>;
                candidate mean RGB: <code>{html.escape(json.dumps(zoom['candidateMeanRgb']))}</code></p>
                <img src="{html.escape(rel(zoom['sideBySideImage'], out_dir))}" alt="{html.escape(item['label'])} {html.escape(zoom['label'])} zoom">
                <h4>Zoom overlay</h4>
                <img src="{html.escape(rel(zoom['overlayImage'], out_dir))}" alt="{html.escape(item['label'])} {html.escape(zoom['label'])} overlay">
                """
            )
        color_sections = []
        for sample in diff.get("colorPicks", []):
            if sample.get("error"):
                color_sections.append(
                    f"""
                    <h3>Color Pick: {html.escape(str(sample.get('label', '')))}</h3>
                    <p><strong>Error:</strong> <code>{html.escape(str(sample['error']))}</code></p>
                    """
                )
                continue
            swatch_html = ""
            if sample.get("swatchImage"):
                swatch_html = f'<img src="{html.escape(rel(sample["swatchImage"], out_dir))}" alt="{html.escape(item["label"])} {html.escape(sample["label"])} color swatches">'
            color_sections.append(
                f"""
                <h3>Color Pick: {html.escape(sample['label'])}</h3>
                <p>Rect: <code>{html.escape(json.dumps(sample['rect']))}</code>; point:
                <code>{html.escape(json.dumps(sample.get('point')))}</code>; quantum:
                <code>{sample['quantum']}</code></p>
                <p>Reference mean/median: <code>{html.escape(str(sample['reference'].get('meanHex')))}</code> /
                <code>{html.escape(str(sample['reference'].get('medianHex')))}</code></p>
                <p>Candidate mean/median: <code>{html.escape(str(sample['candidate'].get('meanHex')))}</code> /
                <code>{html.escape(str(sample['candidate'].get('medianHex')))}</code></p>
                <details open><summary>Dominant colors</summary>
                  <p>Reference: <code>{html.escape(json.dumps(sample['reference'].get('dominantColors', [])))}</code></p>
                  <p>Candidate: <code>{html.escape(json.dumps(sample['candidate'].get('dominantColors', [])))}</code></p>
                </details>
                {swatch_html}
                """
            )
        sections.append(
            f"""
            <section>
              <h2>{html.escape(item['label'])}</h2>
              <h3>Side by side</h3>
              <img src="{html.escape(rel(diff['sideBySideImage'], out_dir))}" alt="{html.escape(item['label'])} side by side">
              <h3>Unmasked side by side</h3>
              <img src="{html.escape(rel(diff.get('unmaskedSideBySideImage'), out_dir))}" alt="{html.escape(item['label'])} unmasked side by side">
              <h3>Heatmap</h3>
              <img src="{html.escape(rel(diff['heatmapImage'], out_dir))}" alt="{html.escape(item['label'])} heatmap">
              <h3>Overlay</h3>
              <img src="{html.escape(rel(diff['overlayImage'], out_dir))}" alt="{html.escape(item['label'])} overlay">
              {''.join(zoom_sections)}
              {''.join(color_sections)}
              <h3>Content snapshots</h3>
              <ul>
                <li>Reference JSON: <code>{html.escape(rel(item['reference'].get('content', {}).get('json'), out_dir))}</code></li>
                <li>Reference text: <code>{html.escape(rel(item['reference'].get('content', {}).get('text'), out_dir))}</code></li>
                <li>Reference HTML: <code>{html.escape(rel(item['reference'].get('content', {}).get('html'), out_dir))}</code></li>
                <li>Unmasked reference screenshot: <code>{html.escape(rel(item['reference'].get('unmaskedScreenshot'), out_dir))}</code></li>
                <li>Candidate JSON: <code>{html.escape(rel(item['candidate'].get('content', {}).get('json'), out_dir))}</code></li>
                <li>Candidate text: <code>{html.escape(rel(item['candidate'].get('content', {}).get('text'), out_dir))}</code></li>
                <li>Candidate HTML: <code>{html.escape(rel(item['candidate'].get('content', {}).get('html'), out_dir))}</code></li>
                <li>Unmasked candidate screenshot: <code>{html.escape(rel(item['candidate'].get('unmaskedScreenshot'), out_dir))}</code></li>
              </ul>
            </section>
            """
        )

    html_doc = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Visual Diff Report</title>
  <style>
    body {{ margin: 24px; font: 14px/1.45 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; color: #111; background: #f6f6f6; }}
    code {{ background: #eee; padding: 2px 4px; border-radius: 4px; }}
    table {{ border-collapse: collapse; width: 100%; background: white; margin: 16px 0 28px; }}
    th, td {{ border: 1px solid #ddd; padding: 8px 10px; text-align: left; }}
    th {{ background: #191919; color: white; }}
    section {{ margin: 28px 0; padding: 18px; background: white; border: 1px solid #ddd; }}
    img {{ display: block; width: 100%; max-width: none; height: auto; border: 1px solid #ccc; background: white; }}
  </style>
</head>
<body>
  <h1>Visual Diff Report</h1>
  <p><strong>Reference:</strong> {html.escape(report['referenceUrl'])}</p>
  <p><strong>Candidate:</strong> {html.escape(report['candidateUrl'])}</p>
  <p><strong>Created:</strong> {html.escape(report['createdAt'])}</p>
  <p><strong>Output:</strong> <code>{html.escape(str(out_dir))}</code></p>
  <table>
    <thead><tr><th>Viewport</th><th>Reference</th><th>Candidate</th><th>Mismatch</th><th>SSIM</th><th>Same size</th></tr></thead>
    <tbody>{''.join(rows)}</tbody>
  </table>
  {''.join(sections)}
</body>
</html>
"""
    html_path.write_text(html_doc, encoding="utf-8")


def device_specs(playwright: Any, names: list[str]) -> list[tuple[ViewportSpec, dict[str, Any]]]:
    specs = []
    for name in names:
        if name not in playwright.devices:
            available = ", ".join(sorted(playwright.devices.keys())[:20])
            raise ValueError(f"Unknown device '{name}'. Example available devices: {available}")
        device = dict(playwright.devices[name])
        viewport = device.get("viewport") or {"width": 390, "height": 844}
        dpr = float(device.get("device_scale_factor", 1))
        specs.append(
            (
                ViewportSpec(
                    label=safe_slug(name),
                    width=int(viewport["width"]),
                    height=int(viewport["height"]),
                    dpr=dpr,
                    device_name=name,
                ),
                device,
            )
        )
    return specs


def main() -> int:
    args = parse_args()
    out_dir = Path(args.out).expanduser().resolve() if args.out else default_output_dir()
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.viewport:
        viewport_specs = [parse_viewport(v) for v in args.viewport]
    elif args.device:
        viewport_specs = []
    else:
        viewport_specs = [parse_viewport(v) for v in DEFAULT_VIEWPORTS]
    report: dict[str, Any] = {
        "createdAt": dt.datetime.now(dt.timezone.utc).isoformat(),
        "referenceUrl": args.reference,
        "candidateUrl": args.candidate,
        "outputDir": str(out_dir),
        "fullPage": not args.viewport_only,
        "settings": {
            "waitUntil": args.wait_until,
            "waitMs": args.wait_ms,
            "lazyScroll": args.lazy_scroll,
            "lazyScrollStep": args.lazy_scroll_step,
            "lazyScrollWaitMs": args.lazy_scroll_wait_ms,
            "lazyScrollImageTimeoutMs": args.lazy_scroll_image_timeout_ms,
            "timeoutMs": args.timeout_ms,
            "navigationRetries": args.navigation_retries,
            "captureRetries": args.capture_retries,
            "allowNavigationError": args.allow_navigation_error,
            "referenceImageDir": args.reference_image_dir,
            "candidateImageDir": args.candidate_image_dir,
            "threshold": args.threshold,
            "dismissCycles": args.dismiss_cycles,
            "dismissWaitMs": args.dismiss_wait_ms,
            "colorScheme": args.color_scheme,
            "locale": args.locale,
            "timezone": args.timezone,
            "storageState": args.storage_state,
            "referenceStorageState": args.reference_storage_state,
            "candidateStorageState": args.candidate_storage_state,
            "screenshotScale": args.screenshot_scale,
            "dismissSelectors": args.dismiss,
            "dismissText": args.dismiss_text,
            "waitForSelectors": args.wait_for,
            "waitForText": args.wait_for_text,
            "referenceWaitForSelectors": args.reference_wait_for,
            "referenceWaitForText": args.reference_wait_for_text,
            "candidateWaitForSelectors": args.candidate_wait_for,
            "candidateWaitForText": args.candidate_wait_for_text,
            "waitForTimeoutMs": args.wait_for_timeout_ms,
            "failOnWaitTimeout": args.fail_on_wait_timeout,
            "hoverSelectors": args.hover,
            "referenceHoverSelectors": args.reference_hover,
            "candidateHoverSelectors": args.candidate_hover,
            "hoverWaitMs": args.hover_wait_ms,
            "hoverStabilityProbeSelectors": args.hover_stability_probe,
            "hoverStabilityMs": args.hover_stability_ms,
            "scrollY": args.scroll_y,
            "referenceScrollY": args.reference_scroll_y,
            "candidateScrollY": args.candidate_scroll_y,
            "scrollWaitMs": args.scroll_wait_ms,
            "hideSelectors": args.hide,
            "maskSelectors": args.mask,
            "maskRects": args.mask_rect,
            "clipSelector": args.clip_selector,
            "referenceClipSelector": args.reference_clip_selector,
            "candidateClipSelector": args.candidate_clip_selector,
            "zoomRects": args.zoom_rect,
            "zoomScale": args.zoom_scale,
            "colorPicks": args.color_pick,
            "colorPickRects": args.color_pick_rect,
            "colorPickTop": args.color_pick_top,
            "colorPickQuantum": args.color_pick_quantum,
            "freezeAnimations": args.freeze_animations,
        },
        "viewports": [],
    }

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        all_specs: list[tuple[ViewportSpec, dict[str, Any] | None]] = [(spec, None) for spec in viewport_specs]
        all_specs.extend(device_specs(playwright, args.device))
        for spec, device in all_specs:
            print(f"Capturing {spec.label} ({spec.width}x{spec.height}@{spec.dpr:g})", flush=True)
            if args.reference_image_dir:
                reference = image_only_capture(spec, "reference", args.reference_image_dir, out_dir, args.reference)
            else:
                reference = capture_page(browser, args.reference, spec, "reference", out_dir, args, device=device)

            if args.candidate_image_dir:
                candidate = image_only_capture(spec, "candidate", args.candidate_image_dir, out_dir, args.candidate)
            else:
                candidate = capture_page(browser, args.candidate, spec, "candidate", out_dir, args, device=device)
            diff = compare_images(Path(reference["screenshot"]), Path(candidate["screenshot"]), spec, out_dir, args)
            if reference.get("unmaskedScreenshot") and candidate.get("unmaskedScreenshot"):
                diff["unmaskedSideBySideImage"] = make_unmasked_side_by_side(
                    Path(reference["unmaskedScreenshot"]),
                    Path(candidate["unmaskedScreenshot"]),
                    spec,
                    out_dir,
                    args,
                )
            report["viewports"].append(
                {
                    "label": spec.label,
                    "width": spec.width,
                    "height": spec.height,
                    "dpr": spec.dpr,
                    "deviceName": spec.device_name,
                    "reference": reference,
                    "candidate": candidate,
                    "diff": diff,
                }
            )
        browser.close()

    write_reports(report, out_dir)

    worst = max((item["diff"]["mismatchPercent"] for item in report["viewports"]), default=0.0)
    print(f"Visual diff report: {out_dir / 'report.html'}")
    print(f"JSON report: {out_dir / 'report.json'}")
    print(f"Worst mismatch: {worst:.4f}%")

    if args.max_mismatch is not None and worst > args.max_mismatch:
        print(f"Worst mismatch exceeds --max-mismatch {args.max_mismatch:.4f}%", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
