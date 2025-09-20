# 示例与演示（examples/）

该目录提供用于本地联调与演示的脚本与素材，帮助快速理解 API 与外部系统集成方式。

目录：
- 消息：`examples/messaging_demo.py`
- 支付（示例与 cURL）：`examples/payments/*`（含 demo HTML、渠道示例载荷与脚本）

---

## 消息示例（Kafka）
- 运行前设置 `KAFKA__BOOTSTRAP_SERVERS`；
- 生产：
```
python examples/messaging_demo.py produce --topic demo.topic.v1 --count 5 --interval 0.2
```
- 消费：
```
python examples/messaging_demo.py consume --topic demo.topic.v1 --group demo-group
```
- 详见 `docs/messaging.md`。

---

## 支付示例
- Stripe：
  - 创建 Intent：`examples/payments/stripe/curl_create_payment_intent.sh`
  - Webhook 事件样例：`examples/payments/stripe/webhook_event_payment_intent_succeeded.json`
- Alipay：
  - 预下单请求体示例：`examples/payments/alipay/precreate_biz_content.json`
  - 回调 form 样例：`examples/payments/alipay/notify_form.txt`
- WeChat：
  - JSAPI 请求样例：`examples/payments/wechat/jsapi_request.json`
  - 回调样例：`examples/payments/wechat/callback.json`
- 通用 cURL：
  - `examples/payments/curl_api_create_payment_*.sh`、`curl_api_query_payment.sh`、`curl_api_refund.sh`、`curl_api_close.sh`

---

## Demo 页面
- `examples/payments/demo/index.html`：
  - Stripe：输入 publishable key，点击 “Create Intent” & “Pay”；
  - Alipay/WeChat：点击 “Create QR” 渲染 `qr_code/code_url`。

