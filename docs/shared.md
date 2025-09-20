# 共享模块设计与使用指南（shared/）

`shared/` 存放跨层复用的常量与轻量工具，尤其是“业务码”枚举，作为多层的单一事实来源（Single Source of Truth）。

目录：
- `shared/codes.py` — 业务码 `BusinessCode`（成功/参数/业务/权限/系统/限流）
- `shared/codes/payment_codes.py` — 支付相关码与“渠道状态 → 内部状态”映射

---

## BusinessCode（shared/codes.py）
- 将常见错误聚合为稳定、可被各层识别的 IntEnum（如 `PARAM_VALIDATION_ERROR`、`UNAUTHORIZED`、`TOO_MANY_REQUESTS`）。
- 在领域异常、全局异常映射、API 响应中统一使用，避免“魔法数字”。

---

## 支付状态映射（payment_codes.py）
- 不同渠道状态语义不同，应用通过 `_map_status()` 将其转换为内部统一词汇：`succeeded/processing/pending/canceled/expired/refund_pending/...`。
- 目前提供 Stripe/Alipay/WeChat 的基础映射，可按业务扩展。

---

## 最佳实践
- 只在 `shared/` 定义业务码，不要在其他层重复枚举；
- 映射表更新需考虑回溯兼容（新增键值优先）；
- 在日志中输出 `code` 与 `error_type`，利于聚合检索与对齐观测体系（Metrics/Tracing）。

