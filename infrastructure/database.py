"""
数据库配置和连接管理
"""
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.engine import make_url
from typing import AsyncGenerator

from core.config import settings
from infrastructure.models import Base

# 创建异步引擎
def _build_async_url(database_url: str) -> str:
    """确保数据库URL使用异步驱动"""
    url = make_url(database_url)
    drivername = url.drivername

    if "+" in drivername:
        return database_url

    driver_map = {
        "postgresql": "postgresql+asyncpg",
        "postgres": "postgresql+asyncpg",
        "mysql": "mysql+aiomysql",
        "sqlite": "sqlite+aiosqlite",
    }

    if drivername not in driver_map:
        raise ValueError(f"不支持的数据库驱动: {drivername}. 请使用 async 驱动或更新DATABASE_URL")

    async_driver = driver_map[drivername]
    return str(url.set(drivername=async_driver))


engine = create_async_engine(
    _build_async_url(settings.DATABASE_URL),
    echo=settings.DEBUG,
    future=True
)

# 创建异步会话工厂 (SQLAlchemy 1.4 兼容)
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """获取数据库会话（不自动提交，由调用方控制事务）

    使用异步上下文管理器自动关闭会话，无需显式 close。
    """
    async with AsyncSessionLocal() as session:
        yield session


async def create_tables():
    """
    创建所有表
    
    根据models中定义的所有模型创建对应的数据库表
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def drop_tables():
    """
    删除所有表
    
    警告：仅用于测试环境，会删除所有数据！
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
