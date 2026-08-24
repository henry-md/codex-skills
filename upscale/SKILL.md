---
name: upscale
description: AI-upscale one or more repository images and swap them into the original asset paths while preserving the prior files as *_orig backups. Use when the user invokes $upscale or asks to upscale repo/site images with OpenAI/API image editing so the running app immediately shows the improved images under the same filenames.
---

# Upscale

## Overview

Use this skill to AI-upscale specified repository images in place. Keep the old images in the repo by renaming each original from `name.ext` to `name_orig.ext`, then save the upscaled result back to `name.ext` so existing code, manifests, and browser tabs immediately reference the improved asset.

## Workflow

1. Resolve every requested image path to an existing repo file.
   - Refuse ambiguous paths until the exact source files are identified.
   - Do not upscale backup files that already end in `_orig`.
   - If `name_orig.ext` already exists, stop for that file unless the user explicitly authorizes overwriting or choosing a different backup suffix.

2. Confirm the work is intentionally AI/API-based if the user did not explicitly say so.
   - This skill is for OpenAI/API-style image upscaling, not local-only resizing.
   - If cost or authorization is unclear, ask once before making image-generation/editing calls.

3. Generate each upscaled image into a temporary path first.
   - Use one source image per AI image request.
   - Preserve the original composition, crop, text, logos, transparency, and file role unless the user gives different prompt instructions.
   - Prefer a prompt like: `Upscale this image for a production website asset. Preserve exact layout, text, logos, crop, colors, transparency, and aspect ratio. Reduce compression artifacts and improve sharpness without changing the design.`
   - Include any user-specified prompt verbatim unless it conflicts with preservation requirements.

4. Multi-thread independent image requests.
   - Run multiple image-generation/editing requests concurrently when the available tools support parallel calls or subagents.
   - Still send only one source image in each request.
   - If the current tool surface cannot parallelize image generation safely, process sequentially and state that limitation.

5. Swap files only after all requested upscaled images exist and have been sanity-checked.
   - Use `scripts/swap_upscaled_images.py` for the rename/move step.
   - Pass one `--pair original=generated` argument per image.
   - The script renames each original to `*_orig.ext` and moves the generated file into the original path.

6. Verify the result in the product.
   - Run the repo's relevant checks.
   - For visible site assets, refresh or open the affected route in a browser and inspect a screenshot.
   - Report the final original paths, backup paths, and any verification caveats.

## Swap Helper

Run from any working directory:

```bash
python3 /Users/Henry/.codex/skills/upscale/scripts/swap_upscaled_images.py \
  --pair /repo/public/images/a.png=/tmp/upscale/a.png \
  --pair /repo/public/images/b.png=/tmp/upscale/b.png
```

This changes:

```text
/repo/public/images/a.png      -> /repo/public/images/a_orig.png
/tmp/upscale/a.png             -> /repo/public/images/a.png
/repo/public/images/b.png      -> /repo/public/images/b_orig.png
/tmp/upscale/b.png             -> /repo/public/images/b.png
```

Use `--dry-run` before the real swap when the list is long or the repo has a messy working tree.

## Safety Rules

- Never delete the original image.
- Never overwrite an existing `_orig` backup without explicit user permission.
- Never change code references when the same filename swap is sufficient.
- Keep generated temporary files outside the repo unless the user asks to retain them.
- If a swap partly fails, use the helper's rollback output before continuing.
