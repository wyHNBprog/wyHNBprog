"""评论模型：Comment + CommentLike。"""
from datetime import datetime

from sqlalchemy import Column, String, Text, Boolean, Integer, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship

from app.database import Base


class Comment(Base):
    __tablename__ = 'comments'

    id = Column(String(64), primary_key=True)
    voice_id = Column(String(64), ForeignKey('voices.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id = Column(String(64), ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    content = Column(Text, nullable=False)
    anon_name = Column(String(64), nullable=True)
    like_count = Column(Integer, default=0)
    status = Column(String(20), default='pending', index=True)  # pending / approved / rejected
    reject_reason = Column(String(512), nullable=True)
    review_cleared = Column(Boolean, default=False, index=True)  # 管理员清除审核记录后置 True
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    likes = relationship('CommentLike', backref='comment', lazy='dynamic', cascade='all, delete-orphan')

    def to_dict(self, with_user=True) -> dict:
        data = {
            'id': self.id,
            'voice_id': self.voice_id,
            'user_id': self.user_id,
            'content': self.content,
            'anon_name': self.anon_name,
            'like_count': self.like_count,
            'status': self.status,
            'reject_reason': self.reject_reason,
            'review_cleared': self.review_cleared or False,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
        if with_user and hasattr(self, 'author') and self.author:
            data['user'] = self.author.to_dict()
        else:
            data['user'] = None
        return data


class CommentLike(Base):
    __tablename__ = 'comment_likes'

    id = Column(String(64), primary_key=True)
    comment_id = Column(String(64), ForeignKey('comments.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id = Column(String(64), ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint('comment_id', 'user_id', name='uk_comment_user'),
    )
