# Courier clients and render timings

Historical Courier reference from November 24, 2026. EmailQA is now the hosted rendering provider; follow the [current workflow](../SKILL.md#maintaining-the-emailqa-account). The catalog IDs, allowance rules and timings below apply to Courier and must not be used as EmailQA data.

The former Courier standard set covered completed emails and final regression passes. During focused bug fixing, only the fastest target that visibly reproduced the defect was rendered; the reported client remained required for final verification.

## Standard set

Twenty views cover ten client/platform combinations in light and dark mode. The exact catalog IDs and canonical PNG filenames are in [courier-standard-clients.json](courier-standard-clients.json). Confirm saved IDs and their client/platform/mode metadata against `GET /previews/devices` before using them. Flag unavailable targets; do not silently replace the client or theme.

| Client / platform | Filename stem | Modes |
| --- | --- | --- |
| Outlook Microsoft 365, Windows 11 | `outlook-m365-windows` | light, dark |
| Outlook for Windows, Windows 11 | `outlook-for-windows` | light, dark |
| Outlook Microsoft 365, macOS 13 | `outlook-m365-macos` | light, dark |
| Outlook.com, Chrome on Windows 10 | `outlook-web` | light, dark |
| Outlook, iPhone 13 / iOS 15 | `outlook-ios` | light, dark |
| Gmail.com, Chrome on Windows 10 | `gmail-web` | light, dark |
| Gmail, iPhone 16 / iOS 26 | `gmail-ios` | light, dark |
| Gmail, Pixel 10 / Android 16 | `gmail-android` | light, dark |
| Apple Mail 16, macOS 13 | `apple-mail-macos` | light, dark |
| Apple Mail, iPhone 17 / iOS 26 | `apple-mail-ios` | light, dark |

Append `-light.png` or `-dark.png` to each stem. If a download is WebP or JPEG, convert it to a real PNG without resizing; changing the extension alone is insufficient. Keep Microsoft 365 Windows, the separate Outlook for Windows app, Outlook web and Outlook mobile distinct. Use a fixed Outlook version such as 2024, another browser, or another device when the reported bug requires it. Those are additional regression targets, not silent replacements for the standard set.

The catalog supports other desktop, webmail and mobile configurations. This set is representative: it does not cover Outlook Android, Mac webmail, every browser, every OS version or every fixed Outlook release. The saved Outlook iOS and Mac targets use the versions shown above; do not label them as the newest OS.

## Preview allowance

Each client/mode view consumes one preview. A full standard pass uses 20; one focused client uses one per iteration. For example, Starter's $20/month allowance of 100 previews covers five full standard passes, not 100 passes. Check the account's current usage and tier before launching a batch. When refreshing this reference, retain measurements for unchanged targets and benchmark only missing or changed configurations unless a full repeat is needed.

## Timing reference

Measured on November 24, 2026 using the same 34,949-byte North Square email. Nineteen standard views retain their three measurements from the earlier 20-view batches, polled every two seconds. Gmail web dark was added afterward and measured in three single-client runs, polled every second. No additional full-matrix benchmark was run. Each row below has three successful samples.

Times are seconds from immediately before the render-run POST until the API response first exposed a completed screenshot. Template upload is excluded. Medians are sorted fastest first. These are observations from one email and session, not guaranteed latency; single-client runs and full batches can behave differently. Use the median and spread as a starting priority among clients that visibly reproduce the bug. Small differences near the polling interval are not meaningful.

| Canonical PNG | Run 1 | Run 2 | Run 3 | Median | Range |
| --- | ---: | ---: | ---: | ---: | --- |
| `outlook-ios-dark.png` | 34.6 | 22.5 | 24.5 | 24.5 | 22.5 to 34.6 |
| `outlook-m365-macos-light.png` | 30.5 | 24.5 | 24.5 | 24.5 | 24.5 to 30.5 |
| `outlook-ios-light.png` | 36.5 | 24.5 | 26.4 | 26.4 | 24.5 to 36.5 |
| `apple-mail-ios-light.png` | 36.5 | 26.5 | 24.5 | 26.5 | 24.5 to 36.5 |
| `apple-mail-ios-dark.png` | 34.6 | 26.5 | 26.4 | 26.5 | 26.4 to 34.6 |
| `outlook-m365-macos-dark.png` | 30.5 | 24.5 | 30.9 | 30.5 | 24.5 to 30.9 |
| `gmail-web-light.png` | 32.6 | 26.5 | 30.9 | 30.9 | 26.5 to 32.6 |
| `apple-mail-macos-light.png` | 34.6 | 22.5 | 30.9 | 30.9 | 22.5 to 34.6 |
| `outlook-web-light.png` | 32.6 | 46.5 | 30.9 | 32.6 | 30.9 to 46.5 |
| `apple-mail-macos-dark.png` | 34.6 | 28.7 | 38.5 | 34.6 | 28.7 to 38.5 |
| `gmail-android-dark.png` | 40.5 | 48.5 | 38.5 | 40.5 | 38.5 to 48.5 |
| `outlook-web-dark.png` | 34.6 | 50.5 | 40.5 | 40.5 | 34.6 to 50.5 |
| `gmail-web-dark.png` * | 44.4 | 47.4 | 35.4 | 44.4 | 35.4 to 47.4 |
| `outlook-m365-windows-light.png` | 44.7 | 48.5 | 48.5 | 48.5 | 44.7 to 48.5 |
| `gmail-android-light.png` | 38.4 | 48.5 | 50.5 | 48.5 | 38.4 to 50.5 |
| `outlook-m365-windows-dark.png` | 56.6 | 28.7 | 70.5 | 56.6 | 28.7 to 70.5 |
| `gmail-ios-light.png` | 78.5 | 48.5 | 58.6 | 58.6 | 48.5 to 78.5 |
| `outlook-for-windows-light.png` | 50.5 | 358.5 | 70.5 | 70.5 | 50.5 to 358.5 |
| `outlook-for-windows-dark.png` | 80.5 | 50.5 | 70.5 | 70.5 | 50.5 to 80.5 |
| `gmail-ios-dark.png` | 128.5 | 96.5 | 54.6 | 96.5 | 54.6 to 128.5 |

* Gmail web dark used three single-client runs. All other rows came from three earlier full-batch runs. Its local image downloads completed at 45.0, 47.8 and 36.0 seconds; other rows record API readiness, with downloads arriving afterward.

The observed quick group was Outlook Mac, Outlook iPhone, Apple Mail Mac/iPhone and Gmail web light. Gmail iPhone and Outlook for Windows had the longest delays. Dark mode was not consistently slower across clients. Choose a faster target only after its native capture visibly reproduces the same defect.

## Sources

- [Courier Device Preview and per-device API results](https://www.courier.com/docs/design/templates/device-preview)
- [Courier preview billing](https://www.courier.com/docs/workspaces/billing)
- Local evidence: `/Users/Henry/.codex/visualizations/2026/11/24/01a20bc3-c90f-7d91-ab5e-15e3b464e1e6/email-rendering-research/courier-paid-timing/results` and `/Users/Henry/.codex/visualizations/2026/11/24/01a20bc3-c90f-7d91-ab5e-15e3b464e1e6/email-rendering-research/courier-standard-client-reference/gmail-web-dark-3x1`. The source HTML was unchanged; submitted diagnostic comment nonces varied, and downstream cache behavior was not established.
