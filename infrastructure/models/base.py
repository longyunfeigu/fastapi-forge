"""
数据库模型基类
"""
from sqlalchemy.ext.declarative import declarative_base

# 创建基类 - 所有模型都继承这个类
Base = declarative_base()

# 元数据对象用于数据库迁移
metadata = Base.metadata