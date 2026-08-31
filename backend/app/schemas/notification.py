"""通知相关 Pydantic 模型（含输入校验）。"""
from typing import Optional

from pydantic import BaseModel, Field


class NotificationCreate(BaseModel):
    """创建通知请求。"""
    type: str = Field('system', max_length=64, description='通知类型')
    text: str = Field(..., min_length=1, max_length=512, description='通知内容（1-512字）')
