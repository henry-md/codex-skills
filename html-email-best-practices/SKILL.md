---
name: html-email-best-practices
description: Contains guidance on creating HTML emails, AND guidance on the folder structure & workflow I like to maintain with agents (you) when building HTML emails. Use this skill any time you're working with HTML emails.
---

# HTML email best practices

## Best Practices References

Make sure the following guides are always fully in your working memory. If any of them are not in context, and you're refactoring the code of an html email in any substantial way, read them before continuing.

- [Mailchimp: HTML email basics](https://templates.mailchimp.com/getting-started/html-email-basics/)
- [Litmus: accessible email guide](https://www.litmus.com/blog/ultimate-guide-accessible-emails)
- [Google: CSS support in Gmail](https://developers.google.com/workspace/gmail/design/css)
- [Microsoft: Outlook rendering](https://learn.microsoft.com/en-us/troubleshoot/dynamics-365/customer-insights/journeys/email/email-troubleshoot-rendering)
- [Can I Email](https://www.caniemail.com/)

## Things you (the agent) often get wrong that you need to check:

- When given a design to work off of, do not give something 'good enough'. On at least the web (where everythign is supported), it should look exactly the same -- fonts, colors, etc. If you don't have a font and you can't find it, flag this. Use the /visual-diff skill so that it's EXACTLY the same.
- Be very intentional about images -- you need to resize them and often downscale. Because if a client doesn't support styling, it may be blown back up to it's original size. If you can pre-process an image to do the same thing as code (to crop, for example), always pre-process. Nothing can go wrong then.
    - Every image needs an 'alt' attribute.
    - Some clients hide alt text that is too long to fit; keep descriptions concise and test with images blocked or deliberately broken URLs.
    - Make sure to still size an image appropriately with css. If the image doesn't render, you want to avoid the image being blown up as a square that doens't retain the original dimensions. Sizing images is most useful when the image doesn't render.
    - Check alt text. Sometimes it doesn't show up because the alt text is too long
- Make sure that your html is good practice. This means spacing is developer-friendly and conventional. It shouldn't look like a minified file.
- Check that all links are valid. If any recieve an error, either delete the link or flag to the user and do not stop flagging until it's addressed. 

# Workflow

Project structure should look like the following:
`[root folder]/`
      `email.html`
      `reference.pdf`
      `bug-fixes.md`
      `context/`
          `assets/`
          `source-assets/`
          README.md (optional)
      `email-client-renders/`

`email.html` is the html emailer. `reference.pdf` is the original pdf/img mockups of the emails. `bug-fixes.md` is written documentation of every UI bug found. If addressed, it should have before & after pictures showing a reproduction of the bug, and the fix. We can also choose not to address it, with a justification of why fixing this bug produces comparable or worse bugs in this or other clients. The before & after images should be the same client type (ex Outlook dark mode mobile) that I give Codex when I tell it about the bug.

`email-client-renders/` should contain JUST images taken from EmailQA, our hosted email rendering service. email-client-renders should not include any json or other bs. Pictures should be labeled as simply as possible, like 'apple-mail-ios-light.png', 'gmail-ios-dark.png' etc.
`/context` contains everything else -- the assets in the actual email like logos and images (the `assets/` folder), the original pdf/img mockups of the emails, any instruction files (as .txt), or exact image rgb values given as a file, etc. Essentially all the context necessary to make the emails.

Do NOT over-complicate the folder structure with a bunch of nested folders. Keep a single copy of email-client-renders with simple filenames identifying the client and mode. Keep rendering-service names out of PNG filenames and folders, including EmailQA. Clients may receive this folder, so the names should describe the email client and mode.

If similar/analogous folders exist, rename & reshuffle to achieve this structure.

While images should be stored in /context/assets for reference, when we include them in the email, they should *always* be ABSOLUTE url's, hosted at henry-deutsch.com under /shared/finmark-partners/[email name]. The finmark-partners folder already exists there, so if you don't see it you're looking in the wrong place. Even for local development, use these absolute url's. Feel free to commit, push, and deply just your changes to those assets in development, so you can change those images in the emailer.

If given a pdf to re-create, fucking re-create it EXACTLY. Use /visual-diff and only accept 1% difference, if that. (Not in every browser obviously -- we know CSS is spotty for emails. I mean when you render the .html locally and everything is supported). ESPECIALLY things like font, font-size, and colors, should be exactly right.

## Re-rendering email clients

Always update the `email-client-renders` folder after edits so that email.html isn't out of sync with it.


Prefer the [local preview workflow](local-preview/GUIDE.md) for focused debugging when Gmail web, Outlook.com web or Apple Mail for Mac reproduces the issue. It provides 2 main advantages over EmailQA for rendering: (1) it's fast. In benchmarks, you get previews in around 3-5 seconds as opposed to 30 seconds - 1 minute for EmailQA. (2) You get access to the DOM! Not just screenshots. This should help a lot with debugging in certain situations, so you can actually see which element is taking some padding we want to delete, for example.

(Windows clients in the local preview workflow are not implemented yet for this Mac's local setup, and are deferred until there's 100GB of free memory for a VM download.)

When you've finished a coding pass, tell the user immediately that you've finished, and that the html clients will re-render. Immediately after doing this, rename all existing image previews with '...-old.png' in email-client-renders. As the new emails come in, overwrite those. This way, the user can easily see which have been replaced so far, and which are still old.

### Local edit loop for development & bugs

1. Inspect the existing captures and inspection evidence, checking which HTML revision they represent. Refresh stale or unknown revisions before establishing a bug reproducer. Choose the fastest verified local configuration that reproduces the defect or covers the feature, considering its measured spread; use the [EmailQA benchmark](local-preview/GUIDE.md#saved-code-to-feedback-benchmark) for measured hosted targets and confirm other targets against EmailQA's current client catalog. Follow an explicit client requirement and keep app, platform, device, account type and light/dark mode fixed. For bugs, save current before images in `context/`, covering both the iteration target and the reported target when they differ.
2. Keep the chosen client open/signed in. Edit and save `email.html`, then run [preview.py](local-preview/preview.py) `prepare --html /absolute/path/to/email.html --clients CLIENT` for a local target. Each edit needs a fresh frozen source and uniquely identified `message.eml`; reuse the authorized setup and helpers between revisions.
3. Use the chosen client's verified loading route. **Gmail:** [insert the complete message into the test mailbox](local-preview/GUIDE.md#gmail-web) with the existing insertion-only authorization, open the returned native message ID and use `inspectInsertedGmail`. **Outlook.com:** [pass the saved message bytes to `openOutlookEML`](local-preview/GUIDE.md#outlook-web), which invokes Outlook's native file-reading handler, then inspect its popup with `inspectOpenedOutlook`. **Apple Mail:** [open the saved `.eml` through Finder](local-preview/GUIDE.md#apple-mail-for-mac), rebind the Mail app handle and inspect that new window. The tested Outlook automation uses its native drop handler; Finder-to-browser dragging failed here.
4. Verify the current unique subject/message identity, source hash, loaded assets and complete ending. Inspect only that message's DOM in Gmail/Outlook, using the existing inspectors and Chrome DevTools to locate the cause of the defect. In Mail, use accessibility data and native images. Check the actual defect or feature behavior; a prepared file or successful request alone is insufficient. Repeat source edits and reload only the chosen reproducing client during intermediate iterations.
5. Before claiming a bug is fixed, reload the current code in the originally reported client/mode, including when it differs from the iteration target, and take an after screenshot. Before/after screenshots from the same client configuration are mandatory: give them to the user and retain them in `context/` for `bug-fixes.md`. Then complete the final client verification below.

### Final client verification

Use a single client for quick iterations. Once the fix or feature works in that target and any originally reported client/mode, render the full agreed client/mode set in EmailQA once to catch regressions. Select targets from EmailQA's current catalog; client IDs and mode availability are provider-specific. Call the render folder current only after all required views have been refreshed, and report any unavailable or failed views.

### Maintaining the EmailQA account

- Keep exactly one EmailQA project per local email project folder under the HTML email workspace. For example, `finmark-emailers/north-square-1/` maps to one EmailQA project named `north-square-1`. Reuse that project across chats, HTML revisions, diagnostic variants and client selections.
- Before creating a project, check the local `context/` records for its saved EmailQA slug/URL, then search EmailQA's existing projects and inspect likely matches. Record the chosen project's slug/URL and corresponding local folder in `context/` so later agents reuse it. Create a project only when no matching project exists.
- Upload changed HTML as a new version of that same project. Keep baseline, candidate, diagnostic and regression renders in its version/render history, and submit each render job against the intended version. For final verification, upload the actual current `email.html` and record its source hash, version and render job IDs in `context/`.
- With the [existing EmailQA integration](/Users/Henry/.codex/integrations/emailqa/render.py), always pass `--project EXISTING_SLUG` after initial project creation. Omitting `--project` creates another project. Select the required client IDs/modes from EmailQA's current catalog and check the included allowance before submitting.
- Poll intermediate per-client results and download each completed image immediately, even while the overall job is processing. Keep job metadata and timings in `context/`, and place only client/mode-named PNGs in `email-client-renders/`.

## Compatibility Tips

- Use semantic HTML and ordinary CSS where the target clients support them. For broad legacy support, use presentation tables and inline essential styles; keep core content usable without media queries.
- Check classic Outlook for Windows separately from new Outlook and web/mobile Outlook. Use VML only when classic Outlook needs it for a background or button treatment.
- Keep JavaScript and web-only interactions out of delivered email. Use live text for copy and linked table-cell buttons when required for client support.
