# 应用层设计与使用指南（application/）

应用层承接 API 的输入，编排领域服务与事务，输出 DTO 给表现层。它不包含数据库实现细节，也不直接依赖外部 SDK，而是通过“端口（Port）协议 + 适配器（Adapter）”使用基础设施。

目录与职责：
- DTO：`application/dto.py`、支付 DTO `application/dtos/payments.py`
- 用例服务：`services/user_service.py`、`services/file_asset_service.py`、`services/payment_service.py`
- 端口协议：`ports/storage.py`
- 工具：`utils/storage.py`

---

## 事务与 UoW（Unit of Work）
- 抽象：`domain/common/unit_of_work.py`
- 实现：`infrastructure/unit_of_work.py`
- 使用方式：服务构造时注入 `uow_factory`（通常是 `SQLAlchemyUnitOfWork`）。
- 只读优化：`with self._uow_factory(readonly=True)` 不会提交事务，适合查询用例。
- 读写：进入 `with` 后获取仓储，写操作完成后由 UoW 统一提交/回滚。

---

## 用户用例（services/user_service.py）
- 注册首超：
  1) 先只读统计用户总数；若可能为 0 且配置了 Redis，则获取分布式锁 `first_superuser_init`；
  2) 锁内再次确认后创建用户，确保并发场景下只有一个“首个用户”。
- 登录/认证：
  - 认证在领域服务中完成（密码校验、活跃状态检查）。
  - 生成 `access_token`（短期）与 `refresh_token`（长期）。
  - `verify_token(token)`：
    - 过期 → 抛出 `TokenExpiredException`（由全局异常处理为 401 + 过期语义）。
    - 无效 → 返回 `None`（API 返回 401 无效凭据）。
- 用户资料：查询、更新、改密、激活/停用、删除。数据修改前由领域实体做规则校验。

---

## 文件用例（services/file_asset_service.py）
- 设计：聚合根 `domain/file_asset/entity.py` 管理状态机（pending/active/deleted）。
- 直传（推荐）：
  1) 客户端请求预签名：生成存储 Key（`utils/storage.build_storage_key`）→ 调用 StoragePort 生成预签名。
  2) 同时在 DB 中创建 `pending` 记录（不保存预签名到库）。
  3) 客户端直传后，调用 `complete`：从存储读取元数据并回填，标记 `active`。
- 中转上传：
  - 由 API 接收文件字节并写入存储，再 `upsert_active_asset` 更新/插入 `active` 记录。
- 访问 URL：
  - 若对象公共可读，优先返回稳定公共 URL。
  - 否则通过 StoragePort 生成带 `Content-Disposition` 的临时签名 URL（不入库，只在响应中覆盖）。

---

## 存储端口（ports/storage.py）
- 这是应用“拥有”的协议：
  - `generate_presigned_url()`、`upload()`、`get_metadata()`、`delete()`、`public_url()` 等。
- 基础设施通过适配器实现：`infrastructure/adapters/storage_port.py` 将具体 Provider 的模型翻译为端口 DTO（`PresignedURL`、`UploadOutcome` 等）。
- 好处：应用层不关心 S3/OSS/本地的差异，易于测试（可直接 mock Port）。

---

## 支付用例（services/payment_service.py）
- 网关协议：`application/ports/payment_gateway.py`（应用依赖该协议而非 SDK）。
- 工厂：`infrastructure/external/payments.get_payment_gateway(provider)` 返回具体适配器（Stripe/Alipay/WeChat），
  由 API/任务在组装阶段注入到 `PaymentService(gateway=...)`。
- 幂等性：创建/退款请求若未提供 `idempotency_key`，应用层会根据稳定字段（订单、金额、币种、渠道等）生成 SHA-256 键，降低网络重试带来的副作用。
- Webhook：仅负责调用网关解析签名并记录事件，幂等去重在 API 路由层通过 Redis 完成。
- 资源清理：按需调用 `aclose()` 关闭底层 HTTP 客户端。

---

## DTO 约定
- `DTOBase` 统一 UTC-Z 时间序列化，避免时区歧义。
- `TokenDTO` 为兼容 OAuth2 密码模式，直接作为 API 返回体（不包 `Response`）。
- `PaginationParams` 负责 `page/size → skip/limit` 的派生；API/Service 之间以 DTO 交互，避免穿透到 ORM。

---

## 扩展配方
- 新用例（不涉及外部系统）：
  1) 在领域层添加实体/规则（如需）。
  2) 在应用层创建 `XxxApplicationService`，通过 UoW 调用仓储实现事务边界。
  3) 定义输入/输出 DTO，封装为稳定对外契约。
  4) 在 API 层增加路由，依赖注入该服务，进行 DTO 组装与权限控制。
- 新外部系统（如新的对象存储/支付渠道）：
  1) 为应用层定义/沿用端口协议（Port）。
  2) 在基础设施实现 Provider 与适配器（Adapter）。
  3) 在应用服务中仅依赖 Port；测试可通过 Fake/Stub Port 注入。

---

## 测试建议
- 优先对服务进行“端到端”单元测试：构造内存/Stub 仓储与端口，覆盖分支与异常；
- API 层使用 `httpx.AsyncClient` 做少量集成测试验证绑定与安保；
- 避免将 ORM/SDK 细节引入应用层测试（保持可替换性）。
