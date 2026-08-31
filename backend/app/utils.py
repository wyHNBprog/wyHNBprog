"""通用工具：UUID 生成、时区转换、内容安全检测、批量预加载上下文。"""
import contextvars
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, Set

# 中国时区（+8），统一将后端 naive UTC 时间转本地展示
CHINA_TZ = timezone(timedelta(hours=8))

# 匿名默认昵称
ANON_NAME = 'nnit热心网友'


def gen_uuid() -> str:
    """生成 32 位无横线 UUID 字符串。"""
    return str(uuid.uuid4()).replace('-', '')[:32]


def _local_str(dt, fmt='%m-%d %H:%M', default='刚刚') -> str:
    """将 naive UTC datetime 转为本地时区字符串。"""
    if not dt:
        return default
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(CHINA_TZ).strftime(fmt)


def check_content_safe(content: str):
    """内容安全检测：调用企业微信 msg_sec_check。

    企业微信未配置时跳过检测（返回安全），检测异常时不阻断。
    """
    from app.services.content_security import check_ugc_content
    return check_ugc_content(content, 'text')


# ===== 批量预加载上下文（contextvars，线程/协程安全）=====
# 由 data_api 等批量接口在开头设置、结尾清除。
# 为 None 时回退到单条查询（保持原有逻辑），非 None 时直接用集合判断，避免 N+1。
_current_uid_ctx: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    'current_uid', default=None
)
_bulk_liked_voice_ids_ctx: contextvars.ContextVar[Optional[Set[str]]] = contextvars.ContextVar(
    'bulk_liked_voice_ids', default=None
)
_bulk_liked_comment_ids_ctx: contextvars.ContextVar[Optional[Set[str]]] = contextvars.ContextVar(
    'bulk_liked_comment_ids', default=None
)
_bulk_voted_idea_ids_ctx: contextvars.ContextVar[Optional[Set[str]]] = contextvars.ContextVar(
    'bulk_voted_idea_ids', default=None
)
# user 批量预加载缓存：{uid: nickname}，避免序列化时逐条 db.get(User) 造成 N+1
_bulk_user_map_ctx: contextvars.ContextVar[Optional[dict]] = contextvars.ContextVar(
    'bulk_user_map', default=None
)
# feedback 最新回复批量预加载缓存：{feedback_id: FeedbackReply}，避免逐条查询
_bulk_feedback_reply_map_ctx: contextvars.ContextVar[Optional[dict]] = contextvars.ContextVar(
    'bulk_feedback_reply_map', default=None
)


def get_current_uid_safe() -> Optional[str]:
    """从上下文获取当前用户 ID（失败返回 None）。"""
    return _current_uid_ctx.get()


def set_current_uid(uid: Optional[str]) -> None:
    """设置当前用户 ID 到上下文。"""
    _current_uid_ctx.set(uid)


def set_bulk_cache(
    liked_voice_ids: Optional[Set[str]],
    liked_comment_ids: Optional[Set[str]],
    voted_idea_ids: Optional[Set[str]],
    user_map: Optional[dict] = None,
    feedback_reply_map: Optional[dict] = None,
) -> None:
    """设置批量预加载缓存（避免 N+1 查询）。"""
    _bulk_liked_voice_ids_ctx.set(liked_voice_ids)
    _bulk_liked_comment_ids_ctx.set(liked_comment_ids)
    _bulk_voted_idea_ids_ctx.set(voted_idea_ids)
    _bulk_user_map_ctx.set(user_map)
    _bulk_feedback_reply_map_ctx.set(feedback_reply_map)


def clear_bulk_cache() -> None:
    """清除批量预加载缓存，恢复单条查询回退逻辑。"""
    _bulk_liked_voice_ids_ctx.set(None)
    _bulk_liked_comment_ids_ctx.set(None)
    _bulk_voted_idea_ids_ctx.set(None)
    _bulk_user_map_ctx.set(None)
    _bulk_feedback_reply_map_ctx.set(None)


def get_user_nickname(db, uid: str) -> Optional[str]:
    """获取用户昵称（优先用批量缓存，回退到 db.get）。"""
    if not uid:
        return None
    bulk = _bulk_user_map_ctx.get()
    if bulk is not None:
        return bulk.get(uid)
    from app.models.user import User
    u = db.get(User, uid)
    return u.nickname if u else None


def get_feedback_latest_reply(db, feedback_id: str):
    """获取反馈的最新回复（优先用批量缓存，回退到单条查询）。"""
    if not feedback_id:
        return None
    bulk = _bulk_feedback_reply_map_ctx.get()
    if bulk is not None:
        return bulk.get(feedback_id)
    from app.models.feedback import FeedbackReply
    return (
        db.query(FeedbackReply)
        .filter_by(feedback_id=feedback_id)
        .order_by(FeedbackReply.created_at.desc())
        .first()
    )


def is_liked_voice(db, voice_id: str) -> bool:
    """检查当前用户是否已点赞该留言（优先用批量缓存）。"""
    bulk = _bulk_liked_voice_ids_ctx.get()
    if bulk is not None:
        return voice_id in bulk
    uid = get_current_uid_safe()
    if not uid:
        return False
    from app.models.voice import VoiceLike
    return db.query(VoiceLike).filter_by(voice_id=voice_id, user_id=uid).first() is not None


def is_voted_idea(db, idea_id: str) -> bool:
    """检查当前用户是否已投票该创意（优先用批量缓存）。"""
    bulk = _bulk_voted_idea_ids_ctx.get()
    if bulk is not None:
        return idea_id in bulk
    uid = get_current_uid_safe()
    if not uid:
        return False
    from app.models.idea import IdeaVote
    return db.query(IdeaVote).filter_by(idea_id=idea_id, user_id=uid).first() is not None


def is_liked_comment(db, comment_id: str) -> bool:
    """检查当前用户是否已点赞该评论（优先用批量缓存）。"""
    bulk = _bulk_liked_comment_ids_ctx.get()
    if bulk is not None:
        return comment_id in bulk
    uid = get_current_uid_safe()
    if not uid:
        return False
    from app.models.comment import CommentLike
    return (
        db.query(CommentLike).filter_by(comment_id=comment_id, user_id=uid).first()
        is not None
    )
