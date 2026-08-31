"""JWT Token 黑名单模型（支持 token 撤销机制）。"""
from datetime import datetime

from sqlalchemy import Column, String, DateTime, Boolean

from app.database import Base


class TokenBlacklist(Base):
    """已撤销的 JWT Token 黑名单。

    用户登出 / 退出管理员模式时，将当前 token 的 jti 写入黑名单。
    每次请求鉴权时检查 jti 是否在黑名单中，实现 token 撤销。
    过期记录由定时任务清理。
    """
    __tablename__ = 'token_blacklist'

    id = Column(String(64), primary_key=True)
    jti = Column(String(64), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
