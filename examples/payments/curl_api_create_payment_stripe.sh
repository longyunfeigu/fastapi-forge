#!/usr/bin/env bash
set -euo pipefail

BASE_URL=${BASE_URL:-http://localhost:8000}

curl -sS -X POST "$BASE_URL/api/v1/payments/intents" \
  -H 'Content-Type: application/json' \
  -d '{
    "order_id": "ORDER_10001",
    "amount": "19.99",
    "currency": "USD",
    "provider": "stripe",
    "scene": "card",
    "metadata": {"customer_id": "user_42"}
  }' | jq .

