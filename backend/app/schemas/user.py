"""用户管理相关 Pydantic 模型。"""
from typing import Optional

from pydantic import BaseModel


class UserRoleUpdate(BaseModel):
    """用户角色更新请求。"""
    role: str
    nickname: Optional[str] = None
