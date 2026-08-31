"""依赖注入：当前用户 / 管理员 / 超级管理员（含 JWT 黑名单检查）。"""
from typing import Optional

from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.security import decode_token, is_token_revoked
from app.models.user import User
from app.utils import set_current_uid

# OAuth2 Bearer token 提取器（auto_error=False 允许无 token 请求通过）
oauth2_scheme = OAuth2PasswordBearer(tokenUrl='/api/wecom/login-url', auto_error=False)


def get_current_user_optional(
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """获取当前用户（可选）：无 token 或 token 无效或已撤销时返回 None。"""
    if not token:
        return None
    payload = decode_token(token)
    if not payload:
        return None
    uid = payload.get('sub')
    if not uid:
        return None
    # JWT 黑名单检查：已撤销的 token 返回 None
    if is_token_revoked(token, db):
        return None
    return db.get(User, uid)


def get_current_user_required(
    user: Optional[User] = Depends(get_current_user_optional),
) -> User:
    """获取当前用户（必须）：未登录抛出 401。"""
    if not user:
        raise HTTPException(status_code=401, detail='请先登录')
    return user


def get_user_with_context(
    user: Optional[User] = Depends(get_current_user_optional),
) -> Optional[User]:
    """获取当前用户并设置上下文（序列化函数用）。

    在路由中使用此依赖可自动将当前用户 ID 写入 contextvars，
    使 voice_to_dict / idea_to_dict 等序列化函数能正确计算 isMine/isLiked。
    """
    set_current_uid(user.id if user else None)
    return user


def get_user_with_context_required(
    user: User = Depends(get_current_user_required),
) -> User:
    """获取当前用户并设置上下文（必须登录）。

    与 get_user_with_context 相同，但未登录时抛出 401。
    用于强制登录的数据接口。
    """
    set_current_uid(user.id)
    return user


def get_current_admin(
    user: Optional[User] = Depends(get_current_user_optional),
) -> User:
    """获取当前管理员：未登录抛出 401，已登录但非管理员抛出 403。"""
    if not user:
        raise HTTPException(status_code=401, detail='请先登录')
    if not (user.is_admin or user.role in ('super_admin', 'admin')):
        raise HTTPException(status_code=403, detail='需要管理员权限')
    return user


def get_current_super_admin(
    user: Optional[User] = Depends(get_current_user_optional),
) -> User:
    """获取当前超级管理员：未登录抛出 401，已登录但非超管抛出 403。"""
    if not user:
        raise HTTPException(status_code=401, detail='请先登录')
    if user.role != 'super_admin':
        raise HTTPException(status_code=403, detail='需要超级管理员权限')
    return user


def decode_token_safe(token: str) -> Optional[str]:
    """安全解码 JWT token，返回 user_id（sub 声明）或 None。

    用于 WebSocket / SSE 等无法使用标准 Depends 注入的场景，
    从 query param 读取 token 后调用此函数获取用户 ID。
    包含 token 黑名单检查，已撤销的 token 返回 None。
    """
    if not token:
        return None
    payload = decode_token(token)
    if not payload:
        return None
    # 检查 token 黑名单（is_token_revoked 接收原始 token 字符串）
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        if is_token_revoked(token, db):
            return None
    finally:
        db.close()
    return payload.get('sub')
