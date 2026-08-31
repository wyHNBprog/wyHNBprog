"""反馈相关 Pydantic 模型（含输入校验）。"""
from typing import Optional

from pydantic import BaseModel, Field


class FeedbackCreate(BaseModel):
    """创建反馈请求。"""
    content: str = Field(..., min_length=1, max_length=1000, description='反馈内容（1-1000字）')
    category: str = Field('其他', max_length=32, description='反馈分类')
    anonName: Optional[str] = Field(None, max_length=64, description='匿名昵称')
    contact: Optional[str] = Field(None, max_length=128, description='联系方式')


class FeedbackReplyCreate(BaseModel):
    """反馈回复请求。"""
    reply: str = Field(..., min_length=1, max_length=1000, description='回复内容（1-1000字）')
