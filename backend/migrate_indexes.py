"""
数据库索引迁移脚本（MySQL 兼容）
为现有表添加缺失的索引，提升查询性能。
运行方式: python migrate_indexes.py
"""
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal, engine
from sqlalchemy import text


# 所有需要创建的索引（MySQL 不支持 CREATE INDEX IF NOT EXISTS，用 ALTER TABLE + try/except）
INDEXES = [
    # voices 表
    ('voices', 'ix_voices_user_id', 'ALTER TABLE voices ADD INDEX ix_voices_user_id (user_id)'),
    ('voices', 'ix_voices_status', 'ALTER TABLE voices ADD INDEX ix_voices_status (status)'),
    ('voices', 'ix_voices_created_at', 'ALTER TABLE voices ADD INDEX ix_voices_created_at (created_at)'),

    # voice_likes 表
    ('voice_likes', 'ix_voice_likes_voice_id', 'ALTER TABLE voice_likes ADD INDEX ix_voice_likes_voice_id (voice_id)'),
    ('voice_likes', 'ix_voice_likes_user_id', 'ALTER TABLE voice_likes ADD INDEX ix_voice_likes_user_id (user_id)'),

    # voice_tags 表
    ('voice_tags', 'ix_voice_tags_voice_id', 'ALTER TABLE voice_tags ADD INDEX ix_voice_tags_voice_id (voice_id)'),

    # comments 表
    ('comments', 'ix_comments_voice_id', 'ALTER TABLE comments ADD INDEX ix_comments_voice_id (voice_id)'),
    ('comments', 'ix_comments_user_id', 'ALTER TABLE comments ADD INDEX ix_comments_user_id (user_id)'),
    ('comments', 'ix_comments_status', 'ALTER TABLE comments ADD INDEX ix_comments_status (status)'),
    ('comments', 'ix_comments_created_at', 'ALTER TABLE comments ADD INDEX ix_comments_created_at (created_at)'),

    # comment_likes 表
    ('comment_likes', 'ix_comment_likes_comment_id', 'ALTER TABLE comment_likes ADD INDEX ix_comment_likes_comment_id (comment_id)'),
    ('comment_likes', 'ix_comment_likes_user_id', 'ALTER TABLE comment_likes ADD INDEX ix_comment_likes_user_id (user_id)'),

    # ideas 表
    ('ideas', 'ix_ideas_user_id', 'ALTER TABLE ideas ADD INDEX ix_ideas_user_id (user_id)'),
    ('ideas', 'ix_ideas_status', 'ALTER TABLE ideas ADD INDEX ix_ideas_status (status)'),
    ('ideas', 'ix_ideas_created_at', 'ALTER TABLE ideas ADD INDEX ix_ideas_created_at (created_at)'),

    # idea_votes 表
    ('idea_votes', 'ix_idea_votes_idea_id', 'ALTER TABLE idea_votes ADD INDEX ix_idea_votes_idea_id (idea_id)'),
    ('idea_votes', 'ix_idea_votes_user_id', 'ALTER TABLE idea_votes ADD INDEX ix_idea_votes_user_id (user_id)'),

    # feedbacks 表
    ('feedbacks', 'ix_feedbacks_user_id', 'ALTER TABLE feedbacks ADD INDEX ix_feedbacks_user_id (user_id)'),
    ('feedbacks', 'ix_feedbacks_status', 'ALTER TABLE feedbacks ADD INDEX ix_feedbacks_status (status)'),
    ('feedbacks', 'ix_feedbacks_created_at', 'ALTER TABLE feedbacks ADD INDEX ix_feedbacks_created_at (created_at)'),

    # feedback_replies 表
    ('feedback_replies', 'ix_feedback_replies_feedback_id', 'ALTER TABLE feedback_replies ADD INDEX ix_feedback_replies_feedback_id (feedback_id)'),

    # messages 表
    ('messages', 'ix_messages_user_id', 'ALTER TABLE messages ADD INDEX ix_messages_user_id (user_id)'),
    ('messages', 'ix_messages_status', 'ALTER TABLE messages ADD INDEX ix_messages_status (status)'),

    # notifications 表
    ('notifications', 'ix_notifications_user_id', 'ALTER TABLE notifications ADD INDEX ix_notifications_user_id (user_id)'),
    ('notifications', 'ix_notifications_is_read', 'ALTER TABLE notifications ADD INDEX ix_notifications_is_read (is_read)'),
    ('notifications', 'ix_notifications_created_at', 'ALTER TABLE notifications ADD INDEX ix_notifications_created_at (created_at)'),

    # users 表
    ('users', 'ix_users_role', 'ALTER TABLE users ADD INDEX ix_users_role (role)'),
    ('users', 'ix_users_created_at', 'ALTER TABLE users ADD INDEX ix_users_created_at (created_at)'),

    # token_blacklist 表（JWT 撤销机制）
    ('token_blacklist', 'ix_token_blacklist_jti', 'ALTER TABLE token_blacklist ADD INDEX ix_token_blacklist_jti (jti)'),
    ('token_blacklist', 'ix_token_blacklist_expires_at', 'ALTER TABLE token_blacklist ADD INDEX ix_token_blacklist_expires_at (expires_at)'),
]


def run_migration():
    """执行索引迁移。"""
    db = SessionLocal()
    try:
        success_count = 0
        skip_count = 0
        for table, index_name, sql in INDEXES:
            try:
                db.execute(text(sql))
                db.commit()
                success_count += 1
                print(f'  [OK] {index_name} on {table}')
            except Exception as e:
                db.rollback()
                # 索引已存在（Duplicate key name）或其他非致命错误，跳过
                skip_count += 1
                err_msg = str(e)[:80]
                print(f'  [SKIP] {index_name}: {err_msg}')

        print(f'\n迁移完成: {success_count} 个索引创建成功, {skip_count} 个跳过')
    finally:
        db.close()


if __name__ == '__main__':
    print('=' * 60)
    print('VoiceHub 数据库索引迁移（MySQL 兼容）')
    print('=' * 60)
    run_migration()
