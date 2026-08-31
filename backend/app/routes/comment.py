"""评论路由：发表评论 + 点赞 + 审核 + 删除。

评论路径嵌套在 /api/voices/{vid}/comments 下，与 Flask 版本保持一致。
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.deps import get_current_admin, get_current_user_required, get_user_with_context_required
from app.models.user import User
from app.models.voice import Voice
from app.models.comment import Comment, CommentLike
from app.models.notification import Notification
from app.schemas.voice import CommentCreate, StatusUpdate
from app.serialization import notification_to_dict
from app.services.redis_client import rate_limit_check, rate_limit_key, cache_delete
from app.utils import gen_uuid, ANON_NAME, check_content_safe, _local_str

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


@router.post('/api/voices/{vid}/comments')
def add_comment(
    vid: str,
    body: CommentCreate,
    user: User = Depends(get_user_with_context_required),
    db: Session = Depends(get_db),
):
    """发表评论（仅已审核通过的留言可评论）。"""
    v = db.get(Voice, vid)
    if not v:
        raise HTTPException(status_code=404, detail='留言不存在')
    # 仅已审核通过的留言可评论
    if v.status != 'approved':
        raise HTTPException(status_code=403, detail='该留言暂不可评论')

    content = (body.content or '').strip()
    if not content or len(content) > 500:
        raise HTTPException(status_code=400, detail='评论内容长度应在1-500字之间')

    # 内容安全检测（在登录校验之后，避免未认证用户消耗企微 API 配额）
    is_safe, msg = check_content_safe(content)
    if not is_safe:
        raise HTTPException(status_code=400, detail=msg or '内容不合规')

    # 限流
    allowed, count = rate_limit_check(rate_limit_key('comment', user.id), settings.RATE_LIMIT_COMMENT, settings.RATE_LIMIT_WINDOW)
    if not allowed:
        raise HTTPException(status_code=429, detail='评论过于频繁，请稍后再试')

    is_admin = user.is_admin or user.role in ('super_admin', 'admin')
    c = Comment(
        id=gen_uuid(),
        voice_id=vid,
        user_id=user.id,
        content=content,
        anon_name=body.anonName or ANON_NAME,
        status='approved' if is_admin else 'pending',
    )
    db.add(c)
    db.commit()
    return {
        'ok': True,
        'comment': {
            'id': c.id,
            'content': c.content,
            'anonName': c.anon_name,
            'timeText': '刚刚',
            'status': c.status,
        },
    }


@router.put('/api/voices/{vid}/comments/{cid}/status')
def set_comment_status(
    vid: str,
    cid: str,
    body: StatusUpdate,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """管理员审核评论（并发审核保护：行锁 + 409）。"""
    # 使用 SELECT ... FOR UPDATE 行锁，防止两个管理员同时审核通过
    c = db.query(Comment).filter(Comment.id == cid).with_for_update().first()
    if not c:
        raise HTTPException(status_code=404, detail='评论不存在')
    if c.voice_id != vid:
        raise HTTPException(status_code=404, detail='评论不存在')
    new_status = body.status or c.status
    if new_status not in ('pending', 'approved', 'rejected'):
        raise HTTPException(status_code=400, detail='无效状态')
    # 并发保护：已被其他管理员审核则返回 409（与留言/金点子审核逻辑一致）
    if c.status != 'pending':
        raise HTTPException(status_code=409, detail='已被其他管理员审核')
    c.status = new_status
    c.reject_reason = body.rejectReason or ''
    # 审核通过/驳回时创建通知给评论作者（含内容预览）
    author_notif = None
    if c.user_id:
        preview = _content_preview(c.content)
        if new_status == 'approved':
            author_notif = Notification(
                id=gen_uuid(), user_id=c.user_id, type='comment_approved',
                text='你的评论"%s"已通过审核' % preview, is_read=False, related_id=c.id,
            )
            db.add(author_notif)
        elif new_status == 'rejected':
            reason = body.rejectReason or ''
            notif_text = '你的评论"%s"未通过审核' % preview
            if reason:
                notif_text = notif_text + '，原因：' + reason
            author_notif = Notification(
                id=gen_uuid(), user_id=c.user_id, type='comment_rejected',
                text=notif_text, is_read=False, related_id=c.id,
            )
            db.add(author_notif)
    db.commit()
    if author_notif:
        db.refresh(author_notif)
    # 失效统计缓存 + 推送 SSE review_update 事件（管理员 + 作者）
    cache_delete('cache:admin_stats')
    _push_review_update(admin.id, 'comment', c.id, new_status, c.user_id)
    # 推送通知和未读数给内容作者
    if author_notif and c.user_id:
        try:
            from app.routes.sse import push_sse_sync
            push_sse_sync(c.user_id, 'notification', notification_to_dict(author_notif))
            author_count = db.query(Notification).filter_by(
                user_id=c.user_id, is_read=False
            ).count()
            push_sse_sync(c.user_id, 'unread_count', {'count': author_count})
        except Exception:
            pass
        # 企微应用消息推送（手机端通知，不阻塞响应）
        try:
            from app.services.notify import push_wecom_to_user
            notif_type = 'comment_approved' if new_status == 'approved' else 'comment_rejected'
            push_wecom_to_user(db, c.user_id, notif_type, author_notif.text, c.id)
        except Exception:
            pass
    return {'ok': True}


@router.delete('/api/voices/{vid}/comments/{cid}')
def delete_comment(
    vid: str,
    cid: str,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """管理员删除评论（同时清理关联通知）。"""
    c = db.get(Comment, cid)
    if not c:
        raise HTTPException(status_code=404, detail='评论不存在')
    if c.voice_id != vid:
        raise HTTPException(status_code=404, detail='评论不存在')
    # 清理关联通知（related_id 指向被删内容）
    db.query(Notification).filter_by(related_id=cid).delete()
    db.delete(c)
    db.commit()
    cache_delete('cache:admin_stats')
    return {'ok': True}


@router.put('/api/voices/{vid}/comments/{cid}/like')
def toggle_comment_like(
    vid: str,
    cid: str,
    user: User = Depends(get_current_user_required),
    db: Session = Depends(get_db),
):
    """切换评论点赞。"""
    # 行锁：串行化同一评论的点赞/取消，避免并发下计数重复递减/递增
    c = db.query(Comment).filter(Comment.id == cid).with_for_update().first()
    if not c:
        raise HTTPException(status_code=404, detail='评论不存在')
    if c.voice_id != vid:
        raise HTTPException(status_code=404, detail='评论不存在')
    if c.status != 'approved':
        raise HTTPException(status_code=403, detail='该评论暂不可点赞')

    existing = db.query(CommentLike).filter_by(comment_id=cid, user_id=user.id).first()
    if existing:
        # 取消点赞：删除记录并在行锁保护下原子减值
        db.delete(existing)
        db.query(Comment).filter(Comment.id == cid).update(
            {Comment.like_count: func.greatest(0, Comment.like_count - 1)}
        )
        db.commit()
        cache_delete('cache:admin_stats')
        db.refresh(c)
        return {'ok': True, 'isLiked': False, 'likeCount': c.like_count}
    try:
        db.add(CommentLike(id=gen_uuid(), comment_id=cid, user_id=user.id))
        db.query(Comment).filter(Comment.id == cid).update(
            {Comment.like_count: Comment.like_count + 1}
        )
        db.commit()
        cache_delete('cache:admin_stats')
    except IntegrityError:
        # 唯一约束冲突：确认该用户确实已点赞后才返回已赞，否则回滚并报错
        db.rollback()
        c = db.get(Comment, cid)
        still_liked = (
            db.query(CommentLike)
            .filter_by(comment_id=cid, user_id=user.id)
            .first()
        )
        if not still_liked:
            raise HTTPException(status_code=409, detail='点赞失败，请重试')
        return {'ok': True, 'isLiked': True, 'likeCount': c.like_count}
    db.refresh(c)
    return {'ok': True, 'isLiked': True, 'likeCount': c.like_count}


@router.put('/api/voices/{vid}/comments/{cid}/clear-review')
def clear_comment_review(
    vid: str,
    cid: str,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """管理员清除单条评论审核记录（设置 review_cleared=True）。"""
    c = db.get(Comment, cid)
    if not c:
        raise HTTPException(status_code=404, detail='评论不存在')
    if c.voice_id != vid:
        raise HTTPException(status_code=404, detail='评论不存在')
    c.review_cleared = True
    db.commit()
    return {'code': 200, 'message': 'ok'}


@router.post('/api/comments/clear-rejected')
def clear_all_rejected_comments(
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """管理员批量清除所有已驳回评论的审核记录（review_cleared=False 且 status='rejected'）。"""
    count = (
        db.query(Comment)
        .filter(Comment.review_cleared == False, Comment.status == 'rejected')  # noqa: E712
        .update({Comment.review_cleared: True}, synchronize_session='fetch')
    )
    db.commit()
    return {'code': 200, 'message': 'ok', 'count': count}
