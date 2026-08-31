"""认证相关 Pydantic 模型（含输入校验）。"""
from typing import Optional

from pydantic import BaseModel


class UserResponse(BaseModel):
    """用户信息响应。"""
    id: str
    nickname: str
    avatar: Optional[str] = None
    department: Optional[str] = ''
    is_admin: bool = False
    role: str = 'user'
    is_super_admin: bool = False
    is_logged_in: bool = False
