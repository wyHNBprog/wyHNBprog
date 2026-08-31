"""通知模型：Notification + AdminConfig。

注意：type 字段用 db.Column('notification_type', ...) 避免保留字。
"""
from datetime import datetime

from sqlalchemy import Column, String, Boolean, Integer, DateTime, ForeignKey

from app.database import Base


class Notification(Base):
    __tablename__ = 'notifications'

    id = Column(String(64), primary_key=True)
    user_id = Column(String(64), ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    # MySQL 保留字 type，显式指定列名 notification_type
    type = Column('notification_type', String(32), nullable=False)
    text = Column(String(512), nullable=False)
    is_read = Column(Boolean, default=False, index=True)
    related_id = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'user_id': self.user_id,
            'type': self.type,
            'text': self.text,
            'is_read': self.is_read,
            'related_id': self.related_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class AdminConfig(Base):
    __tablename__ = 'admin_config'

    id = Column(Integer, primary_key=True, autoincrement=True)
    config_key = Column(String(64), unique=True, nullable=False)
    config_value = Column(String(512), nullable=False)

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'config_key': self.config_key,
            'config_value': self.config_value,
        }
