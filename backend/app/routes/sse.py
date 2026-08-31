"""SSE 路由：实时通知推送（Server-Sent Events）。

替代 60 秒轮询，实现审核结果、私信、通知的即时推送。
每个用户维护一个 asyncio.Queue 列表（支持多标签页），5 秒心跳保活。
"""
import asyncio
import json
import logging
from typing import Optional

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse, JSONResponse

from app.database import SessionLocal
from app.deps import decode_token_safe
from app.models.user import User
from app.models.notification import Notification

logger = logging.getLogger(__name__)

router = APIRouter()

# ===== SSE 客户端管理 =====
# user_id -> list of asyncio.Queue（同一用户可能开多个标签页）
_sse_clients: dict[str, list[asyncio.Queue]] = {}

# 每用户最大 SSE 连接数（防止连接耗尽攻击）
MAX_SSE_PER_USER = 5

# 主事件循环引用（跨线程安全推送：sync 路由 -> async 事件循环）
_main_loop: Optional[asyncio.AbstractEventLoop] = None


def _set_main_loop(loop: asyncio.AbstractEventLoop) -> None:
    """缓存主事件循环引用，供跨线程 push_sse 使用。"""
    global _main_loop
    _main_loop = loop


def _safe_put(queue: asyncio.Queue, msg: dict) -> None:
    """线程安全的非阻塞入队，队列满时丢弃旧消息。"""
    try:
        queue.put_nowait(msg)
    except asyncio.QueueFull:
        logger.warning('SSE 队列已满，丢弃消息')


def register_sse_client(user_id: str) -> asyncio.Queue:
    """注册一个 SSE 客户端，返回其专属 asyncio.Queue（maxsize=50 防止无界增长）。

    每用户最多 MAX_SSE_PER_USER 个连接，超出时关闭最旧的连接。
    """
    if user_id not in _sse_clients:
        _sse_clients[user_id] = []
    if len(_sse_clients[user_id]) >= MAX_SSE_PER_USER:
        # 关闭最旧的连接（发送结束信号）
        old_q = _sse_clients[user_id].pop(0)
        try:
            old_q.put_nowait(None)
        except Exception:
            pass
    q: asyncio.Queue = asyncio.Queue(maxsize=50)
    _sse_clients[user_id].append(q)
    return q


def unregister_sse_client(user_id: str, queue: asyncio.Queue) -> None:
    """注销 SSE 客户端，从用户队列列表中移除。"""
    if user_id in _sse_clients:
        try:
            _sse_clients[user_id].remove(queue)
            if not _sse_clients[user_id]:
                del _sse_clients[user_id]
        except ValueError:
            pass


def push_sse(user_id: str, event: str, data) -> None:
    """向指定用户的所有 SSE 连接推送事件（非阻塞，跨线程安全）。

    从 sync 路由调用时通过 call_soon_threadsafe 安全投递到事件循环。
    队列满时丢弃消息，不阻塞调用方。
    """
    clients = list(_sse_clients.get(user_id, []))
    if not clients:
        return
    msg = {'event': event, 'data': data}
    for q in clients:
        if _main_loop and _main_loop.is_running():
            # 跨线程安全投递：sync 线程池 -> async 事件循环
            _main_loop.call_soon_threadsafe(_safe_put, q, msg)
        else:
            _safe_put(q, msg)


def push_sse_multi(user_ids: list, event: str, data) -> None:
    """向多个用户批量推送同一事件。"""
    for uid in user_ids:
        push_sse(uid, event, data)


# 别名：供 sync 路由（如 message.py）调用
push_sse_sync = push_sse


@router.get('/api/sse/stream')
async def sse_stream(request: Request):
    """SSE 长连接：向当前用户推送通知、未读数、聊天消息等实时事件。

    客户端使用 EventSource 连接，token 通过 query param 传递
    （EventSource 不支持自定义 Header）。
    """
    # EventSource 无法设置 Header，token 从 query param 读取
    token = request.query_params.get('token', '')
    user_id = decode_token_safe(token)
    if not user_id:
        return JSONResponse(status_code=401, content={'error': '请先登录'})

    # 缓存事件循环引用（供 sync 路由跨线程推送）
    _set_main_loop(asyncio.get_running_loop())

    async def generate():
        # 用临时 db 查询初始数据后立即 close，避免 SSE 长连接占用连接池
        db = SessionLocal()
        try:
            user = db.get(User, user_id)
            if not user:
                return

            # 推送初始未读数（只统计当前用户自己的通知，与 REST API 保持一致）
            count = (
                db.query(Notification)
                .filter(
                    Notification.user_id == user_id,
                    Notification.is_read == False,  # noqa: E712
                )
                .count()
            )
        finally:
            db.close()

        # 注册队列到当前用户 uid（仅当前用户，不再额外注册 first_admin.id）
        q = register_sse_client(user_id)
        try:
            yield f'event: unread_count\ndata: {json.dumps({"count": count}, ensure_ascii=False)}\n\n'

            while True:
                try:
                    # 5 秒超时 -> 心跳保活
                    msg = await asyncio.wait_for(q.get(), timeout=5.0)
                    if msg is None:
                        break  # 收到结束信号（连接被置换），关闭当前流
                    event = msg.get('event', 'message')
                    data_str = json.dumps(
                        msg.get('data'), ensure_ascii=False
                    )
                    yield f'event: {event}\ndata: {data_str}\n\n'
                except asyncio.TimeoutError:
                    yield ': heartbeat\n\n'
        finally:
            # 注销当前用户 uid 下的队列，避免内存泄漏
            unregister_sse_client(user_id, q)

    return StreamingResponse(
        generate(),
        media_type='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
            'Connection': 'keep-alive',
        },
    )
