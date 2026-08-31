"""私信模型。"""
from datetime import datetime

from sqlalchemy import Column, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base


class Message(Base):
    __tablename__ = 'messages'

    id = Column(String(64), primary_key=True)
    user_id = Column(String(64), ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    content = Column(Text, nullable=False)
    anon_name = Column(String(64), nullable=True)
    status = Column(String(20), default='unread', index=True)  # unread / replied
    admin_reply = Column(Text, nullable=True)
    reply_time = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    chat_messages = relationship('ChatMessage', backref='conversation', lazy='dynamic', cascade='all, delete-orphan')

    def to_dict(self, with_user=True) -> dict:
        data = {
            'id': self.id,
            'user_id': self.user_id,
            'content': self.content,
            'anon_name': self.anon_name,
            'status': self.status,
            'admin_reply': self.admin_reply,
            'reply_time': self.reply_time.isoformat() if self.reply_time else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
        if with_user and hasattr(self, 'author') and self.author:
            data['user'] = self.author.to_dict()
        else:
            data['user'] = None
        return data
