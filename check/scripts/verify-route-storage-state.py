#!/usr/bin/env python3
import asyncio
import os
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

from playwright.async_api import async_playwright


async def main() -> None:
    if len(sys.argv) < 3:
        raise SystemExit(
            "Usage: verify-route-storage-state.py <stateFile> <targetUrl> "
            "[requiredTextRegex] [forbiddenTextRegex]"
        )

    state_file = Path(sys.argv[1])
    target_url = sys.argv[2]
    required_pattern = sys.argv[3] if len(sys.argv) > 3 else ""
    forbidden_pattern = sys.argv[4] if len(sys.argv) > 4 else ""

    if not state_file.exists():
        raise SystemExit(f"Storage state does not exist: {state_file}")

    required_regex = re.compile(required_pattern, re.I) if required_pattern else None
    forbidden_regex = re.compile(forbidden_pattern, re.I) if forbidden_pattern else None

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            context = await browser.new_context(storage_state=str(state_file))
            page = await context.new_page()
            await page.goto(target_url, wait_until="domcontentloaded", timeout=30000)
            try:
                await page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                pass
            await page.wait_for_timeout(750)

            current_url = page.url
            body_text = ""
            try:
                body_text = await page.locator("body").inner_text(timeout=10000)
            except Exception:
                pass

            pathname = urlparse(current_url).path
            if pathname in {"/signin", "/signup"}:
                raise SystemExit(f"Storage state redirected to auth page: {current_url}")

            if forbidden_regex and forbidden_regex.search(body_text):
                raise SystemExit(f"Storage state reached forbidden auth text at {current_url}")

            if required_regex and not required_regex.search(body_text):
                raise SystemExit(f"Storage state did not reach required text at {current_url}")
        finally:
            await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
