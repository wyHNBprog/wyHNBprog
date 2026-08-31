"""管理员数据看板路由：统计 + 用户积分排行榜。

对齐 Flask 版逻辑：
- 排行榜取 top 20
- 积分公式：留言10/条 + 评论2/条 + 点赞1/个 + 被点赞2/个 + 金点子20/条 + 被献花20/条 + 被献星星50/条
- 内容数据只统计已通过（approved）的，待审/驳回不计入
- 删除的内容自动从统计中移除并扣分（硬删除）
- 增加私信未读数统计
- 增加反馈总数统计
- Redis 缓存统计结果（TTL 30s），内容变更时自动失效
"""
from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.deps import get_current_admin
from app.models.user import User
from app.models.voice import Voice, VoiceLike
from app.models.comment import Comment, CommentLike
from app.models.idea import Idea
from app.models.feedback import Feedback
from app.models.message import Message
from app.services.points import INITIAL_POINTS
from app.services.redis_client import cache_get, cache_set, cache_delete

router = APIRouter()

# 已通过的内容状态
IDEA_PUBLISHED_STATUSES = ['approved', 'voting']


@router.get('/api/admin/stats')
def admin_stats(
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """管理员数据看板统计。

    返回：
    - voices: 留言统计（total 只含已通过，all_total 含所有状态）
    - ideas: 金点子统计（total 只含已发布，all_total 含所有状态）
    - comments: 评论统计（total 只含已通过，all_total 含所有状态）
    - feedbacks: 反馈总数
    - messages: 未读私信数
    - users: 用户统计（total / active，active 只统计有已通过内容的用户）
    - engagement: 互动统计（只统计已通过内容的互动）
    - ranking: 用户积分排行榜（top 20，只统计已通过内容）
    """
    # Try cache
    cached = cache_get('cache:admin_stats')
    if cached:
        # 缓存命中：按当前请求者动态计算 isMe，避免多管理员看板互相污染
        for r in cached.get('ranking', []):
            r['isMe'] = r.get('id') == admin.id
        return cached

    # 留言统计（按状态分组计数）
    voice_rows = db.query(Voice.status, func.count(Voice.id)).group_by(Voice.status).all()
    voice_map = {s: c for s, c in voice_rows}
    voices = {
        'total': voice_map.get('approved', 0),           # 只统计已通过
        'approved': voice_map.get('approved', 0),
        'pending': voice_map.get('pending', 0),
        'rejected': voice_map.get('rejected', 0),
        'all_total': sum(voice_map.values()),             # 所有状态总和（用于状态分布图）
    }

    # 金点子统计
    idea_rows = db.query(Idea.status, func.count(Idea.id)).group_by(Idea.status).all()
    idea_map = {s: c for s, c in idea_rows}
    idea_published = idea_map.get('voting', 0) + idea_map.get('approved', 0)
    ideas = {
        'total': idea_published,                          # 只统计已发布（approved + voting）
        'voting': idea_published,
        'pending': idea_map.get('pending', 0),
        'rejected': idea_map.get('rejected', 0),
        'all_total': sum(idea_map.values()),              # 所有状态总和
    }

    # 评论统计
    comment_rows = db.query(Comment.status, func.count(Comment.id)).group_by(Comment.status).all()
    comment_map = {s: c for s, c in comment_rows}
    comments = {
        'total': comment_map.get('approved', 0),          # 只统计已通过
        'approved': comment_map.get('approved', 0),
        'pending': comment_map.get('pending', 0),
        'rejected': comment_map.get('rejected', 0),
        'all_total': sum(comment_map.values()),           # 所有状态总和
    }

    # 反馈总数
    feedbacks_total = db.query(Feedback).count()

    # 未读私信数
    messages_unread = db.query(Message).filter_by(status='unread').count()

    # 用户统计（active：发过已通过内容的用户数）
    users_total = db.query(User).count()
    active_ids = set()
    for row in db.query(Voice.user_id).filter(Voice.status == 'approved').distinct():
        if row[0]:
            active_ids.add(row[0])
    for row in db.query(Comment.user_id).filter(Comment.status == 'approved').distinct():
        if row[0]:
            active_ids.add(row[0])
    for row in db.query(Idea.user_id).filter(Idea.status.in_(IDEA_PUBLISHED_STATUSES)).distinct():
        if row[0]:
            active_ids.add(row[0])
    for row in db.query(Feedback.user_id).distinct():
        if row[0]:
            active_ids.add(row[0])
    users = {
        'total': users_total,
        'active': len(active_ids),
    }

    # 互动统计（只统计已通过内容的互动）
    voice_likes = db.query(func.coalesce(func.sum(Voice.like_count), 0)).filter(Voice.status == 'approved').scalar() or 0
    comment_likes = db.query(func.coalesce(func.sum(Comment.like_count), 0)).filter(Comment.status == 'approved').scalar() or 0
    total_votes = db.query(func.coalesce(func.sum(Idea.vote_count), 0)).filter(Idea.status.in_(IDEA_PUBLISHED_STATUSES)).scalar() or 0
    total_flowers = db.query(func.coalesce(func.sum(Idea.flower_count), 0)).filter(Idea.status.in_(IDEA_PUBLISHED_STATUSES)).scalar() or 0
    total_fireworks = db.query(func.count(Idea.id)).filter(
        Idea.has_firework == True,  # noqa: E712
        Idea.status.in_(IDEA_PUBLISHED_STATUSES),
    ).scalar() or 0
    engagement = {
        'totalLikes': voice_likes + comment_likes,
        'totalVotes': total_votes,
        'totalFlowers': total_flowers,
        'totalFireworks': total_fireworks,
    }

    # 用户积分排行榜（只统计已登录用户，且只统计已通过内容）
    # 积分公式：初始10 + 留言10 + 评论2 + 点赞1 + 被点赞2 + 金点子20 + 被献花20 + 被献星星50
    # 只统计已登录用户（wecom_user_id 非空），未登录/匿名用户不进入排行榜
    # 优化：用聚合查询一次性统计所有用户数据，避免 N+1
    voice_stats = db.query(
        Voice.user_id.label('uid'),
        func.count(Voice.id).label('cnt'),
        func.coalesce(func.sum(Voice.like_count), 0).label('likes'),
    ).filter(Voice.status == 'approved').group_by(Voice.user_id).all()
    voice_stat_map = {r.uid: {'count': r.cnt, 'likes': int(r.likes or 0)} for r in voice_stats}

    idea_stats = db.query(
        Idea.user_id.label('uid'),
        func.count(Idea.id).label('cnt'),
        func.coalesce(func.sum(Idea.flower_count), 0).label('flowers'),
        func.coalesce(func.sum(Idea.firework_count), 0).label('fireworks'),
    ).filter(Idea.status.in_(IDEA_PUBLISHED_STATUSES)).group_by(Idea.user_id).all()
    idea_stat_map = {r.uid: {'count': r.cnt, 'flowers': int(r.flowers or 0), 'fireworks': int(r.fireworks or 0)} for r in idea_stats}

    # 评论数统计（按用户分组，只统计已通过）
    comment_stats = db.query(
        Comment.user_id.label('uid'),
        func.count(Comment.id).label('cnt'),
        func.coalesce(func.sum(Comment.like_count), 0).label('likes'),
    ).filter(Comment.status == 'approved').group_by(Comment.user_id).all()
    comment_stat_map = {r.uid: {'count': r.cnt, 'likes': int(r.likes or 0)} for r in comment_stats}

    # 用户给出的点赞数（只统计对已通过内容的点赞）
    voice_like_given = db.query(
        VoiceLike.user_id.label('uid'),
        func.count(VoiceLike.id).label('cnt'),
    ).join(Voice, VoiceLike.voice_id == Voice.id).filter(
        Voice.status == 'approved'
    ).group_by(VoiceLike.user_id).all()
    comment_like_given = db.query(
        CommentLike.user_id.label('uid'),
        func.count(CommentLike.id).label('cnt'),
    ).join(Comment, CommentLike.comment_id == Comment.id).filter(
        Comment.status == 'approved'
    ).group_by(CommentLike.user_id).all()
    likes_given_map = {}
    for r in voice_like_given:
        likes_given_map[r.uid] = likes_given_map.get(r.uid, 0) + r.cnt
    for r in comment_like_given:
        likes_given_map[r.uid] = likes_given_map.get(r.uid, 0) + r.cnt

    ranking = []
    for u in db.query(User).filter(User.wecom_user_id.isnot(None)).all():
        vs = voice_stat_map.get(u.id, {'count': 0, 'likes': 0})
        ic = idea_stat_map.get(u.id, {'count': 0, 'flowers': 0, 'fireworks': 0})
        cs = comment_stat_map.get(u.id, {'count': 0, 'likes': 0})
        likes_given = likes_given_map.get(u.id, 0)
        likes_received = vs['likes'] + cs['likes']
        flower_count = ic['flowers']
        firework_count = ic['fireworks']
        # 积分公式：初始10 + 留言10 + 评论2 + 点赞1 + 被点赞2 + 金点子20 + 被献花20 + 被献星星50
        score = INITIAL_POINTS + vs['count'] * 10 + cs['count'] * 2 + likes_given * 1 + likes_received * 2 + ic['count'] * 20 + flower_count * 20 + firework_count * 50
        ranking.append({
            'id': u.id,
            'nickname': u.nickname,
            'avatar': u.avatar,
            'department': u.department or '',
            'role': u.role or 'user',
            'score': score,
            'voices': vs['count'],
            'comments': cs['count'],
            'ideas': ic['count'],
            'likesGiven': likes_given,
            'likesReceived': likes_received,
            'flowers': flower_count,
            'stars': firework_count,
            # isMe 不在此处设置（避免被全局缓存污染多管理员看板），返回前按请求者动态计算
        })
    ranking.sort(key=lambda x: x['score'], reverse=True)
    # 取 top 20
    ranking = ranking[:20]

    result = {
        'voices': voices,
        'ideas': ideas,
        'comments': comments,
        'feedbacks': feedbacks_total,
        'messages': messages_unread,
        'users': users,
        'engagement': engagement,
        'ranking': ranking,
    }
    cache_set('cache:admin_stats', result, settings.CACHE_TTL_STATS)
    # 按当前请求者动态计算 isMe（不写入缓存，避免多管理员污染）
    for r in result.get('ranking', []):
        r['isMe'] = r.get('id') == admin.id
    return result
