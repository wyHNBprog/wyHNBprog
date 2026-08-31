"""后台定时任务：清理过期 Token 黑名单。

使用后台守护线程实现，无需额外依赖（不引入 APScheduler）。
- 每 24 小时执行一次清理
- Token 黑名单：删除已过期的黑名单记录
"""
import threading
import time
import logging
from datetime import datetime

from app.database import SessionLocal
from app.models.token_blacklist import TokenBlacklist

logger = logging.getLogger(__name__)

# 清理间隔（秒）
CLEANUP_INTERVAL = 86400  # 24 小时


def cleanup_expired_tokens():
    """清理已过期的 Token 黑名单记录。"""
    db = SessionLocal()
    try:
        now = datetime.utcnow()
        expired = db.query(TokenBlacklist).filter(
            TokenBlacklist.expires_at < now,
        ).all()
        count = len(expired)
        for t in expired:
            db.delete(t)
        db.commit()
        if count > 0:
            logger.info('[定时清理] 已清理 %d 条过期 Token 黑名单记录', count)
        return count
    except Exception as e:
        db.rollback()
        logger.warning('[定时清理] Token 黑名单清理失败: %s', e)
        return 0
    finally:
        db.close()


def _cleanup_loop():
    """后台清理循环（守护线程）。"""
    # 启动后先等待 60 秒再首次执行（避免与应用启动竞争资源）
    time.sleep(60)
    while True:
        try:
            cleanup_expired_tokens()
        except Exception as e:
            logger.warning('[定时清理] 清理任务异常: %s', e)
        time.sleep(CLEANUP_INTERVAL)


def start_cleanup_scheduler():
    """启动后台清理守护线程。"""
    thread = threading.Thread(target=_cleanup_loop, daemon=True, name='cleanup-scheduler')
    thread.start()
    logger.info('[定时清理] 后台清理线程已启动（间隔=%d 秒）', CLEANUP_INTERVAL)
