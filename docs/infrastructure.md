# 基础设施层设计与使用指南（infrastructure/）

基础设施层承载“实现细节”：ORM 模型与仓储实现、数据库连接、外部系统客户端（缓存、对象存储、支付、消息）、任务系统、端口适配器等。目标是对上层隐藏技术栈差异，并保持可替换性。

目录（要点模块）：
- 数据库与 UoW：`database.py`、`unit_of_work.py`、`models/*`、`repositories/*`
- 缓存：`external/cache/redis_client.py`
- 对象存储：`external/storage/*`（config/base/models/providers/factory/__init__）
- 支付：`external/payments/*`（base/clients/factory）
- 消息：`external/messaging/*`（配置、工厂、客户端、中间件、重试）
- 任务：`tasks/*`（Celery 配置、Worker、示例任务）
- 适配器：`adapters/storage_port.py`（将 Provider 适配为应用层 Port）

---

## 数据库与事务
- 引擎与会话：`database.py`
  - 根据 `settings.database.url` 自动切换到异步驱动（`postgresql+asyncpg`/`mysql+aiomysql`/`sqlite+aiosqlite`）。
  - 提供 `AsyncSessionLocal` 与建表/删表工具（开发/测试友好）。
- ORM 模型：
  - `models/base.py` 导出 `Base`/`metadata`；
  - `models/user.py` 与 `models/file_asset.py` 定义表结构、索引、约束（如文件唯一键哈希等）。
- 仓储实现：
  - 用户：`repositories/user_repository.py` 负责实体/模型互转、唯一性冲突 → 领域异常、稳定分页排序；
  - 文件：`repositories/file_asset_repository.py` 提供过滤（owner/kind/status）、稳定排序与唯一键处理（`SHA-256(storage_type|bucket|key)`）。
- UoW：`unit_of_work.py`
  - 进入上下文时创建事务（非只读），退出时统一提交/回滚，自动清理事务/会话。

---

## 缓存（Redis）
- 客户端：`external/cache/redis_client.py`
  - 命名空间前缀、JSON 序列化、批量操作（pipeline）、丰富数据结构支持；
  - 指标（命中率/平均耗时/操作计数）与错误处理；
  - 分布式锁（含自动续租可选）；
  - 本项目用于“首个超管”分布式锁与支付 Webhook 去重。

---

## 对象存储
- 配置与工厂：
  - `external/storage/config.py` 定义 `StorageConfig` 与 `StorageType`；
  - `external/storage/factory.py` 注册/创建 Provider，支持本地/S3/OSS。
- Provider 协议：`external/storage/base.py` 与 `external/storage/models.py`；
- 本地实现：`external/storage/providers/local.py`
  - 路径安全：`_safe_path()` 防目录穿越（resolve + relative_to 检测）。
  - 元数据 sidecar（`.meta`）文件保存 `content_type/metadata`；
  - 计算 ETag、公共 URL（可配 `public_base_url`）。
- 生命周期：`external/storage/__init__.py`
  - `init_storage_client()`/`shutdown_storage_client()` 统一初始化与清理；
  - `get_storage_config()` 从 `core.config.settings.storage` 构造配置；
  - 注意：代码中校验中间件判断引用了未定义变量 `s`，应改为读取 `config` 或 `settings.storage`（已在 docs/architecture.md 标注）。
- 应用端口适配：`adapters/storage_port.py` 将 Provider 的数据模型翻译为应用 `StoragePort` 的 DTO（`PresignedURL/ObjectMetadata/UploadOutcome/StorageInfo`）。

---

## 支付网关
- 基类：`external/payments/base.py`
  - 共享能力：`httpx.AsyncClient`、`tenacity` 重试、统一日志、状态映射（`shared/codes/payment_codes.py`）。
- 具体实现：
  - Stripe：`external/payments/stripe_client.py`（PaymentIntent、Refund、Webhook 验签）。
  - Alipay：`external/payments/alipay_client.py`（预下单/PC/WAP、交易查询/退款/关闭、Webhook 验签）。
  - WeChat：`external/payments/wechatpay_client.py`（NATIVE/H5/JSAPI、查询/退款/关闭、回调解密/验签）。
- 工厂：`external/payments/__init__.py:get_payment_gateway()` 按 provider 选择实现。

---

## 消息系统（Kafka）
- 统一配置构建：`external/messaging/config_builder.py` 将 `core.config.settings.kafka` 映射为消息层配置。
- 中间件：日志/指标/追踪，重试拓扑（retry.5s/1m/10m → dlq）。
- 生产/消费工厂：`external/messaging/factory.py`（按 driver 选择 confluent-kafka/aiokafka）。
- 详细说明参见 `docs/messaging.md` 与示例 `examples/messaging_demo.py`。

---

## 任务系统（Celery）
- 配置：`tasks/config/celery.py` 使用 Redis 作为 broker/backend（默认从 settings 继承），配置队列与路由；在开发/测试可启用 `task_always_eager`。
- Worker：`tasks/worker.py`；Beat：`tasks/config/beat.py`。
- 示例任务：`tasks/payment_tasks.py`（查询/退款补偿使用 `PaymentService`，每个任务内以 `asyncio.run` 调用异步 API，任务隔离）。

---

## 最佳实践
- 处理外部错误：将 SDK/网络异常转换为本层异常或返回值，并在应用/领域层抛领域异常；
- 安全：
  - 文件路径/对象键需要严格校验，避免目录穿越与键注入；
  - 不把临时签名 URL 入库，只存稳定公共 URL；
- 性能：
  - SQL 查询稳定排序（时间 + ID）以保证分页一致；
  - Redis pipeline 批处理，合理 TTL；
- 可替换性：
  - 一切对上暴露接口/DTO，内部细节可自由替换（换存储/换支付只需替换 Provider 与 Adapter）。

