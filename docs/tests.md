# 测试策略与约定（tests/）

测试目标：以最小成本覆盖关键行为与边界，优先验证“公共契约与协议”，保持测试对实现细节不敏感。

目录：
- 骨架：`tests/test_payments_skeleton.py`
- 支付服务：`tests/payments/test_service_idempotency.py`、`tests/payments/test_mapping_helpers.py`
- Webhook 解析：`tests/payments/test_stripe_webhook.py`、`tests/payments/test_alipay_webhook.py`、`tests/payments/test_wechat_webhook.py`

---

## 准则
- 每个测试关注一个行为（One assertion per behavior）便于定位失败；
- 异步测试使用 `pytest.mark.asyncio`；
- API 集成测试推荐 `httpx.AsyncClient`（在本仓库暂以支付为主）；
- 对重依赖（SDK/网络/密钥）使用 `pytest.importorskip` 或 monkeypatch/fake 以降低环境要求；
- 不把 ORM/SDK 细节耦合到应用层测试（优先 mock Port/Repository/UoW）。

---

## 示例要点
- 幂等键生成：确保创建/退款在未传入键时，应用层会生成 64 字节的 SHA-256 key；
- Webhook 解析：
  - Stripe：fake `Webhook.construct_event`；
  - Alipay：stub 验签函数为 True；
  - WeChat：fake SDK `callback` 返回解密后的事件；
- 路由注册：基础冒烟用例，确保 `/api/v1/payments/webhooks/{provider}` 可用。

---

## 建议补充
- 用户注册/登录/权限流的 API 测试；
- 文件直传/完成/签名访问流程（mock StoragePort）；
- 数据库事务性与并发（首超分布式锁）的小型一致性测试。

