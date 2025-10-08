# Payments Gateway

This project provides a unified payments gateway with adapters for Stripe, Alipay, and WeChat Pay v3, following DDD boundaries.

## Minimal Demo Endpoints

Base path: `/api/v1/payments`

- Create payment: `POST /intents`
  - Body: `application/json` → `CreatePayment` (order_id, amount, currency, provider, scene, notify_url, return_url, metadata)
  - Returns: normalized `PaymentIntent` with `client_secret_or_params`.
- Query payment: `GET /intents/{order_id}?provider=stripe|alipay|wechat`
- Refund: `POST /refunds` (RefundRequest)
- Close: `POST /intents/{order_id}/close?provider=...`
- Webhooks: `POST /webhooks/{provider}`

See example cURL scripts under `examples/payments/`.

Demo HTML:

- Open `examples/payments/demo/index.html` in a browser.
- Stripe: enter your publishable key, click “Create Intent”, then “Pay”. The backend returns a client_secret and the Payment Element renders.
- Alipay/WeChat: click “Create QR” to render a QR from `qr_code`/`code_url`.

## Config

Set environment variables (see `env.example`):

- `PAYMENT__DEFAULT_PROVIDER`
- Stripe: `STRIPE__SECRET_KEY`, `STRIPE__WEBHOOK_SECRET`
- Alipay: `ALIPAY__APP_ID`, `ALIPAY__PRIVATE_KEY_PATH`, `ALIPAY__ALIPAY_PUBLIC_KEY_PATH`, `ALIPAY__GATEWAY`, `ALIPAY__SIGN_TYPE`
- WeChat: `WECHAT__MCH_ID`, `WECHAT__MCH_CERT_SERIAL_NO`, `WECHAT__PRIVATE_KEY_PATH`, `WECHAT__PLATFORM_CERT_DIR`, `WECHAT__API_V3_KEY`
 - Webhook: `PAYMENT__WEBHOOK__TOLERANCE_SECONDS`（时间容忍/去重 TTL，默认 300）,
   `PAYMENT__WEBHOOK__IP_ALLOWLIST`（可选，IP 或 CIDR 列表，`,` 分隔）

## Notes

- Stripe uses PaymentIntents and verifies webhook signatures (`Stripe-Signature`).
- WeChat v3 adapter verifies and decrypts callback `resource` via SDK.
- Alipay adapter verifies RSA2 signatures of form-encoded notify payloads.

### Webhook Security and Deduplication

- Signature verification:
  - Stripe: `Stripe-Signature` header + `STRIPE__WEBHOOK_SECRET`.
  - Alipay: RSA2 signature verification using `ALIPAY__ALIPAY_PUBLIC_KEY_PATH`.
  - WeChat: SDK-driven verification and AES-GCM decryption using merchant/private keys and platform certs.
- Optional IP allowlist:
  - `PAYMENT__WEBHOOK__IP_ALLOWLIST` supports single IPs and CIDRs.
- Deduplication:
  - The API stores a Redis key `webhook:{provider}:{event.id}:{sha256(body)}` for at least `PAYMENT__WEBHOOK__TOLERANCE_SECONDS` seconds.
  - Re-delivered events within the window are acknowledged with `duplicate=true`.

### Testing and Stubbing

- Stripe: monkeypatch `stripe.Webhook.construct_event` in tests to avoid crypto heavy deps.
- Alipay: the webhook parser allows injecting a public key/verify function at instance level (e.g., `_alipay_pubkey` / `_verify`) to ease testing.
- WeChat: the webhook parser relies on an injected client instance (`self._wx`), so tests can stub `.callback` without installing the SDK.

> For production, store keys in KMS/Secret Manager. Dev-only keys can be placed under `infrastructure/external/payments/keys/`.
