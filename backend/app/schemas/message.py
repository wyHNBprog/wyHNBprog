"""私信相关 Pydantic 模型（含输入校验）。"""
from typing import Optional

from pydantic import BaseModel, Field


class MessageCreate(BaseModel):
    """创建私信请求。"""
    content: str = Field(..., min_length=1, max_length=1000, description='私信内容（1-1000字）')
    anonName: Optional[str] = Field(None, max_length=64, description='匿名昵称')


class MessageReplyCreate(BaseModel):
    """私信回复请求。"""
    content: str = Field(..., min_length=1, max_length=1000, description='回复内容（1-1000字）')
