"""通用响应模型。"""
from typing import Any, Optional

from pydantic import BaseModel


class ApiResponse(BaseModel):
    """通用 API 响应包装。"""
    code: int = 200
    message: str = 'OK'
    data: Optional[Any] = None


class OkResponse(BaseModel):
    """简单成功响应。"""
    ok: bool = True
