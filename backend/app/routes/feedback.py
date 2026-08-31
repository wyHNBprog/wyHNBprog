"""反馈路由：提交反馈 + 管理员回复。"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_admin, get_current_user_required
from app.models.user import User
from app.models.feedback import Feedback, FeedbackReply
from app.models.notification import Notification
from app.serialization import feedback_to_dict
from app.schemas.feedback import FeedbackCreate, FeedbackReplyCreate
from app.utils import gen_uuid, ANON_NAME, check_content_safe

router = APIRouter()


@router.post('/api/feedbacks')
def create_feedback(
    body: FeedbackCreate,
    user: User = Depends(get_current_user_required),
    db: Session = Depends(get_db),
):
    """提交反馈。"""
    content = (body.content or '').strip()
    if not content or len(content) > 1000:
        raise HTTPException(status_code=400, detail='内容长度应在1-1000字之间')

    is_safe, msg = check_content_safe(content)
    if not is_safe:
        raise HTTPException(status_code=400, detail=msg or '内容不合规')

    f = Feedback(
        id=gen_uuid(),
        user_id=user.id,
        type=body.category or '其他',
        content=content,
        anon_name=ANON_NAME,
        is_anonymous=True,
        status='pending',
    )
    db.add(f)
    db.commit()
    return {'ok': True, 'feedback': feedback_to_dict(db, f)}


@router.put('/api/feedbacks/{fid}/reply')
def reply_feedback(
    fid: str,
    body: FeedbackReplyCreate,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """管理员回复反馈（事务原子化：回复与通知一起 commit）。"""
    f = db.get(Feedback, fid)
    if not f:
        raise HTTPException(status_code=404, detail='反馈不存在')

    reply_content = (body.reply or '').strip()
    if not reply_content:
        raise HTTPException(status_code=400, detail='回复内容不能为空')

    # 使用当前操作管理员 ID
    admin_id = admin.id
    r = FeedbackReply(
        id=gen_uuid(),
        feedback_id=fid,
        admin_id=admin_id,
        content=reply_content,
    )
    db.add(r)
    f.status = 'replied'
    # 通知反馈提交者（与回复在同一事务中 commit，避免数据不一致）
    notif = None
    if f.user_id:
        notif = Notification(
            id=gen_uuid(), user_id=f.user_id, type='feedback_replied',
            text='您的反馈已收到回复', is_read=False, related_id=f.id,
        )
        db.add(notif)
    db.commit()
    if notif:
        db.refresh(notif)

    # SSE + 企微应用消息推送
    if notif and f.user_id:
        try:
            from app.services.notify import push_notification
            from app.serialization import notification_to_dict
            push_notification(
                db, f.user_id, 'feedback_replied', notif.text,
                notif_data=notification_to_dict(notif), related_id=f.id,
            )
        except Exception:
            pass

    return {'ok': True, 'feedback': feedback_to_dict(db, f)}
