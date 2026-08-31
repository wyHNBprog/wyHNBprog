"""数据路由：全量数据 / 按需数据接口 / 版本号。

包含权限过滤逻辑：非管理员只看 approved + 自己的 pending/rejected。
包含批量预加载优化：避免 N+1 查询。
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.deps import get_user_with_context_required
from app.models.user import User
from app.models.voice import Voice, VoiceLike
from app.models.comment import Comment, CommentLike
from app.models.idea import Idea, IdeaVote
from app.models.feedback import Feedback, FeedbackReply
from app.models.message import Message
from app.models.announce import Announce
from app.models.notification import Notification
from app.serialization import (
    voice_to_dict,
    idea_to_dict,
    feedback_to_dict,
    message_to_dict,
    announce_to_dict,
    notification_to_dict,
)
from app.utils import set_bulk_cache, clear_bulk_cache

router = APIRouter()


def _is_admin(user: User) -> bool:
    """判断用户是否为管理员。"""
    return bool(user and (user.is_admin or user.role in ('super_admin', 'admin')))


@router.get('/api/data')
def api_data(
    user: User = Depends(get_user_with_context_required),
    db: Session = Depends(get_db),
):
    """全量数据接口（含权限过滤）。

    非管理员只能看到：
    - approved 的心声（加上自己的 pending/rejected）
    - voting 的金点子（加上自己的 pending/rejected）
    - replied 的反馈（加上自己的 pending）
    - 自己的私信和通知
    """
    show_real = _is_admin(user)
    uid = user.id

    # 批量预加载当前用户的点赞/投票状态，避免序列化时逐条查询（N+1）
    liked_voice_ids = set(r.voice_id for r in db.query(VoiceLike).filter_by(user_id=uid).all())
    liked_comment_ids = set(r.comment_id for r in db.query(CommentLike).filter_by(user_id=uid).all())
    voted_idea_ids = set(r.idea_id for r in db.query(IdeaVote).filter_by(user_id=uid).all())

    # ===== 预查询所有可见数据（用于批量收集 user_id 和 feedback_id）=====
    all_voices = (
        db.query(Voice)
        .options(joinedload(Voice.comments), joinedload(Voice.tags))
        .order_by(Voice.created_at.desc())
        .all()
    )
    if show_real:
        # 管理员视图：过滤已清除审核记录的 pending/rejected 项
        visible_voices = [
            v for v in all_voices
            if not (v.review_cleared and v.status in ('pending', 'rejected'))
        ]
    else:
        visible_voices = [v for v in all_voices if v.status == 'approved' or v.user_id == uid]

    all_ideas = db.query(Idea).order_by(Idea.created_at.desc()).all()
    visible_ideas = [
        i for i in all_ideas
        if (show_real or not (i.status in ('pending', 'rejected') and i.user_id != uid))
        and not (i.review_cleared and i.status in ('pending', 'rejected'))
    ]

    if show_real:
        visible_feedbacks = db.query(Feedback).order_by(Feedback.created_at.desc()).all()
    else:
        # 普通用户只看自己的反馈（避免越权查看他人已回复的反馈内容，与 /api/feedbacks/list 一致）
        visible_feedbacks = (
            db.query(Feedback)
            .filter(Feedback.user_id == uid)
            .order_by(Feedback.created_at.desc())
            .all()
        )

    if show_real:
        visible_messages = db.query(Message).order_by(Message.created_at.desc()).all()
    else:
        visible_messages = (
            db.query(Message).filter_by(user_id=uid).order_by(Message.created_at.desc()).all()
        )

    # 通知：所有用户（包括管理员）都只看自己的通知
    visible_notifications = (
        db.query(Notification)
        .filter_by(user_id=uid)
        .order_by(Notification.created_at.desc())
        .all()
    )

    # ===== 批量预加载所有 user（避免序列化时逐条 db.get(User) 造成 N+1）=====
    all_user_ids = set()
    for v in visible_voices:
        if v.user_id:
            all_user_ids.add(v.user_id)
        for c in (v.comments or []):
            if c.user_id:
                all_user_ids.add(c.user_id)
    for i in visible_ideas:
        if i.user_id:
            all_user_ids.add(i.user_id)
    for f in visible_feedbacks:
        if f.user_id:
            all_user_ids.add(f.user_id)
    for m in visible_messages:
        if m.user_id:
            all_user_ids.add(m.user_id)
    user_map = {}
    if all_user_ids:
        user_map = {u.id: u.nickname for u in db.query(User).filter(User.id.in_(all_user_ids)).all()}

    # ===== 批量预加载 feedback 最新回复（避免逐条查询 N+1）=====
    feedback_reply_map = {}
    if visible_feedbacks:
        fb_ids = [f.id for f in visible_feedbacks]
        # 一次性查询所有相关回复，按 feedback_id 分组取最新
        all_replies = (
            db.query(FeedbackReply)
            .filter(FeedbackReply.feedback_id.in_(fb_ids))
            .order_by(FeedbackReply.feedback_id, FeedbackReply.created_at.desc())
            .all()
        )
        seen_fb = set()
        for r in all_replies:
            if r.feedback_id not in seen_fb:
                feedback_reply_map[r.feedback_id] = r
                seen_fb.add(r.feedback_id)

    set_bulk_cache(
        liked_voice_ids,
        liked_comment_ids,
        voted_idea_ids,
        user_map=user_map,
        feedback_reply_map=feedback_reply_map,
    )

    try:
        voices = [voice_to_dict(db, v, include_real_name=show_real) for v in visible_voices]

        ideas = {'voting': [], 'adopted': [], 'completed': []}
        for i in visible_ideas:
            d = idea_to_dict(db, i, include_real_name=show_real)
            # 所有可见金点子统一放入 voting（已取消 adopted/completed 状态）
            ideas['voting'].append(d)

        return {
            'voices': voices,
            'ideas': ideas,
            'feedbacks': [feedback_to_dict(db, f, include_real_name=show_real) for f in visible_feedbacks],
            'messages': [message_to_dict(db, m, include_real_name=show_real) for m in visible_messages],
            'announcements': [
                announce_to_dict(a)
                for a in db.query(Announce)
                .order_by(Announce.is_pinned.desc(), Announce.created_at.desc())
                .all()
            ],
            'notifications': [notification_to_dict(n) for n in visible_notifications],
            'dataVersion': 2,
        }
    finally:
        # 清除批量缓存，恢复单条查询回退逻辑
        clear_bulk_cache()


@router.get('/api/version')
def api_version():
    """数据版本号。"""
    return {'version': 3}


# ========== 按需数据接口（拆分 /api/data，减少首屏负载）==========

@router.get('/api/voices/list')
def voices_list(
    user: User = Depends(get_user_with_context_required),
    db: Session = Depends(get_db),
):
    """心声列表（按需加载）。"""
    show_real = _is_admin(user)
    uid = user.id

    liked_voice_ids = set(r.voice_id for r in db.query(VoiceLike).filter_by(user_id=uid).all())
    liked_comment_ids = set(r.comment_id for r in db.query(CommentLike).filter_by(user_id=uid).all())
    set_bulk_cache(liked_voice_ids, liked_comment_ids, None)
    try:
        all_voices = (
            db.query(Voice)
            .options(joinedload(Voice.comments), joinedload(Voice.tags))
            .order_by(Voice.created_at.desc())
            .all()
        )
        if show_real:
            # 管理员视图：过滤已清除审核记录的 pending/rejected 项
            visible = [v for v in all_voices if not (v.review_cleared and v.status in ('pending', 'rejected'))]
        else:
            visible = [v for v in all_voices if v.status == 'approved' or v.user_id == uid]
        return {'voices': [voice_to_dict(db, v, include_real_name=show_real) for v in visible]}
    finally:
        clear_bulk_cache()


@router.get('/api/ideas/list')
def ideas_list(
    user: User = Depends(get_user_with_context_required),
    db: Session = Depends(get_db),
):
    """金点子列表（按需加载）。"""
    show_real = _is_admin(user)
    uid = user.id

    voted_idea_ids = set(r.idea_id for r in db.query(IdeaVote).filter_by(user_id=uid).all())
    set_bulk_cache(None, None, voted_idea_ids)
    try:
        ideas = {'voting': [], 'adopted': [], 'completed': []}
        for i in db.query(Idea).order_by(Idea.created_at.desc()).all():
            if not show_real and i.status in ('pending', 'rejected') and i.user_id != uid:
                continue
            # 过滤已清除审核记录的 pending/rejected 项
            if i.review_cleared and i.status in ('pending', 'rejected'):
                continue
            d = idea_to_dict(db, i, include_real_name=show_real)
            ideas['voting'].append(d)
        return {'ideas': ideas}
    finally:
        clear_bulk_cache()


@router.get('/api/announcements/list')
def announcements_list(
    user: User = Depends(get_user_with_context_required),
    db: Session = Depends(get_db),
):
    """公告列表（按需加载）。"""
    return {
        'announcements': [
            announce_to_dict(a)
            for a in db.query(Announce)
            .order_by(Announce.is_pinned.desc(), Announce.created_at.desc())
            .all()
        ]
    }


@router.get('/api/feedbacks/list')
def feedbacks_list(
    user: User = Depends(get_user_with_context_required),
    db: Session = Depends(get_db),
):
    """反馈列表（按需加载）。"""
    show_real = _is_admin(user)
    uid = user.id
    all_fbs = db.query(Feedback).order_by(Feedback.created_at.desc()).all()
    if show_real:
        visible = all_fbs
    else:
        # 普通用户只看自己的反馈（避免越权查看他人已回复的反馈内容）
        visible = [f for f in all_fbs if f.user_id == uid]
    return {'feedbacks': [feedback_to_dict(db, f, include_real_name=show_real) for f in visible]}
