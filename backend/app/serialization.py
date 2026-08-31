"""序列化函数：将 ORM 对象转为前端可用的字典。

保留 isMine/isLiked/hasVoted 等字段，支持批量预加载优化。
"""
from typing import Optional

from sqlalchemy.orm import Session

from app.utils import (
    ANON_NAME,
    _local_str,
    get_current_uid_safe,
    is_liked_voice,
    is_voted_idea,
    is_liked_comment,
    get_user_nickname,
    get_feedback_latest_reply,
)
from app.models.user import User
from app.models.voice import Voice, VoiceTag
from app.models.comment import Comment
from app.models.idea import Idea
from app.models.feedback import Feedback, FeedbackReply
from app.models.message import Message
from app.models.chat_message import ChatMessage
from app.models.announce import Announce
from app.models.notification import Notification


def voice_to_dict(db: Session, v: Voice, tags=None, include_real_name: bool = False) -> dict:
    """心声序列化。"""
    author_nickname = get_user_nickname(db, v.user_id) if v.user_id else None
    current_uid = get_current_uid_safe()
    # 评论者昵称：优先用批量缓存（_bulk_user_map_ctx），回退到单条查询
    comment_users = {}
    comment_user_ids = set(c.user_id for c in (v.comments or []) if c.user_id)
    for cuid in comment_user_ids:
        nick = get_user_nickname(db, cuid)
        if nick:
            comment_users[cuid] = nick
    # 非管理员：只返回已审核通过的评论 + 自己的 pending/rejected 评论（与 voices/ideas 可见性逻辑一致）
    # 管理员视图：过滤已清除审核记录的 pending/rejected 评论
    visible_comments = [
        c for c in (v.comments or [])
        if (c.status == 'approved' or include_real_name or c.user_id == current_uid)
        and not (getattr(c, 'review_cleared', False) and c.status in ('pending', 'rejected'))
    ]
    data = {
        'id': v.id,
        'content': v.content,
        'anonName': v.anon_name or ANON_NAME,
        'isAnonymous': v.is_anonymous,
        'tags': tags if tags is not None else [t.tag for t in (v.tags or [])],
        'timeText': _local_str(v.created_at),
        'likeCount': v.like_count or 0,
        'isLiked': is_liked_voice(db, v.id),
        'isMine': v.user_id == current_uid,
        'status': v.status,
        'rejectReason': v.reject_reason or '',
        'reviewCleared': v.review_cleared or False,
        'commentCount': len([c for c in (v.comments or []) if c.status == 'approved'])
        if v.comments
        else 0,
        'comments': [
            {
                'id': c.id,
                'content': c.content,
                'anonName': c.anon_name or ANON_NAME,
                'timeText': _local_str(c.created_at),
                'status': c.status,
                'rejectReason': c.reject_reason or '',
                'reviewCleared': getattr(c, 'review_cleared', False) or False,
                'realName': comment_users.get(c.user_id) if include_real_name else None,
                'isMine': c.user_id == current_uid,
                'likeCount': c.like_count or 0,
                'isLiked': is_liked_comment(db, c.id),
            }
            for c in visible_comments
        ],
    }
    if include_real_name and author_nickname:
        data['realName'] = author_nickname
    return data


def idea_to_dict(db: Session, i: Idea, include_real_name: bool = False) -> dict:
    """金点子序列化。"""
    author_nickname = get_user_nickname(db, i.user_id) if i.user_id else None
    data = {
        'id': i.id,
        'title': i.title,
        'desc': i.description or '',
        'category': i.category or '其他',
        'anonName': i.anon_name or ANON_NAME,
        'isAnonymous': i.is_anonymous if i.is_anonymous is not None else True,
        'timeText': _local_str(i.created_at),
        'voteCount': i.vote_count or 0,
        'hasVoted': is_voted_idea(db, i.id),
        'isMine': i.user_id == get_current_uid_safe(),
        'status': i.status if i.status in ('voting', 'pending', 'rejected') else 'voting',
        'hasFlower': i.has_flower or False,
        'flowerCount': i.flower_count or 0,
        'hasFirework': i.has_firework or False,
        'fireworkCount': i.firework_count or 0,
        'rejectReason': i.reject_reason or '',
        'reviewCleared': i.review_cleared or False,
    }
    if include_real_name and author_nickname:
        data['realName'] = author_nickname
    return data


def feedback_to_dict(db: Session, f: Feedback, include_real_name: bool = False) -> dict:
    """反馈序列化。"""
    latest_reply = get_feedback_latest_reply(db, f.id)
    author_nickname = get_user_nickname(db, f.user_id) if f.user_id else None
    data = {
        'id': f.id,
        'category': f.type or '其他',
        'content': f.content or '',
        'anonName': f.anon_name or ANON_NAME,
        'timeText': _local_str(f.created_at),
        'status': f.status,
        'reply': latest_reply.content if latest_reply else None,
        'replyTime': _local_str(latest_reply.created_at) if latest_reply else None,
    }
    if include_real_name and author_nickname:
        data['realName'] = author_nickname
    return data


def message_to_dict(db: Session, m: Message, include_real_name: bool = False) -> dict:
    """私信序列化。"""
    author_nickname = get_user_nickname(db, m.user_id) if m.user_id else None
    replies = []
    if m.admin_reply:
        replies.append({'content': m.admin_reply, 'timeText': _local_str(m.reply_time)})

    # 查询聊天消息
    chat_msgs = db.query(ChatMessage).filter_by(conversation_id=m.id).order_by(ChatMessage.created_at.asc()).all()
    if chat_msgs:
        chat_data = [cm.to_dict() for cm in chat_msgs]
        # 计算未读数
        current_uid = get_current_uid_safe()
        if current_uid:
            is_admin_view = include_real_name
            if is_admin_view:
                unread = sum(1 for cm in chat_msgs if cm.sender_type == 'user' and not cm.is_read)
            else:
                unread = sum(1 for cm in chat_msgs if cm.sender_type == 'admin' and not cm.is_read)
        else:
            unread = 0
    else:
        # 旧数据兼容
        chat_data = []
        if m.content:
            chat_data.append({'id': m.id + '_u', 'conversationId': m.id, 'senderType': 'user', 'senderId': m.user_id, 'content': m.content, 'isRead': True, 'createdAt': m.created_at.isoformat() if m.created_at else None})
        if m.admin_reply:
            chat_data.append({'id': m.id + '_a', 'conversationId': m.id, 'senderType': 'admin', 'senderId': None, 'content': m.admin_reply, 'isRead': True, 'createdAt': m.reply_time.isoformat() if m.reply_time else None})
        unread = 0 if m.status != 'unread' else 1

    data = {
        'id': m.id,
        'content': m.content,
        'anonName': m.anon_name or ANON_NAME,
        'timeText': _local_str(m.created_at),
        'status': m.status,
        'replies': replies,
        'chatMessages': chat_data,
        'unreadCount': unread,
    }
    if include_real_name and author_nickname:
        data['realName'] = author_nickname
    return data


def chat_message_to_dict(
    cm: ChatMessage,
    real_name: Optional[str] = None,
) -> dict:
    """聊天单条消息序列化。

    real_name 仅管理员视角传入，用于前端展示私信发起者的真实姓名。
    """
    data = cm.to_dict()
    if real_name:
        data['realName'] = real_name
    return data


def announce_to_dict(a: Announce) -> dict:
    """公告序列化。"""
    return {
        'id': a.id,
        'title': a.title,
        'content': a.content or '',
        'pinned': a.is_pinned or False,
        'timeText': _local_str(a.created_at, '%Y-%m-%d', ''),
    }


def notification_to_dict(n: Notification) -> dict:
    """通知序列化。"""
    return {
        'id': n.id,
        'type': n.type,
        'text': n.text,
        'timeText': _local_str(n.created_at),
        'read': n.is_read or False,
    }
