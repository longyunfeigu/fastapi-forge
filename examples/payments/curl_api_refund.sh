#!/usr/bin/env bash
set -euo pipefail

BASE_URL=${BASE_URL:-http://localhost:8000}

curl -sS -X POST "$BASE_URL/api/v1/payments/refunds" \
  -H 'Content-Type: application/json' \
  -d '{
    "order_id": "ORDER_10001",
    "amount": "5.00",
    "currency": "USD",
    "provider": "stripe",
    "reason": "partial refund"
  }' | jq .

