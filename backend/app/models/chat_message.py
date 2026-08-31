"""聊天消息模型：私信多轮对话中的单条消息。

conversation_id 关联到 Message 表（作为会话容器）。
sender_type 区分发送方：'user'（普通用户）或 'admin'（管理员）。
"""
from datetime import datetime

from sqlalchemy import Column, String, Text, Boolean, DateTime, ForeignKey

from app.database import Base


class ChatMessage(Base):
    __tablename__ = 'chat_messages'

    id = Column(String(64), primary_key=True)
    conversation_id = Column(
        String(64),
        ForeignKey('messages.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    sender_type = Column(String(10), nullable=False)  # 'user' / 'admin'
    sender_id = Column(String(64), nullable=True)
    content = Column(Text, nullable=False)
    is_read = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'conversationId': self.conversation_id,
            'senderType': self.sender_type,
            'senderId': self.sender_id,
            'content': self.content,
            'isRead': self.is_read or False,
            'createdAt': self.created_at.isoformat() if self.created_at else None,
        }
