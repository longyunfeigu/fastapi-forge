# 开发指南（Development Guide）

本文档提供 FastAPI Forge 项目的开发工作流、工具配置和最佳实践。

---

## 环境搭建

### 1. 克隆项目

```bash
git clone https://github.com/yourusername/fastapi-forge.git
cd fastapi-forge
```

### 2. 安装依赖

```bash
# 生产依赖
pip install -r requirements.txt

# 开发依赖（包括代码质量工具）
pip install -r requirements-dev.txt
```

### 3. 配置环境变量

```bash
cp env.example .env
# 编辑 .env 文件，设置必要的配置（至少 SECRET_KEY）
```

### 4. 初始化数据库

```bash
# 运行迁移
alembic upgrade head
```

---

## Pre-commit Hooks（代码质量检查）

本项目使用 pre-commit 在提交代码前自动运行代码质量检查工具。

### 安装 Pre-commit

```bash
# 如果已安装 requirements-dev.txt，pre-commit 已包含
pip install pre-commit

# 安装 git hooks
pre-commit install
```

### 工具配置

项目配置了以下工具（在 `.pre-commit-config.yaml` 和 `pyproject.toml` 中）：

#### 1. **Black** - 代码格式化
- 行长度：100 字符
- 自动格式化 Python 代码
- 配置：`pyproject.toml` > `[tool.black]`

```bash
# 手动运行
black .
```

#### 2. **isort** - import 排序
- 按模块分组排序 import 语句
- 与 Black 兼容的配置
- 配置：`pyproject.toml` > `[tool.isort]`

```bash
# 手动运行
isort .
```

#### 3. **Flake8** - 代码风格检查
- 检查 PEP 8 规范
- 最大行长度：100
- 忽略规则：E203, E501, W503（与 Black 兼容）
- 配置：`pyproject.toml` > `[tool.flake8]`

```bash
# 手动运行
flake8 .
```

#### 4. **mypy** - 类型检查
- 静态类型检查
- 排除生成的代码（Alembic 迁移、gRPC stubs）
- 配置：`pyproject.toml` > `[tool.mypy]`

```bash
# 手动运行
mypy .
```

#### 5. **Bandit** - 安全检查
- 检测常见的安全问题
- 排除测试文件中的 assert
- 配置：`pyproject.toml` > `[tool.bandit]`

```bash
# 手动运行
bandit -r . -c pyproject.toml
```

### 手动运行所有检查

```bash
# 对所有文件运行 pre-commit
pre-commit run --all-files

# 只运行特定 hook
pre-commit run black --all-files
pre-commit run mypy --all-files
```

### 跳过 Pre-commit（不推荐）

```bash
# 仅在紧急情况下使用
git commit --no-verify -m "Emergency fix"
```

---

## Docker 开发

### Multi-stage 构建说明

项目使用优化的多阶段 Dockerfile：

1. **Stage 1: Builder** - 构建依赖
   - 安装编译工具
   - 编译 Python 包到虚拟环境

2. **Stage 2: Runtime** - 生产运行时
   - 最小化镜像（只包含运行时依赖）
   - 非 root 用户运行
   - 包含健康检查

3. **Stage 3: Development** - 开发环境
   - 包含开发工具
   - 支持代码热重载

### 构建镜像

```bash
# 生产镜像（默认）
docker build -t fastapi-forge:latest .

# 开发镜像
docker build --target development -t fastapi-forge:dev .
```

### 使用 Docker Compose

```bash
# 启动所有服务
docker-compose up -d

# 仅启动 API（开发模式，热重载）
docker-compose up app

# 启动 gRPC 服务
docker-compose up grpc

# 查看日志
docker-compose logs -f app

# 停止所有服务
docker-compose down

# 重新构建并启动
docker-compose up --build
```

### 进入容器调试

```bash
# 进入运行中的容器
docker-compose exec app bash

# 在容器中运行命令
docker-compose exec app alembic upgrade head
docker-compose exec app pytest tests/
```

---

## 测试

### 运行测试

```bash
# 运行所有测试
pytest tests/

# 运行特定测试文件
pytest tests/payments/test_service_idempotency.py

# 运行并显示详细输出
pytest tests/ -v

# 运行并生成覆盖率报告
pytest tests/ --cov=. --cov-report=html

# 并行运行测试（需要 pytest-xdist）
pytest tests/ -n auto

# 只运行单元测试
pytest tests/ -m unit

# 跳过慢测试
pytest tests/ -m "not slow"
```

### 测试标记

在 `pyproject.toml` 中定义了以下标记：

```python
@pytest.mark.unit
def test_something():
    pass

@pytest.mark.integration
def test_api():
    pass

@pytest.mark.slow
def test_long_running():
    pass
```

---

## 国际化开发指南（i18n）

本项目采用 gettext + Babel 的国际化方案，遵循“分层职责清晰”的原则：

- Domain/应用层：只产生“消息键 + 参数”（不拼自然语言）。
- API/任务：根据当前 locale 翻译键为最终文本（`core.i18n.t()`），将文本放入响应或通知。
- 翻译资源：`locales/<lang>/LC_MESSAGES/messages.po|mo`。

### 运行时语言选择

解析优先级：`?lang=xx` > `X-Lang` > `Accept-Language` > 默认 `en`。语言由 `api/middleware/locale.py` 写入 `ContextVar`，使用 `core.i18n.get_locale()` 可读取。

### 在代码中使用

```python
from core.i18n import t

# 成功消息
msg = t("user.register.success")

# 动态参数
msg = t("user.sessions.list.success", count=3)
```

业务异常建议携带 `message_key` 与 `details`，由 API handler 统一翻译：

```python
from domain.common.exceptions import BusinessException
raise BusinessException(code=..., message="User not found", message_key="user.not_found", details={"user_id": 1})
```

### Babel 工具链

配置文件：`babel.cfg`

常用命令：

```bash
# 抽取可翻译字符串到模板
pybabel extract -F babel.cfg -o locales/messages.pot .

# 初始化语言（仅首次）
pybabel init -i locales/messages.pot -d locales -l en
pybabel init -i locales/messages.pot -d locales -l zh_Hans

# 翻译后编译（生成 .mo）
pybabel compile -d locales

# 更新已有语言（当新增/修改了键）
pybabel update -i locales/messages.pot -d locales
```

### 质量与校验

- Pre-commit 已加入 `.po` 语法校验：`scripts/validate_po.py` 使用 `polib` 解析所有 `.po`。
- CI/本地均可运行：`pre-commit run --all-files`。

### 翻译规范

- 使用稳定的“键名”作为消息 ID（如 `user.register.success`），避免英文原文作为 ID。
- 字符串参数使用 `{name}` 占位，不要字符串拼接。
- 日志不做国际化，避免影响检索与排查。


## 数据库迁移

### 创建新迁移

```bash
# 自动检测模型变更并生成迁移
alembic revision --autogenerate -m "描述你的变更"

# 手动创建空迁移
alembic revision -m "描述你的变更"
```

### 应用迁移

```bash
# 升级到最新版本
alembic upgrade head

# 升级一步
alembic upgrade +1

# 降级一步
alembic downgrade -1

# 降级到特定版本
alembic downgrade <revision_id>
```

### 查看迁移历史

```bash
# 查看当前版本
alembic current

# 查看所有迁移
alembic history

# 查看迁移详情
alembic show <revision_id>
```

---

## gRPC 开发

### 修改 Proto 文件

1. 编辑 `.proto` 文件：`grpc_app/protos/forge/v1/*.proto`
2. 重新生成代码：

```bash
bash scripts/gen_protos.sh
```

3. 实现服务：`grpc_app/services/`

### 测试 gRPC

```bash
# 使用 grpcurl（需要安装）
grpcurl -plaintext localhost:50051 list
grpcurl -plaintext localhost:50051 forge.v1.UserService/Health

# 或者运行 gRPC 测试
pytest tests/grpc/
```

---

## 代码风格指南

### 1. 命名约定

- **模块/文件**：`snake_case.py`
- **类**：`CapWords`
- **函数/变量**：`snake_case`
- **常量**：`UPPER_CASE`
- **私有成员**：`_leading_underscore`

### 2. Import 顺序

```python
# 1. 标准库
import os
from datetime import datetime

# 2. 第三方库
from fastapi import APIRouter
from sqlalchemy import select

# 3. 本地模块（按层级）
from domain.user.entity import User
from application.services.user_service import UserService
from infrastructure.repositories.user_repository import SQLAlchemyUserRepository
from core.config import settings
```

### 3. 类型注解

所有公共函数必须有类型注解：

```python
def process_payment(amount: Decimal, currency: str) -> PaymentIntent:
    ...

async def get_user(user_id: int) -> Optional[User]:
    ...
```

### 4. 文档字符串

使用 Google 风格的 docstring：

```python
def calculate_total(items: List[Item]) -> Decimal:
    """计算订单总额。

    Args:
        items: 订单项列表

    Returns:
        订单总金额（含税）

    Raises:
        ValueError: 当订单项为空时
    """
```

---

## 日志约定

### 使用 structlog

```python
from core.logging_config import get_logger

logger = get_logger(__name__)

# 结构化日志（推荐）
logger.info("user_created", user_id=user.id, username=user.username)

# ❌ 不要使用标准库 logging
import logging  # 避免
```

### 日志级别

- `logger.debug()` - 调试信息（开发环境）
- `logger.info()` - 正常流程日志
- `logger.warning()` - 警告（可恢复的异常情况）
- `logger.error()` - 错误（需要关注）
- `logger.critical()` - 严重错误（系统故障）

---

## 性能分析

### 使用 cProfile

```bash
python -m cProfile -o profile.stats main.py
```

### 使用 py-spy（推荐）

```bash
pip install py-spy

# 实时采样
py-spy top -- python main.py

# 生成火焰图
py-spy record -o profile.svg -- python main.py
```

---

## 调试技巧

### 1. 使用 ipdb

```python
import ipdb; ipdb.set_trace()  # 设置断点
```

### 2. FastAPI 调试模式

在 `.env` 中设置：

```
DEBUG=true
```

### 3. 查看 SQL 查询

```python
# 在 infrastructure/database.py 中启用 echo
engine = create_async_engine(url, echo=True)  # 打印所有 SQL
```

---

## 常见问题

### Q: Pre-commit 太慢怎么办？

A: 可以跳过 mypy（最慢的检查）：

```bash
SKIP=mypy git commit -m "your message"
```

### Q: Docker 镜像太大？

A: 使用多阶段构建（已配置）并清理缓存：

```bash
docker image prune -a
```

### Q: 迁移冲突怎么办？

A: 合并分支后重新生成：

```bash
alembic downgrade base
alembic revision --autogenerate -m "merged migration"
```

---

## 贡献指南

1. Fork 项目
2. 创建特性分支：`git checkout -b feature/my-feature`
3. 提交变更：`git commit -m "feat: add my feature"`（遵循 Conventional Commits）
4. 推送分支：`git push origin feature/my-feature`
5. 创建 Pull Request

### Commit 消息规范

使用 [Conventional Commits](https://www.conventionalcommits.org/)：

```
feat: 新功能
fix: 修复 bug
docs: 文档更新
style: 代码格式（不影响功能）
refactor: 重构
test: 测试
chore: 构建/工具链
```

---

## 参考资源

- [FastAPI 文档](https://fastapi.tiangolo.com/)
- [SQLAlchemy 文档](https://docs.sqlalchemy.org/)
- [Alembic 文档](https://alembic.sqlalchemy.org/)
- [Black 文档](https://black.readthedocs.io/)
- [Pre-commit 文档](https://pre-commit.com/)
