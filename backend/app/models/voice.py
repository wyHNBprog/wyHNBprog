"""心声模型：Voice + VoiceLike + VoiceTag。"""
from datetime import datetime

from sqlalchemy import Column, String, Text, Boolean, Integer, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship

from app.database import Base


class Voice(Base):
    __tablename__ = 'voices'

    id = Column(String(64), primary_key=True)
    user_id = Column(String(64), ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    content = Column(Text, nullable=False)
    anon_name = Column(String(64), nullable=True)
    is_anonymous = Column(Boolean, default=False)
    like_count = Column(Integer, default=0)
    status = Column(String(20), default='pending', index=True)  # pending / approved / rejected
    reject_reason = Column(String(512), nullable=True)
    review_cleared = Column(Boolean, default=False, index=True)  # 管理员清除审核记录后置 True
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    comments = relationship('Comment', backref='voice', lazy='select', cascade='all, delete-orphan')
    likes = relationship('VoiceLike', backref='voice', lazy='dynamic', cascade='all, delete-orphan')
    tags = relationship('VoiceTag', backref='voice', lazy='joined', cascade='all, delete-orphan')

    def to_dict(self, with_user=True) -> dict:
        data = {
            'id': self.id,
            'user_id': self.user_id,
            'content': self.content,
            'anon_name': self.anon_name,
            'is_anonymous': self.is_anonymous,
            'like_count': self.like_count,
            'status': self.status,
            'reject_reason': self.reject_reason,
            'review_cleared': self.review_cleared or False,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'comment_count': len([c for c in (self.comments or []) if c.status == 'approved']),
            'tags': [t.tag for t in (self.tags or [])],
        }
        if with_user and hasattr(self, 'author') and self.author:
            data['user'] = self.author.to_dict()
        else:
            data['user'] = None
        return data


class VoiceLike(Base):
    __tablename__ = 'voice_likes'

    id = Column(String(64), primary_key=True)
    voice_id = Column(String(64), ForeignKey('voices.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id = Column(String(64), ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint('voice_id', 'user_id', name='uk_voice_user'),
    )


class VoiceTag(Base):
    __tablename__ = 'voice_tags'

    id = Column(String(64), primary_key=True)
    voice_id = Column(String(64), ForeignKey('voices.id', ondelete='CASCADE'), nullable=False, index=True)
    tag = Column(String(32), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint('voice_id', 'tag', name='uk_voice_tag'),
    )
