"""公告模型。"""
from datetime import datetime

from sqlalchemy import Column, String, Text, Boolean, DateTime

from app.database import Base


class Announce(Base):
    __tablename__ = 'announces'

    id = Column(String(64), primary_key=True)
    title = Column(String(256), nullable=False)
    content = Column(Text, nullable=True)
    is_pinned = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'title': self.title,
            'content': self.content,
            'is_pinned': self.is_pinned,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
