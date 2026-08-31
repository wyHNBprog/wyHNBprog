"""公告路由：CRUD。"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_admin, get_user_with_context_required
from app.models.user import User
from app.models.announce import Announce
from app.serialization import announce_to_dict
from app.schemas.voice import AnnouncementCreate, AnnouncementUpdate
from app.utils import gen_uuid

router = APIRouter()


@router.get('/api/announcements')
def list_announcements(
    user: User = Depends(get_user_with_context_required),
    db: Session = Depends(get_db),
):
    """获取公告列表（置顶优先，再按时间倒序）。"""
    return [
        announce_to_dict(a)
        for a in db.query(Announce)
        .order_by(Announce.is_pinned.desc(), Announce.created_at.desc())
        .all()
    ]


@router.post('/api/announcements')
def create_announcement(
    body: AnnouncementCreate,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """创建公告（管理员）。"""
    a = Announce(
        id=gen_uuid(),
        title=body.title or '',
        content=body.content or '',
        is_pinned=bool(body.pinned),
    )
    db.add(a)
    db.commit()
    return {'ok': True, 'announcement': announce_to_dict(a)}


@router.put('/api/announcements/{aid}')
def update_announcement(
    aid: str,
    body: AnnouncementUpdate,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """更新公告（管理员）。"""
    a = db.get(Announce, aid)
    if not a:
        raise HTTPException(status_code=404, detail='公告不存在')
    if body.title is not None:
        a.title = body.title
    if body.content is not None:
        a.content = body.content
    if body.pinned is not None:
        a.is_pinned = bool(body.pinned)
    db.commit()
    return {'ok': True, 'announcement': announce_to_dict(a)}


@router.delete('/api/announcements/{aid}')
def delete_announcement(
    aid: str,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """删除公告（管理员）。"""
    a = db.get(Announce, aid)
    if not a:
        raise HTTPException(status_code=404, detail='公告不存在')
    db.delete(a)
    db.commit()
    return {'ok': True}
