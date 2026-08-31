"""金点子相关 Pydantic 模型（含输入校验）。"""
from typing import Optional

from pydantic import BaseModel, Field


class IdeaCreate(BaseModel):
    """创建金点子请求。"""
    title: str = Field(..., min_length=1, max_length=100, description='金点子标题（1-100字）')
    desc: str = Field('', max_length=1000, description='金点子描述（最多1000字）')
    category: str = Field('其他', max_length=32, description='分类')
    anonName: Optional[str] = Field(None, max_length=64, description='匿名昵称')
    isAnonymous: bool = Field(True, description='是否匿名')
