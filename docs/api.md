# API 层设计与使用指南（api/）

本层是系统的 HTTP 表现层（Controller）。职责是：
- 将 HTTP 输入/输出与应用用例解耦（只做 I/O 绑定与依赖注入）。
- 进行边界校验（Pydantic DTO）与安全控制（认证/授权）。
- 调用 Application Service 执行业务，不直接访问数据库/外部 SDK。

目录：
- 依赖与安全：`api/dependencies.py`
- 中间件：`api/middleware/request_id.py`、`api/middleware/logging.py`
- 路由：`api/routes/user.py`、`api/routes/storage.py`、`api/routes/files.py`、`api/routes/payments.py`
- 工具：`api/utils/headers.py`

---

## 中间件

1) Request ID（追踪） — `api/middleware/request_id.py`
- 在每个请求生成或透传 `X-Request-ID`，写入 `request.state` 与 `contextvars`。
- 绑定到 structlog 日志上下文：`request_id`、`client_ip`、`method`、`path`。
- 响应头会返回同一个 `X-Request-ID` 便于调用方链路追踪。

2) 请求/响应日志 — `api/middleware/logging.py`
- 记录方法、路径、查询参数、路径参数、状态码、耗时等。
- 请求体记录可控：
  - 默认由 `settings.LOG_REQUEST_BODY_ENABLE_BY_DEFAULT` + `DEBUG` 决定。
  - 可用请求头覆盖：`X-Log-Body: true|false`。
  - 截断前 N 字节（默认 2048）并对敏感字段脱敏：`password`/`token`/`access_token`/`refresh_token` 等。
  - `multipart/form-data` 默认不读取以避免大文件开销（可配置仅记录标记）。

---

## 依赖与安全（dependencies.py）
- 统一 Token 提取：同时支持 Swagger 的 OAuth2 Password Flow 与普通 Bearer：
  - `get_token()`：优先 OAuth2，再尝试 `Authorization: Bearer`，失败返回 401 并带 `WWW-Authenticate`。
- 用户态依赖：
  - `get_current_user()` → 验证 Access Token，返回 `UserResponseDTO`。
  - `get_current_active_user()` → 校验用户未被停用。
  - `get_current_superuser()` → 超管校验。
- 应用服务依赖：
  - `get_user_service()` — 注入 `UserApplicationService(uow_factory=SQLAlchemyUnitOfWork)`。
  - 文件资产相关通过端口：`get_storage_port()` 注入 `StoragePort` 适配器，`get_file_asset_service()` 组合 UoW + StoragePort。

要点：API 层不触达 ORM 或外部 SDK；一切通过 Application Service 与 Port 完成。

---

## 路由设计

- 用户（/api/v1/users） — `api/routes/user.py`
  - 注册：`POST /register`，返回统一 `Response[UserResponseDTO]`。
  - 登录：`POST /login`（表单），返回 `TokenDTO`（为符合 OAuth2 期望，未包一层 Response）。
  - 刷新：`POST /refresh`，返回 `TokenDTO`。
  - 我：`GET /me`，需登录。
  - 更新我：`PUT /me`。
  - 超管操作：列表/按 ID 获取/更新/激活/停用/删除。

- 存储（/api/v1/storage） — `api/routes/storage.py`
  - 直传预签名：`POST /presign-upload` → 返回预签名与 pending 记录摘要（不包含临时签名入库）。
  - 直传完成：`POST /complete` → 根据 `id` 或 `key` 回填元数据并激活。
  - 中转上传：`POST /upload` → API 接收文件后写入对象存储并 upsert 活跃资产。

- 文件管理（/api/v1/files） — `api/routes/files.py`
  - 列表：分页、条件过滤；可选 `signed=true` 在响应时动态覆盖 URL 为临时签名（不入库）。
  - 详情：支持 `signed` 与 `filename` 参数以控制下载/预览文件名与有效期。
  - 生成预览/下载链接：`/{asset_id}/preview-url`、`/{asset_id}/download-url`。
  - 删除：软删或物理删除（超管/本人）。

- 支付（/api/v1/payments） — `api/routes/payments.py`
  - Webhook：`POST /webhooks/{provider}`（Stripe/Alipay/WeChat），根据渠道校验 Content-Type 与 IP allowlist；使用 Redis 以 `event.id + body_hash` 去重。
  - 发起：`POST /intents`，返回标准化 `PaymentIntent`。
  - 查询：`GET /intents/{order_id}`。
  - 退款：`POST /refunds`； 关闭：`POST /intents/{order_id}/close`。

---

## 统一响应与异常
- 成功：`core/response.py:success_response()`。
- 失败：统一由 `core/exceptions.register_exception_handlers()` 生成 `Response[error]`，包含 `request_id` 与 UTC-Z 时间戳，业务码见 `shared/codes.py`。

---

## 示例（cURL）

- 注册
```
curl -X POST http://localhost:8000/api/v1/users/register \
  -H 'Content-Type: application/json' \
  -d '{"username":"alice","email":"a@ex.com","password":"Abcdefg1"}'
```

- 登录（OAuth2 Password）
```
curl -X POST http://localhost:8000/api/v1/users/login \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d 'username=alice&password=Abcdefg1'
```

- 带 Token 访问
```
curl http://localhost:8000/api/v1/users/me \
  -H 'Authorization: Bearer <ACCESS_TOKEN>'
```

---

## 编码准则（API 层）
- Controller 保持“瘦”：不做业务、不做数据访问。
- 所有日志通过 `core.logging_config.get_logger(__name__)`，不要使用 `print`。
- DTO/Response 作为对外契约；不要将 ORM 模型直接泄露到 API。
- 对外字段/行为如需变更，先改 DTO 与 Service，再改路由，避免跨层耦合。

---

## 删除策略（文件资源）

- 默认仅支持“软删除”：`DELETE /api/v1/files/{asset_id}` 将资源标记为 `deleted`（不会立即移除对象存储上的文件）。
- 物理删除（远端对象 + DB 记录）仅在服务内部提供：`FileAssetApplicationService.purge_asset_by_id(key)` 等，不对外暴露开关以避免误删。
- 推荐操作顺序：
  - 业务删除 → 软删（可恢复/审计）。
  - 后台保留清理任务按策略批量“物理删除”真正无引用的对象（如超期、回收站清空）。

---

## 安全建议

- 配置：
  - 强制设置 `SECRET_KEY`（或 `JWT_SECRET_KEY`）；生产环境使用高强度、唯一密钥。
  - 合理配置 CORS；默认开发便捷设置不要用于生产。
  - Token 过期与刷新：`ACCESS_TOKEN_EXPIRE_MINUTES`、`REFRESH_TOKEN_EXPIRE_DAYS`。
  - Webhook：建议启用 IP 白名单与时间容忍度，见“Webhook 安全”。
- 日志：
  - 使用结构化日志；请求体记录遵守脱敏与体积限制；禁止输出密钥/令牌。
- 访问控制：
  - 所有文件写入/删除均要求登录；跨租户/可见范围由应用层校验（如 `owner_id`）。

---

## Webhook 安全（支付）

- 路由：`POST /api/v1/payments/webhooks/{provider}`（`stripe|alipay|wechat`）。
- 内容类型：
  - Alipay：`application/x-www-form-urlencoded`；其他渠道通常使用 `application/json`。
- 签名校验：
  - Stripe：`Stripe-Signature` + `STRIPE__WEBHOOK_SECRET`。
  - Alipay：RSA2 签名（公钥 `ALIPAY__ALIPAY_PUBLIC_KEY_PATH`）。
  - WeChat：SDK 校验与解密（商户/平台证书与密钥）。
- 防重放：
  - 使用 Redis 基于 `provider + event.id + sha256(body)` 的键进行去重；TTL 由 `PAYMENT__WEBHOOK__TOLERANCE_SECONDS` 控制（默认 300s）。
- IP 允许列表：
  - 环境配置 `PAYMENT__WEBHOOK__IP_ALLOWLIST`（CIDR 或 IP 列表），非白名单可直接返回 200（记录日志）以减少渠道重试风暴；生产视需要返回 4xx 并同步治理来源。

---

## 认证与令牌（Access / Refresh）

目标：在保持 API 无状态的同时，兼顾登录会话的安全与可控性。

- Access Token（访问令牌）
  - 形式：JWT（HS256）。字段：`sub`（用户ID）、`username`、`is_superuser`、`exp`、`type=access`、`jti`。
  - 生成与校验：`TokenService.create_access_token()` / `TokenService.verify_access_token()`。
  - 持久化：不落库（无状态）。
  - 使用场景：HTTP API（dependencies.get_current_user）、WebSocket 握手（`/api/v1/ws?token=...`）与 gRPC 拦截器（Authorization: Bearer）。
  - 撤销策略：无法中心化强制撤销，依赖较短过期时间（`ACCESS_TOKEN_EXPIRE_MINUTES`）。若需“立即失效”体验，可辅以服务端 denylist（未默认实现）或缩短 TTL。

- Refresh Token（刷新令牌）
  - 形式：JWT + 数据库存证。仅存储 SHA-256 哈希，避免明文落库。
  - 模型：`infrastructure/models/refresh_token.py`（表 `refresh_tokens`）。字段要点：`jti`、`family_id`、`parent_jti`、`token_hash`、`is_revoked`、`is_used`、`device_info`、`ip_address`、`expires_at`。
  - 用例编排：`TokenService.rotate_refresh_token()` 实现刷新令牌轮转与安全策略：
    1) 验证签名/过期 → 2) 校验是否撤销 → 3) 检测是否已使用（检测重用）→ 4) 标记旧令牌已使用 → 5) 颁发新 access/refresh。
    6) 若检测到“已使用令牌再次被使用”，撤销整个令牌家族（`revoke_family()`）。
  - 撤销能力：
    - 单个撤销：`revoke_token(jti)`；整用户撤销：`revoke_all_user_tokens(user_id)`（“登出所有设备”）。
    - 清理：`cleanup_expired(before)` 删除过期且已撤销/已使用的记录。

- 流程与职责分工：
  - 登录：返回 access + refresh。访问令牌短期可用；刷新令牌长期可用（可轮转）。
  - 刷新：仅接受 refresh；成功后轮转出新的 access+refresh，并使旧 refresh 立刻失效（`is_used=true`）。
  - 统一验证入口：API/WS/gRPC 均依赖 `TokenService.verify_access_token`；异常策略：过期抛 `TokenExpiredException`，其它无效返回 `None`（上层 401）。

- 客户端安全建议：
  - 总是通过 HTTPS 传输；不要在日志中输出 token。
  - Access Token 建议放入内存/短期缓存；Refresh Token 不建议暴露给 JS（优先考虑 HttpOnly Cookie 等方案）。
  - 若使用浏览器 SPA，可将刷新动作放在受保护路径并结合 CSRF 防护。
