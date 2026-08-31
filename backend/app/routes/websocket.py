"""WebSocket 路由：实时聊天（私信多轮对话）。

FastAPI 原生 WebSocket 实现，替代 Flask-Socket.IO。
房间机制：user_<uid>（私人）、admin_all（管理员群）、chat_<conv_id>（会话）
"""
import json
import logging
from datetime import datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import or_

from app.database import SessionLocal
from app.security import decode_token, is_token_revoked
from app.config import settings
from app.models.user import User
from app.models.message import Message
from app.models.notification import Notification
from app.models.chat_message import ChatMessage
from app.utils import gen_uuid, check_content_safe, get_user_nickname
from app.serialization import notification_to_dict, chat_message_to_dict
from app.services.redis_client import rate_limit_check, rate_limit_key
from app.routes.sse import push_sse

logger = logging.getLogger(__name__)

router = APIRouter()

# ===== 全局连接管理 =====
# room_id -> set of WebSocket（房间机制）
_ws_connections: dict[str, set[WebSocket]] = {}

# 每用户最大 WebSocket 连接数（防止连接耗尽攻击）
MAX_WS_PER_USER = 5

# 用户连接计数：user_id -> set of WebSocket
_user_ws_connections: dict[str, set[WebSocket]] = {}


class ConnectionManager:
    """WebSocket 连接管理器：按房间管理连接。

    room_id 命名规则：
      - user_<uid>   用户私人房间
      - admin_all    管理员群房间
      - chat_<conv_id> 会话房间
    """

    def connect(self, room_id: str, ws: WebSocket) -> None:
        """将 WebSocket 加入指定房间。"""
        _ws_connections.setdefault(room_id, set()).add(ws)

    def disconnect(self, room_id: str, ws: WebSocket) -> None:
        """从房间移除 WebSocket。"""
        if room_id in _ws_connections:
            _ws_connections[room_id].discard(ws)
            if not _ws_connections[room_id]:
                del _ws_connections[room_id]

    async def broadcast(self, room_id: str, message: dict) -> None:
        """向房间内所有连接广播消息，自动清理断开的连接。"""
        connections = list(_ws_connections.get(room_id, []))
        dead = []
        for ws in connections:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(room_id, ws)

    async def send_to_user(self, user_id: str, message: dict) -> None:
        """向指定用户的所有 WebSocket 连接发送消息。"""
        await self.broadcast(f'user_{user_id}', message)


# 全局管理器实例
manager = ConnectionManager()


def _is_admin(user: User) -> bool:
    """判断用户是否为管理员。"""
    return bool(user and (user.is_admin or user.role in ('super_admin', 'admin')))


@router.websocket('/api/ws')
async def websocket_endpoint(ws: WebSocket):
    """WebSocket 实时聊天端点。

    连接时通过 query param token 验证身份，加入对应房间。
    支持事件类型：join_chat / send_chat / mark_chat_read / ping
    """
    token = ws.query_params.get('token', '')
    payload = decode_token(token)
    if not payload:
        await ws.close(code=4001, reason='未授权')
        return

    user_id = payload.get('sub')
    if not user_id:
        await ws.close(code=4001, reason='未授权')
        return

    # 验证用户存在并检查管理员状态
    db = SessionLocal()
    try:
        # JWT 黑名单检查：已撤销的 token 拒绝连接
        if is_token_revoked(token, db):
            await ws.close(code=4001, reason='登录已失效，请重新登录')
            return
        user = db.get(User, user_id)
        if not user:
            await ws.close(code=4001, reason='用户不存在')
            return
        is_admin = _is_admin(user)
    finally:
        db.close()

    # 连接数限制：每用户最多 MAX_WS_PER_USER 个 WebSocket 连接
    _user_ws_connections.setdefault(user_id, set())
    if len(_user_ws_connections[user_id]) >= MAX_WS_PER_USER:
        await ws.close(code=4013, reason='连接数超过限制，请关闭其他标签页后重试')
        return

    await ws.accept()

    # 加入私人房间
    manager.connect(f'user_{user_id}', ws)
    # 注册用户连接（用于连接数限制计数）
    _user_ws_connections.setdefault(user_id, set()).add(ws)
    # 管理员额外加入 admin_all 房间
    if is_admin:
        manager.connect('admin_all', ws)

    # 记录此连接加入的所有房间（断开时统一清理）
    joined_rooms = {f'user_{user_id}'}
    if is_admin:
        joined_rooms.add('admin_all')

    try:
        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue

            event = msg.get('event', '')
            data = msg.get('data', {}) or {}

            # ===== 心跳保活 =====
            if event == 'ping':
                await ws.send_json({'event': 'pong'})

            # ===== 加入会话房间 =====
            elif event == 'join_chat':
                conv_id = data.get('conversationId', '')
                if not conv_id:
                    continue
                db = SessionLocal()
                try:
                    m = db.get(Message, conv_id)
                    if m and (m.user_id == user_id or is_admin):
                        room = f'chat_{conv_id}'
                        manager.connect(room, ws)
                        joined_rooms.add(room)
                        await ws.send_json({
                            'event': 'joined',
                            'data': {'conversationId': conv_id},
                        })
                finally:
                    db.close()

            # ===== 发送聊天消息 =====
            elif event == 'send_chat':
                # 限流检查（复用 Redis 限流，Redis 不可用时降级到进程内计数）
                allowed, _ = rate_limit_check(
                    rate_limit_key('chat', user_id),
                    settings.RATE_LIMIT_MESSAGE,
                    settings.RATE_LIMIT_WINDOW,
                )
                if not allowed:
                    await ws.send_json({
                        'event': 'error',
                        'data': {'error': '发送过于频繁，请稍后再试'},
                    })
                    continue
                conv_id = data.get('conversationId', '')
                content = (data.get('content') or '').strip()
                if not conv_id or not content:
                    await ws.send_json({
                        'event': 'error',
                        'data': {'error': '参数缺失'},
                    })
                    continue
                if len(content) > 1000:
                    await ws.send_json({
                        'event': 'error',
                        'data': {'error': '内容不能超过1000字'},
                    })
                    continue

                db = SessionLocal()
                try:
                    m = db.get(Message, conv_id)
                    if not m:
                        await ws.send_json({
                            'event': 'error',
                            'data': {'error': '会话不存在'},
                        })
                        continue

                    # 权限：管理员可回复任意会话，普通用户只能在自己的会话中发消息
                    if not is_admin and m.user_id != user_id:
                        await ws.send_json({
                            'event': 'error',
                            'data': {'error': '无权操作'},
                        })
                        continue

                    # 内容安全检测
                    is_safe, safe_msg = check_content_safe(content)
                    if not is_safe:
                        await ws.send_json({
                            'event': 'error',
                            'data': {'error': safe_msg or '内容不合规'},
                        })
                        continue

                    # 创建聊天消息
                    sender_type = 'admin' if is_admin else 'user'
                    chat_msg = ChatMessage(
                        id=gen_uuid(),
                        conversation_id=conv_id,
                        sender_type=sender_type,
                        sender_id=user_id,
                        content=content,
                        is_read=False,
                    )
                    db.add(chat_msg)

                    notif = None
                    admin_list = []

                    if is_admin:
                        # 管理员回复 -> 更新会话状态 + 通知用户
                        m.admin_reply = content
                        m.reply_time = datetime.utcnow()
                        m.status = 'replied'
                        preview = (
                            (content[:20] + '...')
                            if len(content) > 20
                            else content
                        )
                        notif = Notification(
                            id=gen_uuid(),
                            user_id=m.user_id,
                            type='message_replied',
                            text=f'管理员回复了你的私信"{preview}"',
                            is_read=False,
                            related_id=m.id,
                        )
                        db.add(notif)
                    else:
                        # 用户发消息 -> 更新状态 + 通知管理员
                        m.status = 'unread'
                        admin_list = db.query(User).filter(
                            or_(User.is_admin == True, User.role.in_(('super_admin', 'admin')))  # noqa: E712
                        ).all()
                        first_admin = admin_list[0] if admin_list else None
                        if first_admin:
                            preview = (
                                (content[:30] + '...')
                                if len(content) > 30
                                else content
                            )
                            notif = Notification(
                                id=gen_uuid(),
                                user_id=first_admin.id,
                                type='message_received',
                                text=f'收到新私信：{preview}',
                                is_read=False,
                                related_id=m.id,
                            )
                            db.add(notif)

                    db.commit()
                    db.refresh(chat_msg)

                    # 用户发消息给管理员时，管理员视角附带真实姓名
                    real_name = None
                    if not is_admin and m.user_id:
                        real_name = get_user_nickname(db, m.user_id)
                    admin_msg_data = chat_message_to_dict(
                        chat_msg, real_name if real_name else None
                    )

                    # 构建消息数据（用户本人视角不含真实姓名）
                    msg_data = {
                        'id': chat_msg.id,
                        'conversationId': conv_id,
                        'senderType': sender_type,
                        'senderId': user_id,
                        'content': content,
                        'isRead': False,
                        'timeText': '刚刚',
                        'createdAt': (
                            chat_msg.created_at.isoformat()
                            if chat_msg.created_at
                            else None
                        ),
                    }

                    # WebSocket 实时推送到会话房间
                    # 用户发消息时带真实姓名（管理员可见），管理员回复时不含
                    await manager.broadcast(
                        f'chat_{conv_id}',
                        {'event': 'chat_message', 'data': admin_msg_data},
                    )

                    # 直接给发送者发送 chat_sent 事件（确保发送者收到自己的消息回显）
                    # 发送者可能不在 chat_{conv_id} room 中，需单独发送确认
                    await ws.send_json({
                        'event': 'chat_sent',
                        'data': msg_data,
                    })

                    # SSE + WebSocket 推送给接收方
                    if is_admin:
                        # 管理员回复 -> 推送给用户
                        push_sse(m.user_id, 'chat_message', msg_data)
                        await manager.send_to_user(
                            m.user_id,
                            {'event': 'chat_message', 'data': msg_data},
                        )
                        if notif:
                            push_sse(
                                m.user_id,
                                'notification',
                                notification_to_dict(notif),
                            )
                            cnt = (
                                db.query(Notification)
                                .filter_by(user_id=m.user_id, is_read=False)
                                .count()
                            )
                            push_sse(
                                m.user_id, 'unread_count', {'count': cnt}
                            )
                            # 企微应用消息推送给用户（手机端通知）
                            try:
                                from app.services.notify import push_wecom_to_user
                                push_wecom_to_user(db, m.user_id, 'message_replied', notif.text, m.id)
                            except Exception:
                                pass
                    else:
                        # 用户发消息 -> 推送给所有在线管理员
                        await manager.broadcast(
                            'admin_all',
                            {'event': 'chat_message', 'data': admin_msg_data},
                        )
                        for admin in admin_list:
                            push_sse(
                                admin.id, 'chat_message', admin_msg_data
                            )
                        # 通知 + 未读数仅推送给拥有该通知的管理员（first_admin）
                        # 其他管理员仅收到 chat_message，不收到不属于自己的通知
                        if notif and first_admin:
                            push_sse(
                                first_admin.id,
                                'notification',
                                notification_to_dict(notif),
                            )
                            cnt = (
                                db.query(Notification)
                                .filter_by(
                                    user_id=first_admin.id, is_read=False
                                )
                                .count()
                            )
                            push_sse(
                                first_admin.id,
                                'unread_count',
                                {'count': cnt},
                            )
                            # 企微应用消息推送给管理员（手机端通知）
                            try:
                                from app.services.notify import push_wecom_to_user
                                push_wecom_to_user(db, first_admin.id, 'message_received', notif.text, m.id)
                            except Exception:
                                pass

                finally:
                    db.close()

            # ===== 标记会话已读 =====
            elif event == 'mark_chat_read':
                conv_id = data.get('conversationId', '')
                if not conv_id:
                    continue
                db = SessionLocal()
                try:
                    m = db.get(Message, conv_id)
                    if not m:
                        continue
                    if not is_admin and m.user_id != user_id:
                        continue

                    # 用户标记管理员消息已读；管理员标记用户消息已读
                    target_sender = 'admin' if not is_admin else 'user'
                    db.query(ChatMessage).filter_by(
                        conversation_id=conv_id,
                        sender_type=target_sender,
                        is_read=False,
                    ).update({ChatMessage.is_read: True})

                    # 同步标记关联通知为已读，避免未读角标永久残留
                    notif_type = 'message_received' if is_admin else 'message_replied'
                    db.query(Notification).filter(
                        Notification.type == notif_type,
                        Notification.related_id == conv_id,
                        Notification.user_id == user_id,
                        Notification.is_read == False,  # noqa: E712
                    ).update({Notification.is_read: True})

                    # 若会话中已无未读消息，更新 Message.status
                    remaining_unread = (
                        db.query(ChatMessage)
                        .filter_by(
                            conversation_id=conv_id, is_read=False
                        )
                        .count()
                    )
                    if remaining_unread == 0 and m.status == 'unread':
                        m.status = 'replied'

                    db.commit()

                    # 通知对方消息已读
                    await manager.broadcast(
                        f'chat_{conv_id}',
                        {
                            'event': 'chat_read',
                            'data': {
                                'conversationId': conv_id,
                                'readBy': 'admin' if is_admin else 'user',
                            },
                        },
                    )

                    # 已读后重新推送未读数给当前用户（前端角标即时清零）
                    try:
                        from app.routes.sse import push_sse_sync
                        unread_count = db.query(Notification).filter_by(
                            user_id=user_id, is_read=False
                        ).count()
                        push_sse_sync(user_id, 'unread_count', {'count': unread_count})
                    except Exception:
                        pass
                finally:
                    db.close()

    except WebSocketDisconnect:
        logger.info('WebSocket 断开: user=%s', user_id)
    except Exception as e:
        logger.error('WebSocket 异常: %s', e, exc_info=True)
    finally:
        # 从所有已加入的房间中移除
        for room in joined_rooms:
            manager.disconnect(room, ws)
        # 清理用户连接计数
        if user_id in _user_ws_connections:
            _user_ws_connections[user_id].discard(ws)
            if not _user_ws_connections[user_id]:
                del _user_ws_connections[user_id]
