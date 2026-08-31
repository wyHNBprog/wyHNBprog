"""金点子模型：Idea + IdeaVote。"""
from datetime import datetime

from sqlalchemy import Column, String, Text, Boolean, Integer, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship

from app.database import Base


class Idea(Base):
    __tablename__ = 'ideas'

    id = Column(String(64), primary_key=True)
    user_id = Column(String(64), ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    title = Column(String(256), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(32), nullable=True)
    expected_benefit = Column(Text, nullable=True)
    vote_count = Column(Integer, default=0)
    has_flower = Column(Boolean, default=False)
    flower_count = Column(Integer, default=0)
    has_firework = Column(Boolean, default=False)
    firework_count = Column(Integer, default=0)
    anon_name = Column(String(64), nullable=True)
    is_anonymous = Column(Boolean, default=True)
    status = Column(String(20), default='pending', index=True)  # pending / approved / voting / rejected
    reject_reason = Column(String(512), nullable=True)
    review_cleared = Column(Boolean, default=False, index=True)  # 管理员清除审核记录后置 True
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    votes = relationship('IdeaVote', backref='idea', lazy='dynamic', cascade='all, delete-orphan')

    def to_dict(self, with_user=True) -> dict:
        data = {
            'id': self.id,
            'user_id': self.user_id,
            'title': self.title,
            'description': self.description,
            'category': self.category,
            'expected_benefit': self.expected_benefit,
            'vote_count': self.vote_count,
            'has_flower': self.has_flower,
            'flower_count': self.flower_count or 0,
            'has_firework': self.has_firework or False,
            'firework_count': self.firework_count or 0,
            'anon_name': self.anon_name or '匿名',
            'is_anonymous': self.is_anonymous,
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


class IdeaVote(Base):
    __tablename__ = 'idea_votes'

    id = Column(String(64), primary_key=True)
    idea_id = Column(String(64), ForeignKey('ideas.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id = Column(String(64), ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint('idea_id', 'user_id', name='uk_idea_user'),
    )
