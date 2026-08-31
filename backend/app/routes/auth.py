"""认证路由：认证配置 / 用户信息 / 管理员状态 / Token 撤销。

仅支持企业微信 OAuth 登录（wecom_auth.py），管理员由数据库 is_admin 字段指定。
JWT 撤销机制：logout 时将 token jti 写入黑名单。
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.deps import get_current_user_optional, get_user_with_context, oauth2_scheme
from app.models.user import User
from app.security import decode_token, is_token_revoked, revoke_token
from app.services.points import calc_user_total_points
from app.utils import set_current_uid

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get('/api/auth/config')
def auth_config():
    """返回认证配置：前端据此决定是否显示企微登录页。"""
    return {
        'wecom_enabled': settings.wecom_enabled,
    }


@router.get('/api/auth/me')
def auth_me(
    token: Optional[str] = None,
    user: User = Depends(get_user_with_context),
    db: Session = Depends(get_db),
):
    """获取当前登录用户信息。

    返回 user 对象（含昵称、头像、部门）或 None。
    isAdmin 字段表示当前用户是否为管理员。
    支持 WeChat OAuth token 通过 URL 参数传入。
    """
    # 如果依赖注入未获取到用户（无 Authorization header），尝试从 URL 参数获取 token
    if not user and token:
        payload = decode_token(token)
        if payload:
            uid = payload.get('sub')
            if uid:
                # 直接用 jti 查询黑名单，避免 is_token_revoked 内部重复 decode_token
                jti = payload.get('jti')
                if jti:
                    from app.models.token_blacklist import TokenBlacklist
                    blacklisted = db.query(TokenBlacklist).filter_by(jti=jti).first()
                    if blacklisted:
                        return {'user': None}
                user = db.get(User, uid)
                if user:
                    set_current_uid(user.id)

    if not user:
        return {'user': None}
    data = user.to_dict()
    data['is_logged_in'] = True
    data['isAdmin'] = user.is_admin or user.role in ('super_admin', 'admin')
    data['is_super_admin'] = user.role == 'super_admin'
    data['points'] = calc_user_total_points(db, user.id)
    return {'user': data}


@router.post('/api/auth/logout')
def auth_logout(
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
):
    """退出登录：将当前 token 加入黑名单（撤销）。"""
    if token:
        revoke_token(token, db)
    return {'ok': True}


# ========== 管理员状态检查 ==========

@router.get('/api/admin/status')
def admin_status(user: User = Depends(get_current_user_optional)):
    """检查当前 JWT 用户是否为管理员，并返回 isSuperAdmin 字段。

    管理员身份由数据库 is_admin 字段决定，无前端登录入口。
    """
    is_admin = bool(user and (user.is_admin or user.role in ('super_admin', 'admin')))
    is_super = bool(user and user.role == 'super_admin')
    return {'isAdmin': is_admin, 'isSuperAdmin': is_super}
