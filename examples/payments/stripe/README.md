# Stripe Examples

- `curl_create_payment_intent.sh` – Create a PaymentIntent with idempotency key.
- `webhook_event_payment_intent_succeeded.json` – Example webhook payload for `payment_intent.succeeded`.

To test webhooks locally, consider using the Stripe CLI:

- `stripe listen --forward-to localhost:8000/api/v1/payments/webhooks/stripe`
- `stripe trigger payment_intent.succeeded`

This project’s Stripe adapter verifies signatures using `STRIPE__WEBHOOK_SECRET` and enforces a timestamp tolerance.
