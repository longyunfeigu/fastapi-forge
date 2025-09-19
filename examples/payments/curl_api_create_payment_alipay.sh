#!/usr/bin/env bash
set -euo pipefail

BASE_URL=${BASE_URL:-http://localhost:8000}

curl -sS -X POST "$BASE_URL/api/v1/payments/intents" \
  -H 'Content-Type: application/json' \
  -d '{
    "order_id": "ORDER_20250919_0001",
    "amount": "88.88",
    "currency": "CNY",
    "provider": "alipay",
    "scene": "qr_code",
    "notify_url": "https://example.com/api/v1/payments/webhooks/alipay"
  }' | jq .

