"""用户积分服务：初始积分 + 动态内容积分。

积分规则（与数据看板排行榜保持一致）：
- 初始积分：INITIAL_POINTS（10 分），登录即得 / 已登录用户均拥有
- 动态积分：留言10 + 评论2 + 点赞1 + 被点赞2 + 金点子20 + 被献花20 + 被献星星50
- 实际部署中请以本模块为准，避免与 dashboard 聚合逻辑重复定义
"""
from sqlalchemy import func

# 登录即得的初始积分
INITIAL_POINTS = 10

# 动态积分系数
POINTS_VOICE = 10      # 已通过留言
POINTS_COMMENT = 2     # 已通过评论
POINTS_LIKE_GIVEN = 1  # 给他人点赞
POINTS_LIKE_RECEIVED = 2  # 被点赞
POINTS_IDEA = 20       # 已发布金点子
POINTS_FLOWER = 20     # 被献花
POINTS_STAR = 50       # 被献星星


def calc_user_dynamic_score(db, user_id: str) -> int:
    """计算单个用户的动态内容积分（不含初始积分）。

    只统计已通过/已发布的内容，与数据看板排行榜口径一致。
    """
    from app.models.voice import Voice, VoiceLike
    from app.models.comment import Comment, CommentLike
    from app.models.idea import Idea

    # 已通过留言数及被点赞数
    voice = (
        db.query(
            func.count(Voice.id),
            func.coalesce(func.sum(Voice.like_count), 0),
        )
        .filter(Voice.user_id == user_id, Voice.status == 'approved')
        .first()
    )
    voice_count = int(voice[0] or 0)
    voice_likes = int(voice[1] or 0)

    # 已通过评论数及被点赞数
    comment = (
        db.query(
            func.count(Comment.id),
            func.coalesce(func.sum(Comment.like_count), 0),
        )
        .filter(Comment.user_id == user_id, Comment.status == 'approved')
        .first()
    )
    comment_count = int(comment[0] or 0)
    comment_likes = int(comment[1] or 0)

    # 已发布金点子数、被献花数、被献星星数
    idea = (
        db.query(
            func.count(Idea.id),
            func.coalesce(func.sum(Idea.flower_count), 0),
            func.coalesce(func.sum(Idea.firework_count), 0),
        )
        .filter(
            Idea.user_id == user_id,
            Idea.status.in_(['approved', 'voting']),
        )
        .first()
    )
    idea_count = int(idea[0] or 0)
    flower_count = int(idea[1] or 0)
    star_count = int(idea[2] or 0)

    # 给出的点赞数（仅统计对已通过内容的点赞）
    likes_given = 0
    for row in (
        db.query(VoiceLike.user_id, func.count(VoiceLike.id))
        .join(Voice, VoiceLike.voice_id == Voice.id)
        .filter(VoiceLike.user_id == user_id, Voice.status == 'approved')
        .group_by(VoiceLike.user_id)
        .all()
    ):
        likes_given += int(row[1] or 0)
    for row in (
        db.query(CommentLike.user_id, func.count(CommentLike.id))
        .join(Comment, CommentLike.comment_id == Comment.id)
        .filter(CommentLike.user_id == user_id, Comment.status == 'approved')
        .group_by(CommentLike.user_id)
        .all()
    ):
        likes_given += int(row[1] or 0)

    score = (
        voice_count * POINTS_VOICE
        + comment_count * POINTS_COMMENT
        + likes_given * POINTS_LIKE_GIVEN
        + (voice_likes + comment_likes) * POINTS_LIKE_RECEIVED
        + idea_count * POINTS_IDEA
        + flower_count * POINTS_FLOWER
        + star_count * POINTS_STAR
    )
    return score


def calc_user_total_points(db, user_id: str) -> int:
    """计算用户总积分 = 初始积分 + 动态积分。"""
    return INITIAL_POINTS + calc_user_dynamic_score(db, user_id)