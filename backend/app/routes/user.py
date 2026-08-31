"""用户管理路由：用户列表 + 角色管理 + 企业通讯录拉取。

保护初始超级管理员 FELY/YHAD（任何人不可降级）。
至少保留1个超级管理员。
"""
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_admin, get_current_super_admin
from app.models.user import User
from app.schemas.user import UserRoleUpdate
from app.services.wecom import get_all_wecom_members
from app.utils import gen_uuid

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get('/api/admin/users')
def admin_users_list(
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """管理员获取已注册用户列表（标记 is_self 供前端识别当前用户）。"""
    users = db.query(User).filter(User.wecom_user_id.isnot(None)).all()
    result = []
    for u in users:
        d = u.to_dict(include_wecom_id=True)
        d['is_self'] = (u.id == admin.id)
        result.append(d)
    return {'users': result}


@router.get('/api/admin/wecom-members')
def wecom_members_list(
    admin: User = Depends(get_current_super_admin),
    db: Session = Depends(get_db),
):
    """超级管理员获取企业微信通讯录全部成员（含未登录论坛的用户）。

    合并企微通讯录与本地数据库：
    - 已注册用户：显示数据库中的角色
    - 未注册用户：标记 registered=False，角色显示为 'user'

    registered 匹配采用忽略大小写的 userid 归一化：
    企业微信 simplelist 返回的 userid 与 OAuth 登录时存入的 wecom_user_id
    可能存在大小写差异，统一按大写比较，避免已注册用户被误判为未注册。
    """
    members, error = get_all_wecom_members()
    if error:
        # 透传企微具体错误码/描述，便于前端展示真实原因
        return {'members': [], 'error': error}

    # 查询所有已注册用户，建立 userid（忽略大小写）-> user 映射
    db_users = db.query(User).filter(User.wecom_user_id.isnot(None)).all()
    user_map = {}
    for u in db_users:
        if u.wecom_user_id:
            user_map[u.wecom_user_id.upper()] = u

    result = []
    for m in members:
        wid = m['userid']
        if not wid:
            continue
        u = user_map.get(wid.upper())
        if u:
            result.append({
                'userid': wid,
                'name': m['name'] or u.nickname,
                'department': m['department'] or u.department or '',
                'avatar': m.get('avatar') or u.avatar or '',
                'registered': True,
                'id': u.id,
                'role': u.role,
                'is_admin': u.is_admin,
                'is_self': (u.id == admin.id),
            })
        else:
            result.append({
                'userid': wid,
                'name': m['name'] or wid,
                'department': m['department'] or '',
                'avatar': m.get('avatar', ''),
                'registered': False,
                'id': None,
                'role': 'user',
                'is_admin': False,
                'is_self': False,
            })
    return {'members': result}


@router.put('/api/admin/users/{uid}/role')
def update_user_role(
    uid: str,
    body: UserRoleUpdate,
    admin: User = Depends(get_current_super_admin),
    db: Session = Depends(get_db),
):
    """超级管理员修改用户角色。

    支持：
    - 修改已注册用户的角色
    - 为未注册用户预设角色（通过 wecom_user_id 查找，不存在则创建）

    保护规则：
    1. 不能降级自己
    2. 保护初始超级管理员 FELY/YHAD（任何人不可降级）
    3. 至少保留1个超级管理员
    """
    new_role = body.role
    if new_role not in ('user', 'admin', 'super_admin'):
        raise HTTPException(status_code=400, detail='无效角色')

    # 先按数据库 ID 查找，找不到再按 wecom_user_id 查找（支持预设角色）
    target = db.get(User, uid)
    if not target:
        target = db.query(User).filter_by(wecom_user_id=uid).first()

    if not target:
        # 未注册用户：创建一条记录，预设角色
        # 此时只有 wecom_user_id 和 nickname，等用户登录时会自动匹配
        target = User(
            id=gen_uuid(),
            wecom_user_id=uid,
            nickname=body.nickname if hasattr(body, 'nickname') and body.nickname else uid,
            avatar='',
            department='',
            is_admin=new_role in ('super_admin', 'admin'),
            role=new_role,
        )
        db.add(target)
        db.commit()
        db.refresh(target)
        return {'ok': True, 'user': target.to_dict(), 'created': True}

    # 不能降级自己
    if target.id == admin.id and new_role != 'super_admin':
        raise HTTPException(status_code=400, detail='不能降级自己的超级管理员权限')

    # 保护初始超级管理员 FELY/YHAD（任何人不可降级）
    if target.wecom_user_id in ('FELY', 'YHAD') and new_role != 'super_admin':
        raise HTTPException(status_code=403, detail='初始超级管理员不可被降级')

    # 至少保留1个超级管理员
    if target.role == 'super_admin' and new_role != 'super_admin':
        super_count = db.query(User).filter_by(role='super_admin').count()
        if super_count <= 1:
            raise HTTPException(status_code=400, detail='至少需要保留1名超级管理员')

    target.role = new_role
    target.is_admin = new_role in ('super_admin', 'admin')
    db.commit()
    return {'ok': True, 'user': target.to_dict()}
