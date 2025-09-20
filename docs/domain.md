# 领域层设计与使用指南（domain/）

领域层是业务核心：只表达规则与状态机，不依赖任何基础设施。这里的代码应当“可在纯 Python 环境下运行”，可被应用层编排调用，持久化细节由仓储实现负责。

目录与职责：
- 通用：`domain/common/exceptions.py`（业务异常）、`domain/common/unit_of_work.py`（UoW 抽象）
- 用户：`user/entity.py`、`user/repository.py`、`user/service.py`、`user/events.py`
- 文件：`file_asset/entity.py`、`file_asset/repository.py`
- 支付：领域事件 `payment/events.py`（支付成功/失败/退款/取消）；
  网关协议迁移至应用端口 `application/ports/payment_gateway.py`（保持领域与外部解耦）

---

## 业务异常（common/exceptions.py）
- 统一以 `BusinessException` 为基类，携带 `code/message/error_type/details/field`。
- 常见异常：
  - `UserNotFoundException`、`UserAlreadyExistsException`、`PasswordErrorException`、`UserInactiveException` 等；
  - 文件相关：`FileAssetNotFoundException`、`FileAssetAlreadyDeletedException`；
  - 领域校验：`DomainValidationException`（字段级错误携带 `field`）。
- 优点：应用层/基础设施统一抛出领域异常，API 层通过 `core/exceptions` 统一映射为响应格式与 HTTP 状态。

---

## 用户实体与服务
- 实体（`user/entity.py`）
  - 业务规则：邮箱/用户名/手机号格式校验；`activate()`/`deactivate()`；`change_password()`；`record_login()`；超管设置/撤销。
  - 重要约束：超管不可被停用（`SuperuserDeactivationForbiddenException`）。
- 领域服务（`user/service.py`）
  - 注册：校验密码强度、用户名/邮箱唯一、首个用户授予超管；记录 `UserCreated` 事件。
  - 认证：支持用户名/邮箱登录；密码校验与活跃状态检查；记录登录时间。
  - 改密：校验旧密码、强度、新旧不同；记录 `PasswordChanged` 事件。
  - 状态流转：`activate_user`/`deactivate_user` 及对应事件。
- 密码服务（`PasswordService`）：演示使用 PBKDF2；生产建议替换为 argon2/bcrypt。

---

## 文件资产聚合
- 实体（`file_asset/entity.py`）
  - 状态机：`pending` → `active` → `deleted`（允许从 active 直接 deleted，再次 pending/active 需业务场景重新入库）。
  - 元数据更新：`update_object_metadata(size/etag/content_type/url/metadata)`；所有时间戳统一为 UTC。
  - 声明式校验：非法状态将抛出 `DomainValidationException` 并附 allowed 列表。
- 仓储契约（`file_asset/repository.py`）
  - `create/update/delete/get_by_id/get_by_key/list/count`，不暴露 ORM 细节。

---

## UoW 抽象（common/unit_of_work.py）
- 控制多个仓储的一致性，抽象了 `commit/rollback` 与异步上下文协议。
- 只读模式：退出时不会提交，便于查询优化。

---

## 支付（协议与事件）
- 应用端口：`application/ports/payment_gateway.py` 定义协议（Protocol）：
  `create_payment/query_payment/refund/close_payment/parse_webhook`。
- 领域事件：`domain/payment/events.py` 定义 `PaymentSucceeded/Failed/Refunded/Canceled`；
  应用可在解释 Webhook 后投递到消息系统或编排后续用例。
- 分层原则：领域保持纯净；外部网关适配器放在 `infrastructure/external/payments/*`，
  通过工厂提供实现。

---

## 约定与最佳实践
- 领域不做 I/O：不读写数据库、不访问网络；时间一律使用 UTC aware；
- 实体首选 dataclass，Value Object 可按需引入；
- 异常与业务码集中在 `shared/codes.py` 与 `domain/common/exceptions.py`，避免多处枚举漂移；
- 通过领域事件传递“发生了什么”（facts），由外层决定如何处理（记录、通知、补偿）。
