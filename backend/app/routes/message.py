"""私信路由：发送私信 + 管理员回复 + 删除。"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.deps import get_current_admin, get_current_user_required, get_user_with_context_required
from app.models.user import User
from app.models.message import Message
from app.models.notification import Notification
from app.models.chat_message import ChatMessage
from app.serialization import message_to_dict, notification_to_dict, chat_message_to_dict
from app.schemas.message import MessageCreate, MessageReplyCreate
from app.schemas.voice import ChatMessageCreate
from app.services.redis_client import rate_limit_check, rate_limit_key
from app.utils import gen_uuid, ANON_NAME, check_content_safe

router = APIRouter()


def _is_admin(user: User) -> bool:
    return bool(user and (user.is_admin or user.role in ('super_admin', 'admin')))


@router.get('/api/messages')
@router.get('/api/messages/list')
def list_messages(
    user: User = Depends(get_user_with_context_required),
    db: Session = Depends(get_db),
):
    """获取私信列表（非管理员只看自己的私信）。"""
    show_real = _is_admin(user)
    uid = user.id
    if show_real:
        msgs = db.query(Message).order_by(Message.created_at.desc()).all()
    else:
        msgs = db.query(Message).filter_by(user_id=uid).order_by(Message.created_at.desc()).all()
    return {'messages': [message_to_dict(db, m, include_real_name=show_real) for m in msgs]}


@router.post('/api/messages')
def create_message(
    body: MessageCreate,
    user: User = Depends(get_current_user_required),
    db: Session = Depends(get_db),
):
    """发送私信（管理员无法使用私信功能）。"""
    is_admin = user.is_admin or user.role in ('super_admin', 'admin')
    if is_admin:
        raise HTTPException(status_code=403, detail='管理员无法使用私信功能')

    is_safe, msg = check_content_safe(body.content or '')
    if not is_safe:
        raise HTTPException(status_code=400, detail=msg or '内容不合规')

    m = Message(
        id=gen_uuid(),
        user_id=user.id,
        content=body.content or '',
        anon_name=body.anonName or ANON_NAME,
        status='unread',
    )
    db.add(m)
    db.flush()

    # 创建初始 ChatMessage（与 Message 同一事务，确保聊天消息格式一致）
    chat_msg = ChatMessage(
        id=gen_uuid(),
        conversation_id=m.id,
        sender_type='user',
        sender_id=user.id,
        content=body.content or '',
        is_read=False,
    )
    db.add(chat_msg)

    # 创建通知给管理员并推送 SSE
    admin_notif = None
    first_admin_id = None
    try:
        first_admin = db.query(User).filter(
            or_(User.is_admin == True, User.role.in_(('super_admin', 'admin')))  # noqa: E712
        ).first()
        if first_admin:
            first_admin_id = first_admin.id
            admin_notif = Notification(
                id=gen_uuid(), user_id=first_admin.id, type='message_received',
                text='您有新的私信消息', is_read=False, related_id=m.id,
            )
            db.add(admin_notif)
    except Exception:
        pass

    db.commit()
    db.refresh(chat_msg)
    if admin_notif:
        db.refresh(admin_notif)

    # 推送 SSE 给管理员（异步，不阻塞响应）
    try:
        from app.routes.sse import push_sse_sync
        if first_admin_id:
            push_sse_sync(first_admin_id, 'chat_message', chat_msg.to_dict())
            if admin_notif:
                push_sse_sync(first_admin_id, 'notification', notification_to_dict(admin_notif))
            admin_count = db.query(Notification).filter_by(
                user_id=first_admin_id, is_read=False
            ).count()
            push_sse_sync(first_admin_id, 'unread_count', {'count': admin_count})
    except Exception:
        pass

    # 企微应用消息推送给管理员（手机端通知）
    if first_admin_id and admin_notif:
        try:
            from app.services.notify import push_wecom_to_user
            push_wecom_to_user(db, first_admin_id, 'message_received', admin_notif.text, m.id)
        except Exception:
            pass

    return {'ok': True, 'message': message_to_dict(db, m)}


@router.put('/api/messages/{mid}/reply')
def reply_message(
    mid: str,
    body: MessageReplyCreate,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """管理员回复私信（事务原子化：回复与通知一起 commit）。"""
    m = db.get(Message, mid)
    if not m:
        raise HTTPException(status_code=404, detail='私信不存在')
    reply_content = (body.content or '').strip()
    if not reply_content:
        raise HTTPException(status_code=400, detail='回复内容不能为空')
    m.admin_reply = reply_content
    m.reply_time = datetime.utcnow()
    m.status = 'replied'

    # 创建 ChatMessage 记录（与 WebSocket 回复保持一致，确保聊天历史完整）
    chat_msg = ChatMessage(
        id=gen_uuid(),
        conversation_id=mid,
        sender_type='admin',
        sender_id=admin.id,
        content=reply_content,
        is_read=False,
    )
    db.add(chat_msg)

    # 通知私信发送者（与回复在同一事务中 commit，避免数据不一致）
    notif = None
    if m.user_id:
        notif = Notification(
            id=gen_uuid(), user_id=m.user_id, type='message_replied',
            text='您的私信已收到回复', is_read=False, related_id=m.id,
        )
        db.add(notif)
    db.commit()

    # 推送 SSE 给用户（异步，不阻塞响应）
    try:
        from app.routes.sse import push_sse_sync
        push_sse_sync(m.user_id, 'chat_message', chat_msg.to_dict())
        if notif:
            push_sse_sync(m.user_id, 'notification', notification_to_dict(notif))
            cnt = db.query(Notification).filter_by(user_id=m.user_id, is_read=False).count()
            push_sse_sync(m.user_id, 'unread_count', {'count': cnt})
    except Exception:
        pass

    # 企微应用消息推送给用户（手机端通知）
    if notif and m.user_id:
        try:
            from app.services.notify import push_wecom_to_user
            push_wecom_to_user(db, m.user_id, 'message_replied', notif.text, m.id)
        except Exception:
            pass

    return {'ok': True, 'message': message_to_dict(db, m)}


@router.delete('/api/messages/{mid}')
def delete_message(
    mid: str,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """管理员删除私信（同时清理关联通知）。"""
    m = db.get(Message, mid)
    if not m:
        raise HTTPException(status_code=404, detail='私信不存在')
    # 清理关联通知（related_id 指向被删内容）
    db.query(Notification).filter_by(related_id=mid).delete()
    db.delete(m)
    db.commit()
    return {'ok': True}


@router.get('/api/messages/{mid}/chat')
def get_chat_messages(
    mid: str,
    user: User = Depends(get_user_with_context_required),
    db: Session = Depends(get_db),
):
    """获取会话所有聊天消息（含旧数据兼容合成）。"""
    m = db.get(Message, mid)
    if not m:
        raise HTTPException(status_code=404, detail='会话不存在')

    # 权限校验
    is_admin_user = _is_admin(user)
    if not is_admin_user and m.user_id != user.id:
        raise HTTPException(status_code=403, detail='无权查看此会话')

    chat_msgs = db.query(ChatMessage).filter_by(conversation_id=mid).order_by(ChatMessage.created_at.asc()).all()

    # 管理员视角：为私信发起者（用户）的消息附带真实姓名
    real_name = None
    if is_admin_user and m.user_id:
        from app.utils import get_user_nickname
        real_name = get_user_nickname(db, m.user_id)

    # 旧数据兼容：没有 ChatMessage 时，从 Message 合成
    if not chat_msgs:
        synthetic = []
        if m.content:
            synthetic.append({
                'id': m.id + '_u',
                'conversationId': mid,
                'senderType': 'user',
                'senderId': m.user_id,
                'content': m.content,
                'isRead': True,
                'createdAt': m.created_at.isoformat() if m.created_at else None,
                **({'realName': real_name} if real_name else {}),
            })
        if m.admin_reply:
            synthetic.append({
                'id': m.id + '_a',
                'conversationId': mid,
                'senderType': 'admin',
                'senderId': None,
                'content': m.admin_reply,
                'isRead': True,
                'createdAt': m.reply_time.isoformat() if m.reply_time else None,
            })
        return synthetic

    return [chat_message_to_dict(cm, real_name if cm.sender_type == 'user' else None) for cm in chat_msgs]


@router.post('/api/messages/{mid}/chat')
def send_chat_message(
    mid: str,
    body: dict,
    user: User = Depends(get_current_user_required),
    db: Session = Depends(get_db),
):
    """通过 REST 发送聊天消息（WebSocket 降级方案）。"""
    m = db.get(Message, mid)
    if not m:
        raise HTTPException(status_code=404, detail='会话不存在')

    is_admin_user = _is_admin(user)
    # 权限：用户只能在自己的会话中发消息，管理员可在任意会话中回复
    if not is_admin_user and m.user_id != user.id:
        raise HTTPException(status_code=403, detail='无权在此会话中发送消息')
    # 管理员不能给自己发私信
    if is_admin_user and m.user_id == user.id:
        raise HTTPException(status_code=403, detail='管理员不能给自己发私信')

    content = body.content.strip()
    if not content:
        raise HTTPException(status_code=400, detail='消息内容不能为空')
    if len(content) > 1000:
        raise HTTPException(status_code=400, detail='消息内容不能超过1000字')

    # 限流
    allowed, count = rate_limit_check(rate_limit_key('chat', user.id), settings.RATE_LIMIT_MESSAGE, settings.RATE_LIMIT_WINDOW)
    if not allowed:
        raise HTTPException(status_code=429, detail='发送过于频繁，请稍后再试')

    # 内容安全检测
    is_safe, msg = check_content_safe(content)
    if not is_safe:
        raise HTTPException(status_code=400, detail=msg or '内容不合规')

    cm = ChatMessage(
        id=gen_uuid(),
        conversation_id=mid,
        sender_type='admin' if is_admin_user else 'user',
        sender_id=user.id,
        content=content,
        is_read=False,
    )
    db.add(cm)

    # 更新会话状态
    if is_admin_user:
        m.status = 'replied'
        m.reply_time = datetime.utcnow()
    else:
        m.status = 'unread'

    # 管理员回复时创建通知给用户
    if is_admin_user and m.user_id:
        db.add(Notification(
            id=gen_uuid(), user_id=m.user_id, type='message_replied',
            text='您有新的私信回复', is_read=False, related_id=m.id,
        ))

    # 用户发消息时创建通知给管理员
    admin_notif = None
    first_admin_id = None
    if not is_admin_user:
        first_admin = db.query(User).filter(
            or_(User.is_admin == True, User.role.in_(('super_admin', 'admin')))  # noqa: E712
        ).first()
        if first_admin:
            first_admin_id = first_admin.id
            admin_notif = Notification(
                id=gen_uuid(), user_id=first_admin.id, type='message_received',
                text='您有新的私信消息', is_read=False, related_id=m.id,
            )
            db.add(admin_notif)

    db.commit()
    db.refresh(cm)
    if admin_notif:
        db.refresh(admin_notif)

    # 用户发消息给管理员时，管理员视角附带真实姓名
    real_name = None
    if not is_admin_user and m.user_id:
        from app.utils import get_user_nickname
        real_name = get_user_nickname(db, m.user_id)
    admin_data = chat_message_to_dict(cm, real_name if real_name else None)

    # 触发 SSE 推送（异步，不阻塞响应）
    try:
        from app.routes.sse import push_sse_sync
        if is_admin_user:
            # 管理员回复 -> 推送聊天消息给用户
            push_sse_sync(m.user_id, 'chat_message', cm.to_dict())
        elif first_admin_id:
            # 用户发消息 -> 推送聊天消息、通知、未读数给管理员
            push_sse_sync(first_admin_id, 'chat_message', admin_data)
            if admin_notif:
                push_sse_sync(first_admin_id, 'notification', notification_to_dict(admin_notif))
            admin_count = db.query(Notification).filter_by(
                user_id=first_admin_id, is_read=False
            ).count()
            push_sse_sync(first_admin_id, 'unread_count', {'count': admin_count})
    except Exception:
        pass

    # 企微应用消息推送（手机端通知）
    try:
        from app.services.notify import push_wecom_to_user
        if is_admin_user and m.user_id:
            push_wecom_to_user(db, m.user_id, 'message_replied', '您有新的私信回复', m.id)
        elif first_admin_id and admin_notif:
            push_wecom_to_user(db, first_admin_id, 'message_received', admin_notif.text, m.id)
    except Exception:
        pass

    return {'ok': True, 'message': chat_message_to_dict(cm, real_name if (not is_admin_user and real_name) else None)}


@router.put('/api/messages/{mid}/read')
def mark_conversation_read(
    mid: str,
    user: User = Depends(get_current_user_required),
    db: Session = Depends(get_db),
):
    """标记会话已读。"""
    m = db.get(Message, mid)
    if not m:
        raise HTTPException(status_code=404, detail='会话不存在')

    is_admin_user = _is_admin(user)
    if not is_admin_user and m.user_id != user.id:
        raise HTTPException(status_code=403, detail='无权操作')

    # 标记聊天消息已读
    if is_admin_user:
        db.query(ChatMessage).filter_by(conversation_id=mid, sender_type='user', is_read=False).update({'is_read': True})
    else:
        db.query(ChatMessage).filter_by(conversation_id=mid, sender_type='admin', is_read=False).update({'is_read': True})

    # 同步标记关联通知为已读，避免未读角标永久残留
    # 管理员已读 -> 清自己收到的 message_received；用户已读 -> 清自己收到的 message_replied
    notif_type = 'message_received' if is_admin_user else 'message_replied'
    db.query(Notification).filter(
        Notification.type == notif_type,
        Notification.related_id == mid,
        Notification.user_id == user.id,
        Notification.is_read == False,  # noqa: E712
    ).update({'is_read': True})

    # 更新会话状态：管理员标记已读时 unread->replied（表示已处理），
    # 用户标记已读时保持 unread 不变（避免管理员误以为已回复）
    if is_admin_user and m.status == 'unread':
        m.status = 'replied'

    db.commit()
    # 已读后重新推送未读数给当前用户（前端角标即时清零）
    try:
        from app.routes.sse import push_sse_sync
        unread_count = db.query(Notification).filter_by(
            user_id=user.id, is_read=False
        ).count()
        push_sse_sync(user.id, 'unread_count', {'count': unread_count})
    except Exception:
        pass
    return {'ok': True}
