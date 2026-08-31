"""Redis 客户端封装：缓存 + 限流。

多 worker（uvicorn/gunicorn）共享缓存与限流计数。
Redis 不可用时自动降级到进程内缓存（threading.Lock 保护），不影响正常业务。

主要功能：
- 缓存读写：cache_get / cache_set / cache_delete
- 限流计数：rate_limit_check / rate_limit_key
- init_redis() 应在应用启动时调用
"""
import json
import logging
import threading
import time

from app.config import settings

logger = logging.getLogger(__name__)

# 进程内缓存（Redis 不可用时的降级方案）
_local_cache = {}
_local_lock = threading.Lock()

# 进程内限流计数器（Redis 不可用时的降级方案）
_local_rate_limits = {}

_redis_client = None
_redis_available = False


def init_redis():
    """初始化 Redis 连接，失败时降级到进程内缓存。

    应在应用启动时调用（FastAPI lifespan / startup event）。
    读取 app.config.settings.REDIS_URL 作为连接地址。
    """
    global _redis_client, _redis_available
    try:
        import redis
        url = settings.REDIS_URL
        _redis_client = redis.from_url(
            url,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
            retry_on_timeout=False,
        )
        _redis_client.ping()
        _redis_available = True
        logger.info('Redis 连接成功: %s', url)
    except Exception as e:
        _redis_available = False
        _redis_client = None
        logger.warning('Redis 不可用，降级到进程内缓存: %s', e)


def redis_available():
    """Redis 是否可用。"""
    return _redis_available


def cache_get(key):
    """获取缓存，不存在或过期返回 None。"""
    if _redis_available and _redis_client:
        try:
            raw = _redis_client.get(key)
            if raw:
                return json.loads(raw)
            return None
        except Exception as e:
            logger.warning('Redis cache_get 失败，降级到本地: %s', e)
    # 降级：进程内缓存
    with _local_lock:
        item = _local_cache.get(key)
        if item and item['expires_at'] > time.time():
            return item['value']
        if item:
            _local_cache.pop(key, None)
    return None


def cache_set(key, value, ttl=30):
    """设置缓存，ttl 单位秒。"""
    if _redis_available and _redis_client:
        try:
            _redis_client.setex(key, ttl, json.dumps(value, ensure_ascii=False, default=str))
            return
        except Exception as e:
            logger.warning('Redis cache_set 失败，降级到本地: %s', e)
    # 降级：进程内缓存
    with _local_lock:
        _local_cache[key] = {'value': value, 'expires_at': time.time() + ttl}


def cache_delete(*keys):
    """删除一个或多个缓存键。"""
    if _redis_available and _redis_client:
        try:
            if keys:
                _redis_client.delete(*keys)
            return
        except Exception as e:
            logger.warning('Redis cache_delete 失败，降级到本地: %s', e)
    # 降级：进程内缓存
    with _local_lock:
        for k in keys:
            _local_cache.pop(k, None)


def rate_limit_check(key, limit, window=60):
    """限流检查：返回 (allowed, current_count)。

    使用 Redis INCR + EXPIRE 实现固定窗口计数。
    Redis 不可用时降级到进程内计数器（threading.Lock 保护）。
    """
    if not _redis_available or not _redis_client:
        # 降级到进程内计数器
        with _local_lock:
            now = time.time()
            if key not in _local_rate_limits:
                _local_rate_limits[key] = []
            # 清理过期记录
            _local_rate_limits[key] = [t for t in _local_rate_limits[key] if now - t < window]
            if len(_local_rate_limits[key]) >= limit:
                return False, len(_local_rate_limits[key])
            _local_rate_limits[key].append(now)
            return True, len(_local_rate_limits[key])
    try:
        current = _redis_client.incr(key)
        if current == 1:
            _redis_client.expire(key, window)
        return current <= limit, current
    except Exception as e:
        logger.warning('Redis rate_limit_check 失败: %s', e)
        return True, 0


def rate_limit_key(action, uid):
    """生成限流键。"""
    return 'rl:%s:%s' % (action, uid)
