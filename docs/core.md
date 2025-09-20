# 核心层设计与使用指南（core/）

核心层提供整个系统的基座：配置、日志、统一响应与异常映射。它不包含业务规则，只负责横切能力与基础约束。

目录：
- 配置：`core/config.py`（主配置），`core/settings.py`（支付子配置）
- 日志：`core/logging_config.py`
- 响应：`core/response.py`
- 异常映射：`core/exceptions.py`

---

## 配置（pydantic-settings v2）
- `Settings`：支持 `.env` 与嵌套环境变量（分隔符 `__`）。
- 强约束：`SECRET_KEY` 必须设置（任意环境），否则应用启动失败；避免热重载/重启后 JWT 失效。
- 重要分组：
  - `database`：数据库连接串（会在基础设施层升级为异步驱动）。
  - `redis`：缓存/锁/任务 broker 使用。
  - `storage`：对象存储（本地/S3/OSS）与预签名策略。
  - `kafka`：消息系统（详见 docs/messaging.md）。
  - 分页/请求体日志/CORS 等通用开关。
- 支付配置（`PaymentSettings`）：默认 provider、timeouts/retry、webhook 容忍窗口、各渠道密钥/证书位置，支持嵌套 env。

---

## 日志（structlog）
- 统一入口：`get_logger(__name__)`。
- 渲染策略：开发使用 ConsoleRenderer（彩色、便读）；非开发使用 JSON（利于采集/检索）。
- 绑定上下文：通过 `contextvars` 获取 `request_id/method/path/client_ip` 等；std lib logging 与 structlog 统一到同一处理链。

---

## 统一响应与时间序列化
- `Response[T]`/`PaginatedData[T]`：统一 `code/message/data/error` 结构；
- 时间一律序列化为 UTC ISO8601 且以 `Z` 结尾，消除时区歧义；
- 便捷函数：`success_response()`、`error_response()`、`paginated_response()`。

---

## 全局异常映射
- `register_exception_handlers(app)`：
  - 领域 `BusinessException` → 业务码到 HTTP 状态的映射（如校验 422、未授权 401、限流 429 等）。
  - `RequestValidationError` → 422，包含第一个字段错误与完整 errors 数组；
  - `HTTPException` 统一包装为业务码响应；
  - 未捕获异常 → 500，开发环境返回堆栈，日志带 `request_id`。
- 注意：401 场景按需返回 `WWW-Authenticate: Bearer` 以配合客户端行为。

---

## 最佳实践
- 永远通过 `get_logger`；不要 `print`；
- 外层（API/Tasks）在入口尽早绑定 `request_id`（本项目由中间件完成）；
- 对外协议（DTO/Response）变更时，保持兼容或升级版本前缀（如 `/api/v2`）。

