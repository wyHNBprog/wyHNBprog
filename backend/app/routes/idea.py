"""金点子路由：CRUD + 投票 + 献花 + 审核。

包含并发审核保护（status != 'pending' 返回 409）。
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.deps import get_current_admin, get_current_user_required, get_user_with_context_required
from app.models.user import User
from app.models.idea import Idea, IdeaVote
from app.models.notification import Notification
from app.serialization import idea_to_dict, notification_to_dict
from app.schemas.idea import IdeaCreate
from app.schemas.voice import StatusUpdate
from app.services.redis_client import rate_limit_check, rate_limit_key, cache_delete
from app.utils import gen_uuid, ANON_NAME, check_content_safe

router = APIRouter()


def _content_preview(content: str, max_len: int = 20) -> str:
    """取内容前 N 个字符作为预览。"""
    if not content:
        return ''
    content = content.strip()
    if len(content) <= max_len:
        return content
    return content[:max_len] + '...'


def _push_review_update(admin_id: str, item_type: str, item_id: str, status: str, author_id: str = None) -> None:
    """推送 review_update SSE 事件给管理员和内容作者（异步，不阻塞响应）。"""
    try:
        from app.routes.sse import push_sse_sync
        payload = {
            'type': item_type, 'id': item_id, 'status': status,
            'action': status,
        }
        push_sse_sync(admin_id, 'review_update', payload)
        if author_id and author_id != admin_id:
            push_sse_sync(author_id, 'review_update', payload)
    except Exception:
        pass


@router.post('/api/ideas')
def create_idea(
    body: IdeaCreate,
    user: User = Depends(get_user_with_context_required),
    db: Session = Depends(get_db),
):
    """创建金点子（管理员发布直接 approved/voting，普通用户 pending）。"""
    title = (body.title or '').strip()
    desc = (body.desc or '').strip()
    if not title or len(title) > 100:
        raise HTTPException(status_code=400, detail='标题长度应在1-100字之间')
    if len(desc) > 1000:
        raise HTTPException(status_code=400, detail='描述长度不能超过1000字')

    # 内容安全检测（在登录校验之后，避免未认证用户消耗企微 API 配额）
    is_safe, msg = check_content_safe(title + ' ' + desc)
    if not is_safe:
        raise HTTPException(status_code=400, detail=msg or '内容不合规')

    # 限流
    allowed, count = rate_limit_check(rate_limit_key('idea', user.id), settings.RATE_LIMIT_IDEA, settings.RATE_LIMIT_WINDOW)
    if not allowed:
        raise HTTPException(status_code=429, detail='发布过于频繁，请稍后再试')

    is_admin = user.is_admin or user.role in ('super_admin', 'admin')
    i = Idea(
        id=gen_uuid(),
        user_id=user.id,
        title=title,
        description=desc,
        category=body.category or '其他',
        vote_count=0,
        has_flower=False,
        flower_count=0,
        anon_name=body.anonName or ANON_NAME,
        is_anonymous=bool(body.isAnonymous),
        status='approved' if is_admin else 'pending',
    )
    db.add(i)
    db.commit()
    return {'ok': True, 'idea': idea_to_dict(db, i)}


@router.put('/api/ideas/{iid}/vote')
def vote_idea(
    iid: str,
    user: User = Depends(get_current_user_required),
    db: Session = Depends(get_db),
):
    """点赞金点子（已赞取消，未赞点赞）。

    使用行锁 + 唯一约束保证并发下计数不漂移、不重复。
    """
    # 行锁：串行化同一金点子的点赞/取消，避免并发读写导致计数漂移
    i = db.query(Idea).filter(Idea.id == iid).with_for_update().first()
    if not i:
        raise HTTPException(status_code=404, detail='创意不存在')
    # 权限：pending/rejected 状态不允许点赞
    if i.status in ('pending', 'rejected'):
        raise HTTPException(status_code=403, detail='该创意暂不可点赞')

    existing = db.query(IdeaVote).filter_by(idea_id=iid, user_id=user.id).first()
    if existing:
        # 取消点赞：删除记录并原子减值（行锁下计数一致）
        db.delete(existing)
        db.query(Idea).filter(Idea.id == iid).update(
            {Idea.vote_count: func.greatest(0, Idea.vote_count - 1)}
        )
        db.commit()
        cache_delete('cache:admin_stats')
        db.refresh(i)
        return {'ok': True, 'hasVoted': False, 'voteCount': i.vote_count}

    try:
        db.add(IdeaVote(id=gen_uuid(), idea_id=iid, user_id=user.id))
        db.query(Idea).filter(Idea.id == iid).update(
            {Idea.vote_count: Idea.vote_count + 1}
        )
        db.commit()
        cache_delete('cache:admin_stats')
    except IntegrityError:
        # 唯一约束冲突：确认该用户确实已点赞后才返回已赞，否则回滚并报错
        db.rollback()
        i = db.get(Idea, iid)
        still_voted = (
            db.query(IdeaVote)
            .filter_by(idea_id=iid, user_id=user.id)
            .first()
        )
        if not still_voted:
            raise HTTPException(status_code=409, detail='点赞失败，请重试')
        return {'ok': True, 'hasVoted': True, 'voteCount': i.vote_count}
    db.refresh(i)
    return {'ok': True, 'hasVoted': True, 'voteCount': i.vote_count}


@router.put('/api/ideas/{iid}/flower')
def flower_idea(
    iid: str,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """管理员切换献花（行锁 + flower_count 自愈）。"""
    # 使用 SELECT ... FOR UPDATE 行锁，防止并发翻转
    i = db.query(Idea).filter(Idea.id == iid).with_for_update().first()
    if not i:
        raise HTTPException(status_code=404, detail='创意不存在')
    i.has_flower = not i.has_flower
    # 自愈式：直接根据 has_flower 设置，避免增量式计数漂移
    i.flower_count = 1 if i.has_flower else 0
    db.commit()
    cache_delete('cache:admin_stats')
    return {'ok': True, 'hasFlower': i.has_flower, 'flowerCount': i.flower_count}


@router.put('/api/ideas/{iid}/status')
def set_idea_status(
    iid: str,
    body: StatusUpdate,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """管理员审核金点子（并发审核保护：行锁 + 409）。"""
    # 使用 SELECT ... FOR UPDATE 行锁，防止两个管理员同时审核通过
    i = db.query(Idea).filter(Idea.id == iid).with_for_update().first()
    if not i:
        raise HTTPException(status_code=404, detail='创意不存在')
    # 并发审核保护：已被其他管理员审核的不再重复处理
    if i.status != 'pending':
        raise HTTPException(
            status_code=409,
            detail='已被其他管理员审核',
        )
    new_status = body.status or i.status
    if new_status not in ('pending', 'approved', 'rejected', 'voting'):
        raise HTTPException(status_code=400, detail='无效状态')
    i.status = new_status
    reject_reason = body.rejectReason or ''
    i.reject_reason = reject_reason
    # 审核结果通知提交者（与状态更新合并到同一事务，只做一次 commit）
    author_notif = None
    if i.user_id:
        preview = _content_preview(i.title)
        if new_status in ('approved', 'voting'):
            author_notif = Notification(
                id=gen_uuid(), user_id=i.user_id, type='idea_approved',
                text='您的金点子"%s"已通过审核' % preview, is_read=False, related_id=i.id,
            )
            db.add(author_notif)
        elif new_status == 'rejected':
            reason = body.rejectReason or ''
            notif_text = '您的金点子"%s"未通过审核' % preview
            if reason:
                notif_text = notif_text + '，原因：' + reason
            author_notif = Notification(
                id=gen_uuid(), user_id=i.user_id, type='idea_rejected',
                text=notif_text, is_read=False, related_id=i.id,
            )
            db.add(author_notif)
    db.commit()
    if author_notif:
        db.refresh(author_notif)
    # 失效统计缓存 + 推送 SSE review_update 事件（管理员 + 作者）
    cache_delete('cache:admin_stats')
    _push_review_update(admin.id, 'idea', i.id, new_status, i.user_id)
    # 推送通知和未读数给内容作者
    if author_notif and i.user_id:
        try:
            from app.routes.sse import push_sse_sync
            push_sse_sync(i.user_id, 'notification', notification_to_dict(author_notif))
            author_count = db.query(Notification).filter_by(
                user_id=i.user_id, is_read=False
            ).count()
            push_sse_sync(i.user_id, 'unread_count', {'count': author_count})
        except Exception:
            pass
        # 企微应用消息推送（手机端通知，不阻塞响应）
        try:
            from app.services.notify import push_wecom_to_user
            notif_type = 'idea_approved' if new_status in ('approved', 'voting') else 'idea_rejected'
            push_wecom_to_user(db, i.user_id, notif_type, author_notif.text, i.id)
        except Exception:
            pass
    return {'ok': True}


@router.delete('/api/ideas/{iid}')
def delete_idea(
    iid: str,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """管理员删除金点子（同时清理关联通知）。"""
    i = db.get(Idea, iid)
    if not i:
        raise HTTPException(status_code=404, detail='创意不存在')
    # 清理关联通知（related_id 指向被删内容）
    db.query(Notification).filter_by(related_id=iid).delete()
    db.delete(i)
    db.commit()
    cache_delete('cache:admin_stats')
    return {'ok': True}


@router.put('/api/ideas/{iid}/firework')
def firework_idea(
    iid: str,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """管理员切换献星星（toggle has_firework，自愈式设置 firework_count）。

    - 仅管理员可操作
    - toggle 逻辑：翻转 has_firework 布尔值
    - 自愈式：firework_count 直接根据 has_firework 设置为 1 或 0，避免增量计数漂移
    - 返回更新后的 idea dict
    """
    # 使用 SELECT ... FOR UPDATE 行锁，防止并发翻转
    i = db.query(Idea).filter(Idea.id == iid).with_for_update().first()
    if not i:
        raise HTTPException(status_code=404, detail='创意不存在')
    i.has_firework = not i.has_firework
    # 自愈式：直接根据 has_firework 设置，避免增量式计数漂移
    i.firework_count = 1 if i.has_firework else 0
    db.commit()
    db.refresh(i)
    cache_delete('cache:admin_stats')
    return {'ok': True, 'idea': idea_to_dict(db, i)}


@router.put('/api/ideas/{iid}/clear-review')
def clear_idea_review(
    iid: str,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """管理员清除单条金点子审核记录（设置 review_cleared=True）。"""
    i = db.get(Idea, iid)
    if not i:
        raise HTTPException(status_code=404, detail='创意不存在')
    i.review_cleared = True
    db.commit()
    return {'code': 200, 'message': 'ok'}


@router.post('/api/ideas/clear-rejected')
def clear_all_rejected_ideas(
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """管理员批量清除所有已驳回金点子的审核记录（review_cleared=False 且 status='rejected'）。"""
    count = (
        db.query(Idea)
        .filter(Idea.review_cleared == False, Idea.status == 'rejected')  # noqa: E712
        .update({Idea.review_cleared: True}, synchronize_session='fetch')
    )
    db.commit()
    return {'code': 200, 'message': 'ok', 'count': count}
