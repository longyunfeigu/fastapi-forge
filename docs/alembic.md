# 迁移与数据库演进指南（alembic/）

本项目使用 Alembic 进行数据库迁移，异步应用通过 `alembic/env.py` 的 async engine 集成完成。生产环境只使用迁移，不在运行时自动建表（开发环境 `create_tables()` 仅用于快速起步）。

目录：
- `alembic.ini` — Alembic 主配置
- `alembic/env.py` — 连接与元数据装载、在线/离线迁移入口（已加载 `infrastructure.models.Base.metadata`）
- `alembic/versions/*.py` — 版本脚本

---

## 关键点
- 元数据来源：`from infrastructure.models import Base`，确保迁移基于项目内真实 ORM 模型。
- 数据库 URL：
  - 读取优先级：`DATABASE_URL` 或 `DATABASE__URL` 环境变量 → `.env` → 回退 `sqlite+aiosqlite:///./app.db`（开发便捷）。
- 在线迁移：使用 `async_engine_from_config`；
- 版本脚本：建议为重要 DDL 增加注释（`comment=`）以便维护。

---

## 常用命令
```
# 生成迁移（先修改/新增 SQLAlchemy 模型）
alembic revision --autogenerate -m "add user table"

# 升级到最新
alembic upgrade head

# 回滚一步
alembic downgrade -1
```

> 提示：生产库请先备份，再执行变更；若涉及大表/长事务，评估锁与业务窗口，必要时拆分为多步迁移。

---

## 与开发流程的关系
- 开发调试阶段可以使用 `infrastructure.database.create_tables()` 快速建表；
- 提交代码前应生成/更新 Alembic 迁移并在本地验证；
- CI/CD 建议在部署前执行 `alembic upgrade head` 并观测失败快速回滚。

