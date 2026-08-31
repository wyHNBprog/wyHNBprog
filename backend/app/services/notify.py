"""统一通知推送服务：SSE 实时推送 + 企业微信应用消息推送。

调用流程：
1. 路由中创建 Notification 记录并 commit
2. 调用 push_notification() 统一推送
   - SSE 推送给前台在线用户（即时）
   - 企微应用消息推送给离线用户（手机端通知）
3. 两种推送互相独立，任一失败不影响另一个

使用方式：
    from app.services.notify import push_notification
    push_notification(db, user_id, 'voice_approved', '您的留言已通过审核')
"""
import logging

from sqlalchemy.orm import Session

from app.config import settings
from app.models.user import User
from app.models.notification import Notification
from app.services.wecom import send_text_message, send_textcard_message

logger = logging.getLogger(__name__)

# 通知类型 -> 企微卡片标题映射
NOTIF_TITLE_MAP = {
    'voice_approved': '心声审核通过',
    'voice_rejected': '心声审核未通过',
    'idea_approved': '金点子审核通过',
    'idea_rejected': '金点子审核未通过',
    'message_replied': '私信回复通知',
    'message_received': '新私信通知',
    'feedback_replied': '反馈回复通知',
    'comment_approved': '评论审核通过',
    'comment_rejected': '评论审核未通过',
    'system': '系统通知',
}

# 通知类型 -> 前端跳转路径映射
NOTIF_ROUTE_MAP = {
    'voice_approved': '/voices',
    'voice_rejected': '/voices',
    'idea_approved': '/ideas',
    'idea_rejected': '/ideas',
    'message_replied': '/messages',
    'message_received': '/messages',
    'feedback_replied': '/feedback',
    'comment_approved': '/',
    'comment_rejected': '/',
    'system': '/',
}


def _build_card_url(notif_type: str, related_id: str = None) -> str:
    """构建卡片点击跳转 URL。"""
    base = getattr(settings, 'WECOM_APP_URL', '') or ''
    if not base:
        return ''
    route = NOTIF_ROUTE_MAP.get(notif_type, '/')
    url = base.rstrip('/') + '/#' + route
    if related_id:
        url += '?id=' + related_id
    return url


def push_wecom_to_user(db: Session, user_id: str, notif_type: str, text: str, related_id: str = None) -> bool:
    """向指定用户推送企业微信应用消息。

    查找用户的 wecom_user_id，若存在则发送卡片消息（带跳转链接），
    若 WECOM_APP_URL 未配置则退化为纯文本消息。

    Args:
        db: 数据库会话
        user_id: 系统内部用户 ID
        notif_type: 通知类型（见 NOTIF_TITLE_MAP）
        text: 通知文本内容
        related_id: 关联内容 ID（用于构建跳转链接）

    Returns:
        True 表示推送成功（或企微未启用时静默返回 False）
    """
    if not settings.wecom_enabled:
        return False

    try:
        user = db.get(User, user_id)
        if not user or not user.wecom_user_id:
            return False

        title = NOTIF_TITLE_MAP.get(notif_type, '新通知')
        card_url = _build_card_url(notif_type, related_id)

        if card_url:
            # 有 URL 时发卡片消息（可点击跳转）
            success = send_textcard_message(
                wecom_user_id=user.wecom_user_id,
                title=title,
                description=text,
                url=card_url,
            )
        else:
            # 无 URL 时发纯文本消息
            full_text = f'【{title}】{text}'
            success = send_text_message(
                wecom_user_id=user.wecom_user_id,
                content=full_text,
            )
        return success
    except Exception as e:
        logger.error('企微推送失败(user=%s): %s', user_id, e)
        return False


def push_notification(
    db: Session,
    user_id: str,
    notif_type: str,
    text: str,
    notif_data: dict = None,
    related_id: str = None,
    skip_sse: bool = False,
    skip_wecom: bool = False,
) -> None:
    """统一推送通知：SSE（前台实时）+ 企微应用消息（后台/离线）。

    两种推送互相独立，任一失败不影响另一个。

    Args:
        db: 数据库会话
        user_id: 接收用户 ID
        notif_type: 通知类型
        text: 通知文本（用于企微推送）
        notif_data: SSE 推送的通知对象（None 时跳过 notification 事件）
        related_id: 关联内容 ID（用于企微卡片跳转链接）
        skip_sse: 跳过 SSE 推送
        skip_wecom: 跳过企微推送
    """
    # 1. SSE 推送（前台实时）
    if not skip_sse:
        try:
            from app.routes.sse import push_sse_sync
            if notif_data:
                push_sse_sync(user_id, 'notification', notif_data)
            # 推送未读数
            count = db.query(Notification).filter_by(
                user_id=user_id, is_read=False
            ).count()
            push_sse_sync(user_id, 'unread_count', {'count': count})
        except Exception as e:
            logger.warning('SSE 推送失败(user=%s): %s', user_id, e)

    # 2. 企微应用消息推送（后台/离线）
    if not skip_wecom:
        push_wecom_to_user(db, user_id, notif_type, text, related_id)
