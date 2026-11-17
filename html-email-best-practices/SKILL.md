---
name: html-email-best-practices
description: Build and review HTML email, using compatibility workarounds only where the target email clients need them.
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

## Workflow

Project structure should look like the following:
`[root folder]/`
      `email.html`
      `context/`
          `assets/`
          `source-assets/`
          README.md (optional)
      `email-client-renders/`

`email.html` is the html emailer. 
`email-client-renders/` should contain JUST images taken from EMailQA or Mailgun (the two things I might have a subscription to to render emails). email-client-renders should not include any json or other bs. Pictures should be labeled as simply as possible, like 'apple-mail-ios-light.png', 'gmail-ios-dark.png' etc. 
`/context` contains everything else -- the assets in the actual email like logos and images (the `assets/` folder), the original pdf/img mockups of the emails, any instruction files (as .txt), or exact image rgb values given as a file, etc. Essentially all the context necessary to make the emails.

Do NOT over-complicate the folder structure with a bunch of nested shit. Try to keep a single copy of the email-client-renders, and don't distinguish bewteen EmailQA or Mailgun, in folders or png names. Don't include '-emailqa' in the png, or any emailqa folders. Both should work the same for the same client.

If similar/analogous folders exist, rename & reshuffle to achieve this structure.

While images should be stored in /context/assets for reference, when we include them in the email, they should *always* be ABSOLUTE url's, hosted at henry-deutsch.com under /shared/finmark-partners/[email name]. The finmark-partners folder already exists there, so if you don't see it you're looking in the wrong place. Even for local development, use these absolute url's. Feel free to commit, push, and deply just your changes to those assets in development, so you can change those images in the emailer.

Always update the `email-client-renders` folder after edits so that email.html isn't out of sync with it. Use Mailgun or EmailQA to see how it'll look like in different email clients. However, these take a LONG ass time to render, so please use them sparingly. If you've finished a round of edits, immediately update email.html, tell the user you've done this so they can check themselves, and then you can start rendering these images so the user can test the html in the mean time. 

If given a pdf to re-create, fucking re-create it EXACTLY. Use /visual-diff and only accept 1% difference, if that. (Not in every browser obviously -- we know CSS is spotty for emails. I mean when you render the .html locally and everything is supported). ESPECIALLY things like font, font-size, and colors, should be exactly right.

## Compatibility Tips

- Use semantic HTML and ordinary CSS where the target clients support them. For broad legacy support, use presentation tables and inline essential styles; keep core content usable without media queries.
- Check classic Outlook for Windows separately from new Outlook and web/mobile Outlook. Use VML only when classic Outlook needs it for a background or button treatment.
- Keep JavaScript and web-only interactions out of delivered email. Use live text for copy and linked table-cell buttons when required for client support.
