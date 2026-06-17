---
name: visual-diff
description: Capture and compare visual screenshots between a public reference URL and a local or deployed candidate URL. Use when cloning an existing site pixel-for-pixel, validating responsive similarity, generating screenshot heatmaps, comparing public-vs-local pages, auditing exactness across desktop/mobile/tablet screen sizes, or showing the user visual diff artifacts.
---

# Visual Diff

## Overview

Use this skill when a site or app must look exactly like an existing public URL. It captures matched reference/candidate screenshots, generates heatmaps and overlay diffs, reports mismatch metrics, and saves preview-ready artifacts for user inspection.

## Standard Workflow

1. Define the reference URL and candidate URL.
   - Reference is usually the public site, such as `https://vincentdunn.com/`.
   - Candidate is usually the local dev server, such as `http://127.0.0.1:3000/`.

2. Normalize the capture environment.
   - Use the same browser, viewport, device scale, color scheme, locale, waits, and scroll behavior for both URLs.
   - Dismiss or mask popups, cookie banners, carousels, embedded videos, timestamps, and other unstable regions.
   - Prefer `domcontentloaded` plus a fixed wait for sites that never reach `networkidle`.

3. Run the bundled comparer.

```bash
/Users/Henry/.codex/skills/visual-diff/scripts/compare-page.sh \
  --reference "https://example.com/" \
  --candidate "http://127.0.0.1:3000/" \
  --viewport "desktop:1280x720" \
  --viewport "mobile:390x844" \
  --dismiss-text "ACCEPT" \
  --dismiss 'svg[id$="-close-icon"]'
```

4. Inspect the artifacts directly.
   - Open `side-by-side.png`, `heatmap.png`, and `overlay.png` with `view_image`.
   - Show the user the most useful images inline with Markdown image tags using absolute paths.
   - Do not claim exactness from metrics alone; visually inspect the screenshots.

5. Iterate the candidate implementation until the unmasked differences are intentionally small.
   - For an exact clone, treat layout, typography, image assets, spacing, scroll height, colors, and responsive breakpoints as first-class requirements.
   - If the local app differs because of missing assets or fonts, fetch or recreate those assets before tuning CSS.

## Output Contract

The comparer writes into this skill by default:

```text
visual-diff/repos/<repo-key>/runs/<timestamp>/
  report.html
  report.md
  report.json
  <viewport>-reference.png
  <viewport>-candidate.png
  <viewport>-reference-unmasked.png
  <viewport>-candidate-unmasked.png
  <viewport>-heatmap.png
  <viewport>-overlay.png
  <viewport>-side-by-side.png
  <viewport>-reference-dom.json
  <viewport>-candidate-dom.json
  <viewport>-reference-content.json
  <viewport>-candidate-content.json
  <viewport>-reference-text.txt
  <viewport>-candidate-text.txt
  <viewport>-reference.html
  <viewport>-candidate.html
```

When reporting results, include:

- Reference URL, candidate URL, and all viewport specs checked.
- The run directory and report path.
- Inline preview images for side-by-side and heatmap/overlay artifacts.
- Mismatch percentage, SSIM estimate, screenshot dimensions, and any masks/dismissals used.
- When masks are used, use `*-unmasked.png` for human-facing screenshots of the real pages and masked `side-by-side`/`heatmap` artifacts for diagnostic comparison.
- A clear callout for remaining uncertainty, such as third-party iframes, animations, late-loading assets, auth, or network variance.

## CLI Notes

`scripts/compare-page.sh` passes arguments to `scripts/compare_page.py`.

Useful options:

- `--viewport "name:WIDTHxHEIGHT"` or `--viewport "name:WIDTHxHEIGHT@DPR"`.
- `--device "iPhone 13"` for a Playwright device profile.
- `--viewport-only` to compare only the first viewport instead of full-page screenshots.
- `--reference-image-dir path/to/run` to use pre-captured `<viewport>-reference.png` screenshots instead of navigating the reference URL.
- `--candidate-image-dir path/to/run` to use pre-captured `<viewport>-candidate.png` screenshots instead of navigating the candidate URL.
- `--dismiss SELECTOR` to click a selector on both pages before capture.
- `--dismiss-text TEXT` to click visible text on both pages before capture.
- `--dismiss-cycles 5` and `--dismiss-wait-ms 700` to repeat dismissals when closing one overlay reveals another, such as a promo modal followed by a cookie banner.
- `--wait-for SELECTOR` and `--wait-for-text TEXT` to require route-specific hydrated content before capture, such as a product title inside a late-loading store widget.
- Use `--reference-wait-for-text TEXT` or `--reference-wait-for SELECTOR` when only the public reference needs a hydration wait, especially when the candidate is a screenshot-backed static clone whose text is inside an image rather than DOM.
- Add `--fail-on-wait-timeout` for exact clone checks so missing hydration targets abort the run instead of producing screenshots of loading states.
- `--hover SELECTOR`, `--reference-hover SELECTOR`, or `--candidate-hover SELECTOR` to move the cursor over a matching element before capture; use `--hover-wait-ms` when hover animations need extra settle time.
- `--hover-stability-probe SELECTOR --hover-stability-ms 700` to record whether a hovered animated element kept the same position and transform before the screenshot.
- `--scroll-y 160`, `--reference-scroll-y 160`, or `--candidate-scroll-y 160` to compare a page after scrolling; use `--scroll-wait-ms` to let sticky headers or scroll-triggered transitions settle.
- `--lazy-scroll` to scroll through a full page before screenshot capture, trigger lazy-loaded images/iframes, wait for image completion/decode, and return to the top. Use this for exact clone checks unless the page is intentionally viewport-only.
- `--mask SELECTOR` to fill selector bounding boxes with a neutral color before comparison.
- `--mask-rect x,y,w,h` to mask a fixed screenshot rectangle.
- `--zoom-rect label:x,y,w,h` to write magnified reference/candidate/heatmap/overlay crop artifacts for a specific screenshot rectangle; repeatable. Pair with `--zoom-scale 6` or similar when inspecting small details such as icons, star ratings, and text anti-aliasing.
- `--color-pick label:x,y[,radius]` to sample exact reference/candidate colors at a screenshot point, optionally averaging a square radius around it. Repeatable.
- `--color-pick-rect label:x,y,w,h` to sample a screenshot rectangle and report sorted dominant color bins, mean/median RGB/hex values, and a swatch artifact. Tune `--color-pick-top` and `--color-pick-quantum` when matching small assets.
- `--clip-selector SELECTOR` to compare only one component region after all waits, dismissals, hovers, and lazy-load preparation; use role-specific `--reference-clip-selector` or `--candidate-clip-selector` when selectors differ.
- `--freeze-animations` to pause CSS animations/transitions and make marquees, tickers, and other animated surfaces deterministic.
- `--storage-state state.json` to reuse one Playwright storage state for both pages.
- `--reference-storage-state state.json` and `--candidate-storage-state state.json` when the two sides need different sessions.
- `--wait-until domcontentloaded --wait-ms 2000` for deterministic public-site captures.
- `--navigation-retries 2` to retry transient public-site timeouts before failing.
- Navigation failures are fatal by default; use `--allow-navigation-error` only when intentionally inspecting an error state.
- Use `--capture-retries N` with `--fail-on-wait-timeout` when a public widget intermittently hydrates into a loading state before eventually rendering the required content.
- `--max-mismatch 0.5` to return a non-zero exit code when mismatch exceeds the threshold.

Use `--reference-image-dir` after a successful live reference capture when a public site starts throttling or timing out during iterative clone work. Refresh the live reference again before making final claims whenever the public URL is reachable.

Repo-local helpers may exist under `visual-diff/repos/<repo-key>/` for repeated capture work. For the Vincent Dunn clone repo, `capture-reference-pages.sh` captures named public pages once per viewport, and `compare-vincentdunn-route.sh ROUTE RUN_NAME --viewport desktop:1440x900` compares a route with the right popup dismissal, lazy-load, route-specific waits, and iframe masks.

## Relationship To Check

Keep `$check` and `$visual-diff` separate but symbiotic.

- Use `$check` to prove a page is reachable from the correct account/session, seed or refresh auth, and capture a single visual proof.
- Use `$visual-diff` to compare two page renders, retrieve clone content, generate heatmaps, and iterate toward pixel exactness.
- When a diff requires authentication, let `$check` produce or verify the Playwright storage-state JSON, then pass it to `$visual-diff` with `--storage-state`, `--reference-storage-state`, or `--candidate-storage-state`.
- Do not copy `$check` account-selection, Henry-account safety, or auth-refresh logic into this skill. Visual diff may consume browser state, but `$check` should own how that state is created safely.

## Page Content Retrieval

Every capture writes page content artifacts for clone work:

- `*-content.json`: title, URL, canonical URL, language, meta tags, headings, links, images, media/iframes, stylesheets, scripts, and body text.
- `*-text.txt`: rendered body text for quick reading or copy reconstruction.
- `*.html`: post-load HTML snapshot from Playwright.

Use these artifacts to reconstruct copy, image inventories, link targets, embedded media, and stylesheet/script dependencies. Treat screenshots as the visual truth and content snapshots as the inventory that helps build the clone.

## Similarity Standards

For clone work, use metrics as gates and screenshots as proof:

- Pixel mismatch: useful for exactness, but sensitive to fonts, anti-aliasing, video, animations, and browser differences.
- SSIM estimate: useful for broad perceptual similarity, but it can hide small layout errors.
- Screenshot size: different width/height or scroll height is a serious clone mismatch unless intentionally masked.
- DOM audit: use generated `*-dom.json` files to compare visible text, fonts, colors, and element boxes.

Read `references/clone-quality.md` when setting pass/fail thresholds or diagnosing difficult mismatches.

## Self-Healing Rule

Treat this skill like `$check`: every real use is a chance to improve it.

If a run requires repeated manual setup, a missing normalization option, a fragile dismissal pattern, a better report format, a new dependency fallback, or a repo-specific workflow, patch this skill or add a minimal helper under `visual-diff/repos/<repo-key>/`. Prefer improving the global scripts when the lesson is reusable.

After using the skill, state whether you changed the skill or repo-local helpers so future visual-diff runs are faster and more exact.
