"""用户模型。"""
from datetime import datetime

from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base


class User(Base):
    __tablename__ = 'users'

    id = Column(String(64), primary_key=True)
    wecom_user_id = Column(String(128), unique=True, nullable=True)  # 企业微信 UserId
    nickname = Column(String(64), nullable=False)
    avatar = Column(String(512), nullable=True)
    department = Column(String(128), nullable=True)
    is_admin = Column(Boolean, default=False)
    role = Column(String(20), default='user', index=True)  # user / admin / super_admin
    admin_password = Column(String(256), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    voices = relationship('Voice', backref='author', lazy='dynamic')
    comments = relationship('Comment', backref='author', lazy='dynamic')
    ideas = relationship('Idea', backref='author', lazy='dynamic')
    feedbacks = relationship('Feedback', backref='author', lazy='dynamic')
    messages = relationship('Message', backref='author', lazy='dynamic')
    notifications = relationship('Notification', backref='user', lazy='dynamic')

    def to_dict(self, include_wecom_id=False) -> dict:
        d = {
            'id': self.id,
            'nickname': self.nickname,
            'avatar': self.avatar,
            'department': self.department or '',
            'is_admin': self.is_admin or self.role in ('super_admin', 'admin'),
            'role': self.role or 'user',
            'is_super_admin': self.role == 'super_admin',
            'is_logged_in': self.wecom_user_id is not None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
        if include_wecom_id:
            d['wecom_user_id'] = self.wecom_user_id
        return d
