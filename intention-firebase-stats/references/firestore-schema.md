# Intention Setting Firebase Schema

Use this reference only when the bundled aggregate report is not enough.

## Project and Access

- Firebase project: `intention-setter`
- Repo: `/Users/Henry/Developer/intention-setting`
- Public-site package with `firebase-admin`: `public-site`
- Admin credential: `public-site/scripts/intention-setter-firebase-adminsdk-fbsvc-0449a100a5.json`
- Credential safety: never print the private key or copy the credential into tracked files.

## Auth

Firebase Auth is the source for account counts and sign-in recency.

Useful metadata from `admin.auth().listUsers()`:

- `metadata.creationTime`
- `metadata.lastSignInTime`
- `emailVerified`
- `disabled`
- `providerData[].providerId`

Default reporting should count users by windows such as last 1, 7, 30, and 90 days. Do not list emails or user IDs unless explicitly requested.

## Firestore

### `users/{uid}`

Primary app document. Known fields:

- `email`, `displayName`, `photoURL`, `profileSyncedAt`: synced by the public site or extension auth flow.
- `rules`: array of configured blocking/limit rules. Known `type` values include `hard`, `soft`, `session`, and `time`.
- `groups`: array of grouped URLs.
- `conversationHistory`: AI chat history.
- `dailyUsageHistory`: map keyed by `YYYY-MM-DD`.
- `lastDailyResetTimestamp`: most recent local daily reset timestamp.
- `usageResetRequestedAt`, `usageResetAppliedAt`: remote usage clear/reset coordination.

### `users/{uid}.dailyUsageHistory`

Each day value is expected to include:

- `totalTimeSpent`: tracked seconds for that day.
- `trackedSiteCount`: number of tracked site keys with usage.
- `siteTotals`: map of site key to tracked seconds.
- `periodStart`, `periodEnd`, `capturedAt`: timestamps in milliseconds.

Aggregate the day entries for usage-hour totals. Avoid printing `siteTotals` by default because it can reveal browsing patterns.

### `shareIdMappings/{shareId}`

Public sharing lookup. Known fields:

- `userId`
- `enabled`
- `updatedAt`

Count enabled mappings for public-sharing stats. Do not print share IDs by default.

### `users/{uid}/private/shareSettings`

Private per-user sharing settings. Known fields:

- `shareId`
- `enabled`
- `createdAt`
- `updatedAt`

Use collection group `private` and filter locally for doc id `shareSettings` when counting share settings.

### `customers/{uid}/subscriptions/{subscriptionId}`

Stripe extension subscription data. Known fields vary by Stripe extension version, but `status` is the key aggregate field.

Common active statuses:

- `active`
- `trialing`

Count statuses; do not print customer IDs by default.
