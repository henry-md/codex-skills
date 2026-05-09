# Stripe Safety Log

## Purpose

Keep compact notes from Stripe incidents, probes, and integration surprises. Add new entries when a Stripe behavior, warning, or near miss should change future agent behavior.

## Raw Card Data Warning

Date: 2026-04-29

What happened:

- A test-mode probe attempted to create a Stripe payment method by passing the raw test card number `4242424242424242` to Stripe's server API.
- Stripe rejected the request and sent the account owner a first-time warning email about passing a customer's full credit card number to the API.
- The request ID in the warning was `req_nFDJwDv0PIXyEe`.

Why it matters:

- Even test card numbers should not be sent as raw card data from server-side probes.
- Stripe treats this as unsafe integration behavior because real integrations must keep card data in official client-side collection surfaces.
- The safe test succeeded after switching to Stripe's test token path (`tok_visa`).

Rule:

- Never pass raw card numbers to Stripe APIs. Use Checkout/Portal/client integrations, or Stripe's approved test tokens for server-side test setup.

## Firebase Stripe Extension Notes

Observed in the `intention-setter` project on 2026-04-29:

- The deployed Firebase Stripe secret was `sk_test`, so the integration was in test mode.
- The extension build embedded test price `price_1Se6QBFMpQHsTX0mvwmvJqI1`.
- The connected live Stripe account had live price `price_1SgwWZFMpQHsTX0m8zAhC99z`, which is distinct from the test price.
- The enabled test webhook endpoint pointed at `https://us-central1-intention-setter.cloudfunctions.net/ext-firestore-stripe-payments-handleWebhookEvents`.
- Writing a valid `customers/{uid}/checkout_sessions` doc for an existing Firebase Auth user caused the Firebase Stripe extension to create the Stripe customer and Checkout Session URL.
- A direct auth-user-created probe did not populate `customers/{uid}.stripeId` within two minutes, but Checkout Session creation still created/populated the customer doc.

Practical checks:

- Verify checkout by observing the `checkout_sessions` doc for `url` or `error`.
- Verify manage-subscription by checking both Stripe subscription `cancel_at_period_end` and Firestore subscription `cancel_at_period_end`.
- If Stripe customer cleanup is needed after tests, direct retrieval may show `deleted: true` before search results stop showing the customer.

## Probe Hygiene

For future Stripe probes:

- Use metadata such as `codexProbe=true`, `firebaseUID=codex-...`, or an `example.invalid` email.
- Use `try/finally` cleanup for created subscriptions, checkout sessions, app records, Firebase test users, and Stripe customers.
- Prefer expiring open Checkout Sessions and canceling test subscriptions before deleting test customers.
- Do not clean up real or ambiguous customer records automatically.
