"""SQLAlchemy 2.0 引擎 + 会话 + Base 声明基类 + get_db 依赖。"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from app.config import settings

# 创建引擎（MySQL 连接池配置）
engine = create_engine(
    settings.DATABASE_URL,
    pool_size=settings.POOL_SIZE,
    pool_recycle=settings.POOL_RECYCLE,
    pool_pre_ping=settings.POOL_PRE_PING,
    echo=settings.SQLALCHEMY_ECHO,
)

# 会话工厂
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

# 声明基类（所有模型继承）
Base = declarative_base()


def get_db():
    """FastAPI 依赖：提供数据库会话，请求结束自动关闭。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
