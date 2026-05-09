---
name: stripe
description: Reference and diagnostic guidance for Stripe integrations, billing flows, Checkout, Customer Portal, subscriptions, webhooks, Firebase Stripe extension behavior, Stripe test/live mode separation, and safe payment testing. Use when inspecting or modifying Stripe code, verifying payment endpoints, creating checkout or subscription tests, handling Stripe emails or warnings, checking webhook behavior, cleaning up Stripe test data, or preserving learnings about Stripe API safety and integration mistakes.
---

# Stripe

## Overview

Use this skill as a compact, living knowledge base for Stripe work. The goal is to keep payment testing boring: verify what exists, avoid irreversible or noisy side effects, and write down lessons when Stripe behavior surprises us.

For incident notes and concrete guardrails from prior Stripe work, read [references/stripe-safety-log.md](references/stripe-safety-log.md).

## Working Model

Treat Stripe work as four layers:

1. Local code and env: price IDs, publishable keys, secret names, success/cancel URLs, webhook routes.
2. Runtime platform: deployed functions, Firebase/hosting config, secrets, extension instances, logs.
3. Stripe mode and objects: `sk_test` vs `sk_live`, test vs live products/prices/customers/subscriptions.
4. End-to-end behavior: Checkout or Portal opens, webhook syncs state, local app reads the expected records.

Always identify the layer and mode before writing to Stripe.

## Safety Rules

- Never send raw card numbers to Stripe APIs, even Stripe test card numbers.
- Prefer Stripe Checkout, Customer Portal, SetupIntents, or official client integrations for payment collection.
- For server-side test setup, use Stripe-approved test tokens such as `tok_visa`, or create objects that do not require payment details.
- Confirm whether a secret is `sk_test` or `sk_live` before any Stripe write.
- Do not create live charges, subscriptions, invoices, refunds, customer deletions, or payment links unless the user explicitly asks for that live action.
- Tag probe data with obvious metadata such as `codexProbe=true`, and clean it up in `finally` or immediately after verification.
- Mask secrets and never print full API keys, webhook secrets, payment method details, or customer personal data.

## First Checks

Before changing or testing a flow:

```sh
rg -n "stripe|checkout|subscription|portal|price_|prod_|webhook|customer" .
find . -maxdepth 3 -name ".env*" -print
```

Then answer:

- Which code path creates payment state: direct Stripe API, Checkout Session, Customer Portal, Firebase Stripe extension, or another backend?
- Which price IDs are compiled or configured locally?
- Which Stripe mode do the configured secret and price IDs belong to?
- Which webhook endpoint updates local app state?
- Is there already test data for the user/customer/subscription being inspected?

## Testing Pattern

Prefer read-only checks first: list deployed functions, inspect logs, fetch product/price metadata, and compare local env with Stripe objects.

For write tests:

1. State the mode and target objects to yourself before the write.
2. Use test mode unless live behavior was explicitly requested.
3. Create the smallest possible probe.
4. Avoid raw card data.
5. Verify Stripe state and app-side state.
6. Clean up probe customers, sessions, subscriptions, and app records.
7. Record new lessons in [references/stripe-safety-log.md](references/stripe-safety-log.md).

## Known Pitfalls

- A price ID can exist in test mode but not live mode, or vice versa. Fetch with the same secret the runtime uses.
- Firebase Stripe extension checkout creation may create a missing Stripe customer during Checkout Session handling, even if an auth-triggered customer function did not populate the customer doc first.
- Webhook logs can show partial success: one event may update subscriptions while another invoice event logs an error. Verify the exact record the app depends on.
- Search results in Stripe can lag after deletions. Directly retrieve an object if cleanup status matters.
