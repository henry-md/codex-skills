# Clone Quality Reference

## Recommended Gates

Use stricter gates as implementation stabilizes:

| Stage | Pixel mismatch | SSIM estimate | Use |
| --- | ---: | ---: | --- |
| Rough scaffold | under 20% | above 0.80 | Section order and major layout match |
| Close clone | under 5% | above 0.93 | Typography, spacing, colors mostly match |
| Pixel pass | under 0.5% | above 0.985 | Ready to call visually near-exact |
| Exact claim | under 0.1% | above 0.995 | Only after manual inspection and masking unstable regions |

Do not use these gates blindly. A 0.2% mismatch can still include a visible broken header, and a 10% mismatch can be harmless if it is a masked video player that failed to paint in headless Chromium.

## Capture Normalization Checklist

- Same viewport width, height, device scale factor, color scheme, locale, and browser.
- Same full-page versus viewport-only mode.
- Same initial scroll position.
- Same cookie/banner/popup state.
- Same reduced-motion or animation disabling when the reference allows it.
- Same auth/account state when comparing signed-in pages.
- Same externally hosted fonts and image assets loaded before capture.

## Common Mask Targets

- Cookie banners and promotional popups when comparing the underlying page.
- Video embeds, podcast players, iframes, maps, chat widgets, and ad slots.
- Carousels, marquees, animated counters, canvas animations, timestamps, carts, and notification badges.
- Content that is intentionally different between production and local, such as analytics consent copy.

Prefer masking unstable regions with selectors. Use fixed rectangles only when selectors are unavailable or generated markup is too unstable.

## Debugging Differences

- Header shifted: compare logo asset dimensions, nav font, line-height, and body margin.
- Page too tall/short: compare section padding, hidden mobile/desktop sections, iframe heights, and lazy-loaded images.
- Text wraps differently: compare font family availability, font weight, letter spacing, container width, and media breakpoints.
- Images differ: fetch the reference asset, match object-fit/object-position, and compare intrinsic dimensions.
- Colors differ: sample computed colors from the generated DOM audits and compare CSS variables.
- Diff is noisy everywhere: confirm screenshots use the same browser, DPR, color scheme, and anti-aliasing environment.

## Reporting

For clone tasks, show the user:

- Side-by-side screenshot for the most important viewport.
- Heatmap or overlay screenshot for the same viewport.
- Metrics table for every checked viewport.
- Explicit notes about masks, dismissed overlays, and non-deterministic regions.
