"""FastAPI 应用入口。

职责：
- 创建 FastAPI app，配置 CORS
- 注册所有路由器
- 启动时 db.create_all() + seed_data()
- GET /api/health 健康检查
- 静态文件服务（SPA，指向 ../frontend/dist）
- 自定义异常处理（匹配 Flask 响应格式）
"""
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse, FileResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import settings
from app.database import Base, engine, SessionLocal
from app.seed import seed_data
from app.security import decode_token
from app.utils import set_current_uid

# 导入所有模型，确保 Base.metadata 包含全部表定义
from app.models import (  # noqa: F401
    User, Voice, VoiceLike, VoiceTag, Comment, CommentLike,
    Idea, IdeaVote, Feedback, FeedbackReply, Message, ChatMessage, Announce,
    Notification, AdminConfig, TokenBlacklist,
)

# 导入所有路由
from app.routes.auth import router as auth_router
from app.routes.data import router as data_router
from app.routes.voice import router as voice_router
from app.routes.comment import router as comment_router
from app.routes.idea import router as idea_router
from app.routes.feedback import router as feedback_router
from app.routes.message import router as message_router
from app.routes.announce import router as announce_router
from app.routes.notification import router as notification_router
from app.routes.user import router as user_router
from app.routes.dashboard import router as dashboard_router
from app.routes.sse import router as sse_router
from app.routes.websocket import router as websocket_router
from app.routes.wecom_auth import router as wecom_auth_router

from app.scheduler import start_cleanup_scheduler

logger = logging.getLogger(__name__)

# 前端静态文件目录（../frontend/dist）
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
FRONTEND_DIST = os.path.abspath(os.path.join(BACKEND_DIR, '..', 'frontend', 'dist'))


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时建表 + 初始化测试数据。

    数据库不可用时优雅降级：记录警告并继续启动，
    使开发环境下即使数据库暂时不可用，应用仍能提供 API 文档等服务。
    """
    try:
        # 创建所有表
        Base.metadata.create_all(bind=engine)
        # 初始化测试数据（多 worker 安全：异常时跳过）
        db = SessionLocal()
        try:
            seed_data(db)
        except Exception as e:
            logger.warning('seed_data 跳过（可能已由其他 worker 执行）: %s', e)
        finally:
            db.close()
    except Exception as e:
        logger.warning('数据库连接失败，应用以降级模式启动: %s', e)

    # 启动后台清理定时任务（Token 黑名单过期清理）
    start_cleanup_scheduler()

    # 生产环境安全校验：JWT 使用默认密钥时拒绝启动，防止被利用伪造身份
    if settings.is_production and settings.JWT_SECRET_KEY == 'jwt-secret-key-change-in-production':
        raise RuntimeError(
            '安全错误：生产环境 JWT_SECRET_KEY 仍为默认值。'
            '请在 .env 中设置强随机密钥（如执行: python -c "import secrets;print(secrets.token_urlsafe(64))"），'
            '否则攻击者可用公开密钥伪造 JWT 绕过企业微信登录。'
        )

    # 初始化 Redis 连接（缓存 + 限流）
    from app.services.redis_client import init_redis
    init_redis()

    yield
    # 关闭时无需额外处理


def create_app() -> FastAPI:
    """创建 FastAPI 应用实例。"""
    app = FastAPI(
        title='VoiceHub API',
        description='NNIT 匿名论坛后端（FastAPI 版）',
        version='3.0.0',
        lifespan=lifespan,
    )

    # ===== GZip 压缩（静态资源 + API 响应，减少传输体积）=====
    app.add_middleware(GZipMiddleware, minimum_size=1024)

    # ===== CORS =====
    # 浏览器不允许 allow_origins=['*'] 与 allow_credentials=True 同时生效，
    # 生产环境必须配置具体域名；此处检测通配符并自动降级凭证携带。
    cors_origins = settings.CORS_ORIGINS
    allow_credentials = True
    if '*' in cors_origins:
        if settings.is_production:
            logger.warning(
                '安全警告：生产环境 CORS_ORIGINS 为通配符 "*"，'
                '已自动禁用 allow_credentials。请在 .env 中配置具体域名。'
            )
            allow_credentials = False
        else:
            # 开发环境：移除通配符以兼容 credentials，回退为允许所有来源（不带凭证）
            cors_origins = [o for o in cors_origins if o != '*']
            if not cors_origins:
                cors_origins = ['*']
                allow_credentials = False
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=allow_credentials,
        allow_methods=['*'],
        allow_headers=['*'],
    )

    # ===== 上下文中间件：在异步上下文中设置 current_uid =====
    # FastAPI 同步路由处理器运行在线程池中，contextvars 在依赖中设置的值
    # 无法跨线程传递。此中间件在主事件循环中设置 current_uid，
    # 确保同步路由处理器能通过 contextvars 副本正确获取用户 ID（isMine 等）。
    @app.middleware('http')
    async def set_uid_middleware(request: Request, call_next):
        # 仅对 API 和 WebSocket 路径解码 JWT，跳过静态文件请求
        path = request.url.path
        if path.startswith('/api/') or path.startswith('/wecom/') or path == '/api/ws':
            auth_header = request.headers.get('Authorization', '')
            token = auth_header.replace('Bearer ', '') if auth_header.startswith('Bearer ') else ''
            if token:
                payload = decode_token(token)
                if payload and payload.get('sub'):
                    set_current_uid(payload['sub'])
                else:
                    set_current_uid(None)
            else:
                set_current_uid(None)
        else:
            set_current_uid(None)
        response = await call_next(request)
        return response

    # ===== 注册路由器 =====
    app.include_router(auth_router)
    app.include_router(data_router)
    app.include_router(voice_router)
    app.include_router(comment_router)
    app.include_router(idea_router)
    app.include_router(feedback_router)
    app.include_router(message_router)
    app.include_router(announce_router)
    app.include_router(notification_router)
    app.include_router(user_router)
    app.include_router(dashboard_router)
    app.include_router(sse_router)
    app.include_router(websocket_router)
    app.include_router(wecom_auth_router)

    # ===== 健康检查 =====
    @app.get('/api/health')
    def health():
        return {'code': 200, 'message': 'OK', 'data': {'status': 'healthy'}}

    # ===== 自定义异常处理 =====

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        """FastAPI HTTPException -> 统一 JSON 格式。"""
        path = request.url.path
        if path.startswith('/api/') or path.startswith('/wecom/'):
            return JSONResponse(
                status_code=exc.status_code,
                content={'code': exc.status_code, 'message': exc.detail, 'data': None},
            )
        # 非 API 路由：SPA 模式回退到 index.html
        if exc.status_code == 404 and request.method == 'GET':
            index_path = os.path.join(FRONTEND_DIST, 'index.html')
            if os.path.isfile(index_path):
                return FileResponse(index_path)
        return JSONResponse(
            status_code=exc.status_code,
            content={'code': exc.status_code, 'message': exc.detail or '错误', 'data': None},
        )

    @app.exception_handler(StarletteHTTPException)
    async def starlette_exception_handler(request: Request, exc: StarletteHTTPException):
        """Starlette HTTPException（404/405 等）-> API 返回 JSON，非 API 返回 SPA index.html。"""
        path = request.url.path
        if path.startswith('/api/') or path.startswith('/wecom/'):
            # API 路由不存在，返回 JSON 404
            return JSONResponse(
                status_code=exc.status_code,
                content={'code': exc.status_code, 'message': '资源不存在', 'data': None},
            )
        # 非 API 路由：SPA 模式回退到 index.html
        if exc.status_code == 404 and request.method == 'GET':
            index_path = os.path.join(FRONTEND_DIST, 'index.html')
            if os.path.isfile(index_path):
                return FileResponse(index_path)
        return JSONResponse(
            status_code=exc.status_code,
            content={'code': exc.status_code, 'message': exc.detail or '错误', 'data': None},
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """未捕获异常 -> 500 JSON。"""
        logger.error('服务器内部错误: %s', exc, exc_info=True)
        return JSONResponse(
            status_code=500,
            content={'code': 500, 'message': '服务器内部错误', 'data': None},
        )

    # ===== 静态文件服务（SPA，必须放最后）=====

    @app.get('/')
    def serve_index():
        """根路径返回前端 index.html。"""
        index_path = os.path.join(FRONTEND_DIST, 'index.html')
        if os.path.isfile(index_path):
            return FileResponse(index_path)
        return {'code': 200, 'message': 'VoiceHub API', 'data': {'status': 'running'}}

    @app.get('/{path:path}')
    def serve_static(path: str):
        """SPA 静态文件服务 + 回退到 index.html。"""
        # 安全过滤：禁止访问后端文件及敏感文件类型
        SENSITIVE_EXTENSIONS = ('.env', '.py', '.git', '.htaccess', '.sql', '.log', '.yaml', '.yml', '.ini', '.conf')
        SENSITIVE_PREFIXES = ('backend/', '.env', '.git', '__pycache__/')

        if any(path.startswith(p) for p in SENSITIVE_PREFIXES) or any(path.endswith(ext) for ext in SENSITIVE_EXTENSIONS):
            return JSONResponse(status_code=404, content={'error': 'Not Found'})
        # API 路由不存在
        if path.startswith('api/') or path.startswith('wecom/'):
            return JSONResponse(
                status_code=404,
                content={'code': 404, 'message': 'API 不存在', 'data': None},
            )
        # 路径遍历防护：规范化路径并确保不逃出 FRONTEND_DIST
        base = os.path.realpath(FRONTEND_DIST)
        file_path = os.path.realpath(os.path.join(base, path))
        if not (file_path == base or file_path.startswith(base + os.sep)):
            return JSONResponse(status_code=404, content={'error': 'Not Found'})
        # 尝试提供静态文件
        if os.path.isfile(file_path):
            return FileResponse(file_path)
        # SPA 回退：返回 index.html
        index_path = os.path.join(FRONTEND_DIST, 'index.html')
        if os.path.isfile(index_path):
            return FileResponse(index_path)
        return JSONResponse(
            status_code=404,
            content={'code': 404, 'message': '资源不存在', 'data': None},
        )

    return app


# 全局 app 实例（uvicorn 引用）
app = create_app()


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(
        'app.main:app',
        host='0.0.0.0',
        port=int(os.getenv('PORT', '8000')),
        reload=settings.FLASK_ENV != 'production',
    )
