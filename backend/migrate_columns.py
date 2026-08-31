"""
数据库列迁移脚本（MySQL 兼容）
为现有表添加新增的列：review_cleared, has_firework, firework_count。
运行方式: python migrate_columns.py
"""
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal
from sqlalchemy import text


# 所有需要添加的列 (table, column_name, column_def, index_sql)
COLUMNS = [
    # voices 表：添加 review_cleared
    ('voices', 'review_cleared',
     'ALTER TABLE voices ADD COLUMN review_cleared TINYINT(1) DEFAULT 0',
     'ALTER TABLE voices ADD INDEX ix_voices_review_cleared (review_cleared)'),

    # ideas 表：添加 review_cleared, has_firework, firework_count
    ('ideas', 'review_cleared',
     'ALTER TABLE ideas ADD COLUMN review_cleared TINYINT(1) DEFAULT 0',
     'ALTER TABLE ideas ADD INDEX ix_ideas_review_cleared (review_cleared)'),
    ('ideas', 'has_firework',
     'ALTER TABLE ideas ADD COLUMN has_firework TINYINT(1) DEFAULT 0',
     None),
    ('ideas', 'firework_count',
     'ALTER TABLE ideas ADD COLUMN firework_count INT DEFAULT 0',
     None),

    # comments 表：添加 review_cleared
    ('comments', 'review_cleared',
     'ALTER TABLE comments ADD COLUMN review_cleared TINYINT(1) DEFAULT 0',
     'ALTER TABLE comments ADD INDEX ix_comments_review_cleared (review_cleared)'),
]


def run_migration():
    """执行列迁移。"""
    db = SessionLocal()
    try:
        success_count = 0
        skip_count = 0
        for table, column_name, column_sql, index_sql in COLUMNS:
            # 添加列
            try:
                db.execute(text(column_sql))
                db.commit()
                success_count += 1
                print(f'  [OK] {table}.{column_name} 列已添加')
            except Exception as e:
                db.rollback()
                # 列已存在（Duplicate column name）或其他非致命错误，跳过
                skip_count += 1
                err_msg = str(e)[:80]
                print(f'  [SKIP] {table}.{column_name}: {err_msg}')

            # 添加索引
            if index_sql:
                try:
                    db.execute(text(index_sql))
                    db.commit()
                    print(f'  [OK] {table}.{column_name} 索引已创建')
                except Exception as e:
                    db.rollback()
                    err_msg = str(e)[:80]
                    print(f'  [SKIP] {table}.{column_name} 索引: {err_msg}')

        print(f'\n迁移完成: {success_count} 个列添加成功, {skip_count} 个跳过')
    finally:
        db.close()


if __name__ == '__main__':
    print('=' * 60)
    print('VoiceHub 数据库列迁移（MySQL 兼容）')
    print('=' * 60)
    run_migration()
