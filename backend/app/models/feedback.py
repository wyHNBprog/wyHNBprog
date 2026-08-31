"""反馈模型：Feedback + FeedbackReply。

注意：type 字段用 db.Column('feedback_type', ...) 避免保留字。
"""
from datetime import datetime

from sqlalchemy import Column, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base


class Feedback(Base):
    __tablename__ = 'feedbacks'

    id = Column(String(64), primary_key=True)
    user_id = Column(String(64), ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    # MySQL 保留字 type，显式指定列名 feedback_type
    type = Column('feedback_type', String(32), nullable=True)
    content = Column(Text, nullable=True)
    is_anonymous = Column(Boolean, default=False)
    anon_name = Column(String(64), nullable=True)
    contact = Column(String(128), nullable=True)
    status = Column(String(20), default='pending', index=True)  # pending / replied
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    replies = relationship('FeedbackReply', backref='feedback', lazy='dynamic', cascade='all, delete-orphan')

    def to_dict(self, with_user=True) -> dict:
        data = {
            'id': self.id,
            'user_id': self.user_id,
            'type': self.type,
            'content': self.content,
            'is_anonymous': self.is_anonymous,
            'anon_name': self.anon_name,
            'contact': self.contact,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'reply_count': self.replies.count(),
        }
        if with_user and hasattr(self, 'author') and self.author:
            data['user'] = self.author.to_dict()
        else:
            data['user'] = None
        return data


class FeedbackReply(Base):
    __tablename__ = 'feedback_replies'

    id = Column(String(64), primary_key=True)
    feedback_id = Column(String(64), ForeignKey('feedbacks.id', ondelete='CASCADE'), nullable=False, index=True)
    admin_id = Column(String(64), ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'feedback_id': self.feedback_id,
            'admin_id': self.admin_id,
            'content': self.content,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
