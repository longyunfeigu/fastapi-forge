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

### 测试
```bash
pytest tests/
```

## 📄 License

MIT