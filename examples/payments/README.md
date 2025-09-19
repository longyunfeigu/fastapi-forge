# Payments Examples

This folder contains sample payloads and cURL snippets for integrating with the payment gateway adapters (Stripe, Alipay, WeChat Pay v3).

- Stripe
  - Create PaymentIntent via cURL (server-side)
  - Example `payment_intent.succeeded` webhook event
- Alipay
  - `precreate` biz_content example
  - Notify callback sample (form-encoded)
- WeChat Pay v3
  - JSAPI/NATIVE request examples
  - Callback example with `resource` block (AES-256-GCM)

Note: Do not use real secrets. All samples are sanitized.
