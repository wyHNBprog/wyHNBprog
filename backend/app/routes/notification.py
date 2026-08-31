"""通知路由：创建 / 列表 / 已读 / 删除 / 分类统计。"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user_required, get_user_with_context_required
from app.models.user import User
from app.models.notification import Notification
from app.serialization import notification_to_dict
from app.schemas.notification import NotificationCreate
from app.schemas.voice import NotificationReadByType
from app.utils import gen_uuid

router = APIRouter()

# 允许的通知类型枚举
VALID_NOTIFICATION_TYPES = {
    'system', 'voice_approved', 'voice_rejected',
    'idea_approved', 'idea_rejected', 'feedback_replied',
    'message_replied', 'message_received',
    'comment_approved', 'comment_rejected',
}

# 通知类型 -> 分类映射（用于分类统计/按类型标记已读）
NOTIFICATION_TYPE_CATEGORY = {
    'voice_approved': 'voice',
    'voice_rejected': 'voice',
    'idea_approved': 'idea',
    'idea_rejected': 'idea',
    'message_replied': 'message',
    'message_received': 'message',
    'feedback_replied': 'feedback',
    'comment_approved': 'comment',
    'comment_rejected': 'comment',
    'system': 'system',
}

# 分类 -> 通知类型集合（反向映射，用于按类型标记已读）
CATEGORY_TYPES = {}
for _ntype, _cat in NOTIFICATION_TYPE_CATEGORY.items():
    CATEGORY_TYPES.setdefault(_cat, []).append(_ntype)

VALID_CATEGORIES = {'voice', 'idea', 'comment', 'message', 'feedback', 'system'}


def _is_admin(user: User) -> bool:
    return bool(user and (user.is_admin or user.role in ('super_admin', 'admin')))


@router.get('/api/notifications')
@router.get('/api/notifications/list')
def list_notifications(
    user: User = Depends(get_user_with_context_required),
    db: Session = Depends(get_db),
):
    """获取通知列表（所有用户包括管理员都只看自己的通知）。"""
    notifs = (
        db.query(Notification)
        .filter_by(user_id=user.id)
        .order_by(Notification.created_at.desc())
        .all()
    )
    return {'notifications': [notification_to_dict(n) for n in notifs]}


@router.post('/api/notifications')
def create_notification(
    body: NotificationCreate,
    user: User = Depends(get_current_user_required),
    db: Session = Depends(get_db),
):
    """创建通知。"""
    if body.type and body.type not in VALID_NOTIFICATION_TYPES:
        raise HTTPException(status_code=400, detail='无效的通知类型')
    n = Notification(
        id=gen_uuid(),
        user_id=user.id,
        type=body.type or 'system',
        text=body.text or '',
        is_read=False,
    )
    db.add(n)
    db.commit()
    return {'ok': True, 'notification': notification_to_dict(n)}


@router.put('/api/notifications/read-all')
def read_all_notifications(
    user: User = Depends(get_current_user_required),
    db: Session = Depends(get_db),
):
    """标记所有通知为已读。

    admin 在列表中可查看全局通知，但只能标记自己的通知为已读，
    不会修改其他用户的通知状态。
    """
    db.query(Notification).filter_by(user_id=user.id).update({Notification.is_read: True})
    db.commit()
    return {'ok': True}


@router.get('/api/notifications/unread-count')
def notifications_unread_count(
    user: User = Depends(get_current_user_required),
    db: Session = Depends(get_db),
):
    """获取未读通知数（admin 也只统计自己的通知）。"""
    count = db.query(Notification).filter_by(user_id=user.id, is_read=False).count()
    return {'count': count}


@router.get('/api/notifications/unread-by-type')
def notifications_unread_by_type(
    user: User = Depends(get_current_user_required),
    db: Session = Depends(get_db),
):
    """获取各分类未读通知数。

    返回 {voice: N, idea: N, message: N, feedback: N, system: N}
    admin 也只统计自己的通知。
    """
    rows = (
        db.query(Notification.type)
        .filter_by(user_id=user.id, is_read=False)
        .all()
    )
    result = {cat: 0 for cat in VALID_CATEGORIES}
    for (ntype,) in rows:
        cat = NOTIFICATION_TYPE_CATEGORY.get(ntype, 'system')
        result[cat] = result.get(cat, 0) + 1
    return result


@router.put('/api/notifications/read-by-type')
def read_notifications_by_type(
    body: NotificationReadByType,
    user: User = Depends(get_current_user_required),
    db: Session = Depends(get_db),
):
    """按分类标记通知为已读。

    body: {type: 'voice'|'idea'|'message'|'feedback'|'system'}
    admin 也只能标记自己的通知为已读。
    """
    category = body.type
    if category not in VALID_CATEGORIES:
        raise HTTPException(status_code=400, detail='无效的通知分类')
    types = CATEGORY_TYPES.get(category, [])
    if types:
        db.query(Notification).filter(
            Notification.user_id == user.id,
            Notification.is_read == False,  # noqa: E712
            Notification.type.in_(types),
        ).update({Notification.is_read: True}, synchronize_session='fetch')
    db.commit()
    return {'ok': True}


@router.put('/api/notifications/{nid}/read')
def mark_notification_read(
    nid: str,
    user: User = Depends(get_current_user_required),
    db: Session = Depends(get_db),
):
    """标记单条通知为已读（不删除，仅更新 is_read 字段）。

    admin 可标记任何用户的通知为已读（用于管理后台操作）。
    """
    n = db.get(Notification, nid)
    if not n:
        raise HTTPException(status_code=404, detail='通知不存在')
    is_admin_user = _is_admin(user)
    if n.user_id != user.id and not is_admin_user:
        raise HTTPException(status_code=403, detail='无权操作')
    if not n.is_read:
        n.is_read = True
        db.commit()
    return {'ok': True, 'notification': notification_to_dict(n)}


@router.delete('/api/notifications/{nid}')
def delete_notification(
    nid: str,
    user: User = Depends(get_current_user_required),
    db: Session = Depends(get_db),
):
    """删除通知（真正的删除，与标记已读区分）。

    admin 可删除任何用户的通知（与标记已读权限一致）。
    """
    n = db.get(Notification, nid)
    if not n:
        raise HTTPException(status_code=404, detail='通知不存在')
    is_admin_user = _is_admin(user)
    if n.user_id != user.id and not is_admin_user:
        raise HTTPException(status_code=403, detail='无权操作')
    db.delete(n)
    db.commit()
    return {'ok': True}
