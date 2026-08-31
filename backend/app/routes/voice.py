"""心声路由：CRUD + 点赞 + 审核。

包含并发审核保护（status != 'pending' 返回 409）。
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.deps import get_current_admin, get_current_user_required, get_user_with_context_required
from app.models.user import User
from app.models.voice import Voice, VoiceLike, VoiceTag
from app.models.notification import Notification
from app.serialization import voice_to_dict, notification_to_dict
from app.schemas.voice import VoiceCreate, StatusUpdate
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


@router.post('/api/voices')
def create_voice(
    body: VoiceCreate,
    user: User = Depends(get_user_with_context_required),
    db: Session = Depends(get_db),
):
    """创建心声（管理员发布直接 approved，普通用户 pending）。"""
    content = (body.content or '').strip()
    if not content or len(content) > 500:
        raise HTTPException(status_code=400, detail='内容长度应在1-500字之间')

    # 内容安全检测（在登录校验之后，避免未认证用户消耗企微 API 配额）
    is_safe, msg = check_content_safe(content)
    if not is_safe:
        raise HTTPException(status_code=400, detail=msg or '内容不合规')

    # 限流
    allowed, count = rate_limit_check(rate_limit_key('voice', user.id), settings.RATE_LIMIT_VOICE, settings.RATE_LIMIT_WINDOW)
    if not allowed:
        raise HTTPException(status_code=429, detail='发布过于频繁，请稍后再试')

    is_admin = user.is_admin or user.role in ('super_admin', 'admin')
    v = Voice(
        id=gen_uuid(),
        user_id=user.id,
        content=content,
        anon_name=body.anonName or ANON_NAME,
        is_anonymous=bool(body.isAnonymous),
        like_count=0,
        status='approved' if is_admin else 'pending',
    )
    db.add(v)
    db.flush()
    # 持久化标签
    for tag in (body.tags or []):
        db.add(VoiceTag(id=gen_uuid(), voice_id=v.id, tag=tag))
    db.commit()
    db.refresh(v)
    return {'ok': True, 'voice': voice_to_dict(db, v)}


@router.put('/api/voices/{vid}/like')
def toggle_like(
    vid: str,
    user: User = Depends(get_current_user_required),
    db: Session = Depends(get_db),
):
    """切换心声点赞（已赞取消，未赞点赞）。

    使用行锁（SELECT ... FOR UPDATE）串行化同一心声的点赞/取消，
    避免并发读写导致计数漂移；唯一约束兜底防止重复点赞。
    """
    from sqlalchemy.exc import IntegrityError
    # 行锁：串行化同一心声的点赞/取消，避免并发下计数重复递减/递增
    v = db.query(Voice).filter(Voice.id == vid).with_for_update().first()
    if not v:
        raise HTTPException(status_code=404, detail='留言不存在')
    # 权限：pending/rejected 状态的心声不允许点赞
    if v.status in ('pending', 'rejected'):
        raise HTTPException(status_code=403, detail='该留言暂不可点赞')

    existing = db.query(VoiceLike).filter_by(voice_id=vid, user_id=user.id).first()
    if existing:
        # 取消点赞：删除记录并在行锁保护下原子减值
        db.delete(existing)
        db.query(Voice).filter(Voice.id == vid).update(
            {Voice.like_count: func.greatest(0, Voice.like_count - 1)}
        )
        db.commit()
        cache_delete('cache:admin_stats')
        db.refresh(v)
        return {'ok': True, 'isLiked': False, 'likeCount': v.like_count}
    try:
        db.add(VoiceLike(id=gen_uuid(), voice_id=vid, user_id=user.id))
        db.query(Voice).filter(Voice.id == vid).update(
            {Voice.like_count: Voice.like_count + 1}
        )
        db.commit()
        cache_delete('cache:admin_stats')
    except IntegrityError:
        # 唯一约束冲突：确认该用户确实已点赞后才返回已赞，否则回滚并报错
        db.rollback()
        v = db.get(Voice, vid)
        still_liked = (
            db.query(VoiceLike)
            .filter_by(voice_id=vid, user_id=user.id)
            .first()
        )
        if not still_liked:
            raise HTTPException(status_code=409, detail='点赞失败，请重试')
        return {'ok': True, 'isLiked': True, 'likeCount': v.like_count}
    db.refresh(v)
    return {'ok': True, 'isLiked': True, 'likeCount': v.like_count}


@router.put('/api/voices/{vid}/status')
def set_voice_status(
    vid: str,
    body: StatusUpdate,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """管理员审核心声（并发审核保护：行锁 + 409）。"""
    # 使用 SELECT ... FOR UPDATE 行锁，防止两个管理员同时审核通过
    v = db.query(Voice).filter(Voice.id == vid).with_for_update().first()
    if not v:
        raise HTTPException(status_code=404, detail='留言不存在')
    # 并发审核保护：已被其他管理员审核的不再重复处理
    if v.status != 'pending':
        raise HTTPException(
            status_code=409,
            detail='已被其他管理员审核',
        )
    new_status = body.status or v.status
    if new_status not in ('pending', 'approved', 'rejected'):
        raise HTTPException(status_code=400, detail='无效状态')
    v.status = new_status
    v.reject_reason = body.rejectReason or ''
    # 审核结果通知提交者（与状态更新合并到同一事务，只做一次 commit）
    author_notif = None
    if v.user_id:
        preview = _content_preview(v.content)
        if new_status == 'approved':
            author_notif = Notification(
                id=gen_uuid(), user_id=v.user_id, type='voice_approved',
                text='您的留言"%s"已通过审核' % preview, is_read=False, related_id=v.id,
            )
            db.add(author_notif)
        elif new_status == 'rejected':
            reason = body.rejectReason or ''
            notif_text = '您的留言"%s"未通过审核' % preview
            if reason:
                notif_text = notif_text + '，原因：' + reason
            author_notif = Notification(
                id=gen_uuid(), user_id=v.user_id, type='voice_rejected',
                text=notif_text, is_read=False, related_id=v.id,
            )
            db.add(author_notif)
    db.commit()
    if author_notif:
        db.refresh(author_notif)
    # 失效统计缓存 + 推送 SSE review_update 事件（管理员 + 作者）
    cache_delete('cache:admin_stats')
    _push_review_update(admin.id, 'voice', v.id, new_status, v.user_id)
    # 推送通知和未读数给内容作者
    if author_notif and v.user_id:
        try:
            from app.routes.sse import push_sse_sync
            push_sse_sync(v.user_id, 'notification', notification_to_dict(author_notif))
            author_count = db.query(Notification).filter_by(
                user_id=v.user_id, is_read=False
            ).count()
            push_sse_sync(v.user_id, 'unread_count', {'count': author_count})
        except Exception:
            pass
        # 企微应用消息推送（手机端通知，不阻塞响应）
        try:
            from app.services.notify import push_wecom_to_user
            notif_type = 'voice_approved' if new_status == 'approved' else 'voice_rejected'
            push_wecom_to_user(db, v.user_id, notif_type, author_notif.text, v.id)
        except Exception:
            pass
    return {'ok': True}


@router.delete('/api/voices/{vid}')
def delete_voice(
    vid: str,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """管理员删除心声（同时清理关联通知）。"""
    v = db.get(Voice, vid)
    if not v:
        raise HTTPException(status_code=404, detail='留言不存在')
    # 清理关联通知（related_id 指向被删内容）
    db.query(Notification).filter_by(related_id=vid).delete()
    db.delete(v)
    db.commit()
    cache_delete('cache:admin_stats')
    return {'ok': True}


@router.put('/api/voices/{vid}/clear-review')
def clear_voice_review(
    vid: str,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """管理员清除单条留言审核记录（设置 review_cleared=True）。"""
    v = db.get(Voice, vid)
    if not v:
        raise HTTPException(status_code=404, detail='留言不存在')
    v.review_cleared = True
    db.commit()
    return {'code': 200, 'message': 'ok'}


@router.post('/api/voices/clear-rejected')
def clear_all_rejected_voices(
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """管理员批量清除所有已驳回留言的审核记录（review_cleared=False 且 status='rejected'）。"""
    count = (
        db.query(Voice)
        .filter(Voice.review_cleared == False, Voice.status == 'rejected')  # noqa: E712
        .update({Voice.review_cleared: True}, synchronize_session='fetch')
    )
    db.commit()
    return {'code': 200, 'message': 'ok', 'count': count}
