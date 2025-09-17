# FastAPI DDD用户管理系统

基于领域驱动设计（DDD）架构的FastAPI用户管理系统。

## 📁 项目结构

```
fastapi-ddd-user/
├── domain/                 # 领域层 - 纯业务逻辑
│   └── user/
│       ├── entity.py      # 用户实体（包含业务规则）
│       ├── repository.py  # 仓储接口（抽象）
│       ├── service.py     # 领域服务（复杂业务逻辑）
│       └── events.py      # 领域事件
│
├── application/            # 应用层 - 编排领域层
│   ├── user_service.py   # 编排领域服务
│   └── dto.py            # 数据传输对象
│
├── infrastructure/        # 基础设施层 - 技术实现
│   ├── repositories/     # 仓储实现
│   │   └── user_repository.py  # SQLAlchemy实现
│   └── database.py       # 数据库配置
│
├── api/                  # 表现层 - API接口
│   ├── routes/
│   │   └── user.py      # 用户路由
│   └── dependencies.py  # 依赖注入
│
├── core/                # 核心配置
│   └── config.py       # 项目配置
│
└── main.py             # 应用入口
```

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

复制 `.env.example` 为 `.env` 并修改配置：

```bash
cp .env.example .env
```

### 3. 使用Docker Compose启动

```bash
docker-compose up -d
```

### 4. 直接运行

```bash
# 确保PostgreSQL已运行
python main.py
```

## 📚 API文档

启动后访问：
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 🔑 主要功能

### 用户管理
- ✅ 用户注册（首个用户自动成为超管）
- ✅ 用户登录（JWT认证）
- ✅ 获取用户信息
- ✅ 更新用户资料
- ✅ 修改密码
- ✅ 用户列表（需要超管权限）
- ✅ 激活/停用用户（需要超管权限）
- ✅ 删除用户（需要超管权限）

### 业务规则
- 用户名：3-20字符，只含字母数字下划线
- 密码：至少8位，包含大小写字母和数字
- 邮箱：标准邮箱格式验证
- 手机号：中国手机号格式（可选）
- 超管不能被停用

## 🏗️ DDD架构特点

### 领域层（Domain）
- **纯业务逻辑**：不依赖任何技术实现
- **业务规则封装**：所有业务规则在实体中
- **领域服务**：处理复杂的跨实体业务
- **领域事件**：记录重要的业务事件

### 应用层（Application）
- **用例编排**：组织领域服务完成用例
- **DTO转换**：处理数据传输对象
- **事务边界**：管理业务事务
- **JWT认证**：处理令牌生成和验证

### 基础设施层（Infrastructure）
- **仓储实现**：SQLAlchemy异步实现
- **数据库配置**：PostgreSQL异步连接
- **外部服务**：第三方API集成（预留）

### API层（Presentation）
- **FastAPI路由**：RESTful API接口
- **依赖注入**：认证和授权中间件
- **异常处理**：统一的错误响应
- **API文档**：自动生成的OpenAPI文档

## 🔒 安全特性

- JWT令牌认证
- 密码哈希存储（PBKDF2）
- 角色权限控制（超管/普通用户）
- CORS配置
- 环境变量配置敏感信息

## 📝 开发说明

### 添加新功能
1. 在`domain`层定义业务规则
2. 在`application`层编排业务逻辑
3. 在`infrastructure`层实现技术细节
4. 在`api`层暴露接口

### 日志约定
- 统一使用 `core.logging_config.get_logger(__name__)` 获取 `logger`。
- 不使用标准库 `logging.getLogger` 直接输出，确保日志经过 structlog 处理链（开发环境控制台可读、生产环境 JSON）。
- 外围模块（Celery 任务、外部客户端、Redis 客户端等）同样遵循本约定。

### 请求日志中间件（可开关/脱敏）
- 按环境与请求头控制是否记录请求体：
  - DEBUG 环境默认启用（可通过配置项关闭）。
  - 单次请求可用请求头覆盖：`X-Log-Body: true|false`。
- 敏感字段自动脱敏：`password`、`old_password`、`new_password`、`token`、`access_token`、`refresh_token`、`secret`、`api_key` 等将被替换为 `***`。
- 体积限制：仅记录前 N 字节，避免大包影响（默认 2048 字节，可配置）。
- multipart/form-data：默认不记录，避免解析文件；可通过配置仅记录标识（不读取文件）。

可用配置（`.env`）

```
# 是否默认记录请求体（仅在 DEBUG 下生效）；请求头 X-Log-Body 可覆盖
LOG_REQUEST_BODY_ENABLE_BY_DEFAULT=true

# 请求体记录最大字节数
LOG_REQUEST_BODY_MAX_BYTES=2048

# 是否允许记录 multipart/form-data（仅记录 {"multipart": true}，不解析文件）
LOG_REQUEST_BODY_ALLOW_MULTIPART=false
```

注意
- 仅对 `POST/PUT/PATCH` 请求尝试记录请求体。
- 记录的数据用于调试/审计，请按需开启并妥善管理日志访问权限。

### 并发下首个超管的分布式锁
- 目标：确保“首个注册用户自动成为超级管理员”在并发注册时不被破坏（避免多个超管）。
- 策略：
  - 注册前先只读统计总用户数；若可能为 0，则尝试获取 Redis 分布式锁 `first_superuser_init`。
  - 在锁内再次统计确认后执行注册与授予逻辑，确保同一时刻只有一个请求能成为首个用户。
  - 未配置 Redis 时走回退路径（仍可能存在极小概率竞态）。

建议配置（`.env`）

```
# 启用 Redis 以获得强一致的首超判定（同时也用于缓存/任务队列）
REDIS_URL=redis://localhost:6379/0
```

说明
- 锁超时与阻塞等待可通过以下配置调整（单位：秒）：

```
# 分布式锁持有超时时间
FIRST_SUPERUSER_LOCK_TIMEOUT=10

# 获取锁的阻塞等待时间
FIRST_SUPERUSER_LOCK_BLOCKING_TIMEOUT=10
```

- 若生产环境对“首个超管”有更严格要求，建议通过初始化脚本/迁移任务显式创建超管，避免运行时判定。

自动续租（可选）
- 为避免长耗时任务持锁过期，可启用自动续租：

```
# 是否默认启用 Redis 锁自动续租（可在调用处覆盖 auto_renew 参数）
REDIS_LOCK_AUTO_RENEW_DEFAULT=false

# 自动续租的间隔比例（相对于 TTL），建议 0.4~0.6
REDIS_LOCK_AUTO_RENEW_INTERVAL_RATIO=0.6

# 续租间隔的抖动比例（避免续租尖峰），建议 0.05~0.2
REDIS_LOCK_AUTO_RENEW_JITTER_RATIO=0.1
```

使用说明
- 代码中可通过 `cache.lock(key, timeout=10, auto_renew=True)` 开启自动续租；若未提供 `auto_renew`，默认按上述配置决定。
- 续租间隔默认按 `interval = ratio * timeout` 计算，并加入抖动；建议续租间隔小于 TTL 的一半，以预留抖动与重试空间。

### 测试
```bash
pytest tests/
```

## 📄 License

MIT
