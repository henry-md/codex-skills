---
name: intention-firebase-stats
description: Query aggregate Firebase Auth, Firestore, sharing, billing, and tracked-usage stats for the Intention Setting app. Use when the user asks about Firebase access, user counts, active users, app usage stats, public share links, subscriptions, or other user metrics for /Users/Henry/Developer/intention-setting.
---

# Intention Firebase Stats

## Overview

Use this skill to answer Firebase/user-metrics questions for the Intention Setting repo without rediscovering the project, credential path, or Firestore schema.

## Quick Start

Run the bundled aggregate report script:

```bash
node /Users/Henry/.codex/skills/intention-firebase-stats/scripts/report_user_stats.cjs --repo /Users/Henry/Developer/intention-setting
```

Use `--json` when you need machine-readable output:

```bash
node /Users/Henry/.codex/skills/intention-firebase-stats/scripts/report_user_stats.cjs --repo /Users/Henry/Developer/intention-setting --json
```

## Safety Rules

- Report aggregate stats by default.
- Do not print service-account key material, ID tokens, emails, display names, user IDs, or per-user browsing/usage rows unless the user explicitly asks for identifiable data.
- Prefer Auth metadata for login/account stats and Firestore aggregates for app behavior stats.
- Treat the local service-account JSON as sensitive even though it is needed by the Admin SDK.
- Do not modify Firebase data from this skill. The bundled script is read-only.

## Workflow

1. Confirm the repo path, defaulting to `/Users/Henry/Developer/intention-setting`.
2. Run `scripts/report_user_stats.cjs` for the common aggregate report.
3. Summarize the high-signal numbers in prose: Auth users, recent sign-ins, Firestore user docs, rules/groups, usage hours, sharing links, and subscriptions.
4. If the question needs schema context, read `references/firestore-schema.md`.
5. If the script fails because dependencies or credentials are missing, explain the exact missing piece and avoid inventing stats.

## Known Repo Details

- Firebase project ID: `intention-setter`
- Public site package: `/Users/Henry/Developer/intention-setting/public-site`
- Admin credential path: `/Users/Henry/Developer/intention-setting/public-site/scripts/intention-setter-firebase-adminsdk-fbsvc-0449a100a5.json`
- The credential filename pattern is gitignored in `public-site/.gitignore`.
- Main app user collection: `users`
- Stripe extension data: `customers/{uid}/subscriptions`
- Public sharing lookup: `shareIdMappings`

## Reference

Read `references/firestore-schema.md` when you need field meanings, collection relationships, or guidance for a more custom Firebase query.
