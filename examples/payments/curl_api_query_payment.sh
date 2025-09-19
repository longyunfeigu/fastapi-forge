#!/usr/bin/env bash
set -euo pipefail

BASE_URL=${BASE_URL:-http://localhost:8000}

ORDER_ID=${1:-ORDER_10001}
PROVIDER=${2:-stripe}

curl -sS "$BASE_URL/api/v1/payments/intents/$ORDER_ID?provider=$PROVIDER" | jq .

