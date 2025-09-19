#!/usr/bin/env bash
set -euo pipefail

# Create a PaymentIntent with idempotency key (server-side example)
# Requires: STRIPE_SECRET (exported) and curl

if [[ -z "${STRIPE_SECRET:-}" ]]; then
  echo "Please export STRIPE_SECRET=sk_test_xxx" >&2
  exit 1
fi

IDEMP_KEY="order-123-user-42-$(date +%s)"

curl -sS https://api.stripe.com/v1/payment_intents \
  -u "$STRIPE_SECRET:" \
  -H "Idempotency-Key: $IDEMP_KEY" \
  -d amount=1999 \
  -d currency=usd \
  -d automatic_payment_methods[enabled]=true \
  -d metadata[order_id]=order_123 \
  | jq .

