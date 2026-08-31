"""企业微信 OAuth 路由：授权回调 + 获取授权链接。

从 Flask 版迁移，适配 FastAPI 风格。
"""
import logging
import secrets

from fastapi import APIRouter
from fastapi.responses import JSONResponse, RedirectResponse, HTMLResponse

from app.config import settings
from app.database import SessionLocal
from app.security import create_access_token
from app.models.user import User
from app.services.wecom import (
    get_user_id_by_code,
    get_user_detail,
    build_oauth_url,
)
from app.services.redis_client import cache_set, cache_get, cache_delete
from app.utils import gen_uuid

logger = logging.getLogger(__name__)

router = APIRouter()


def _error_html(message: str, status_code: int = 400) -> HTMLResponse:
    """返回 UTF-8 编码的 HTML 错误页面。

    企业微信内置浏览器对 application/json 响应可能不以 UTF-8 解码，
    导致中文乱码。改为返回 HTML 页面（带 <meta charset="UTF-8">）确保正确显示。
    """
    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>登录失败</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
       background: #f5f5f0; display: flex; align-items: center; justify-content: center;
       min-height: 100vh; color: #333; }}
.card {{ background: #fff; border-radius: 16px; padding: 40px 32px; max-width: 360px;
        width: 90%; text-align: center; box-shadow: 0 4px 24px rgba(0,0,0,0.08); }}
.icon {{ font-size: 48px; margin-bottom: 16px; }}
.title {{ font-size: 18px; font-weight: 600; margin-bottom: 8px; }}
.desc {{ font-size: 14px; color: #999; line-height: 1.6; margin-bottom: 24px; }}
.btn {{ display: inline-block; padding: 12px 32px; background: #07C160; color: #fff;
       border-radius: 8px; text-decoration: none; font-size: 15px; font-weight: 500; }}
</style>
</head>
<body>
<div class="card">
  <div class="icon">⚠️</div>
  <div class="title">登录失败</div>
  <div class="desc">{message}</div>
  <a class="btn" href="/">返回首页</a>
</div>
</body>
</html>'''
    return HTMLResponse(content=html, status_code=status_code)


@router.get('/wecom/callback')
def wecom_callback(code: str = '', state: str = ''):
    """企业微信网页授权回调：code -> UserId -> 本地用户 -> JWT -> 重定向前端。

    流程：
    1. 验证 OAuth state（防止 CSRF）
    2. 用 OAuth code 换取企业微信 UserId
    3. 查找或创建本地用户（同步昵称/头像/部门）
    4. 根据 WECOM_ADMIN_IDS 白名单设置管理员角色
    5. 签发 JWT 并重定向到前端首页（/?token=xxx&wecom=1）
    """
    if not settings.wecom_enabled:
        return _error_html('企业微信功能暂未启用', 503)

    if not code:
        return _error_html('缺少授权码，请重新登录', 400)

    # 验证 OAuth state（防止 CSRF 攻击）
    if state:
        cached = cache_get(f'wecom:oauth_state:{state}')
        if not cached:
            return _error_html('授权状态已过期，请重新登录', 400)
        cache_delete(f'wecom:oauth_state:{state}')
    else:
        return _error_html('缺少授权状态参数，请重新登录', 400)

    try:
        wecom_user_id = get_user_id_by_code(code)
        if not wecom_user_id:
            return _error_html(
                '获取用户身份失败，可能是服务器 IP 未加入企业微信白名单，请联系管理员', 401
            )

        # 检查管理员白名单（逗号分隔的企业微信 UserId）
        admin_wecom_ids = settings.wecom_admin_id_list
        is_assigned_admin = wecom_user_id in admin_wecom_ids

        db = SessionLocal()
        try:
            user = (
                db.query(User)
                .filter_by(wecom_user_id=wecom_user_id)
                .first()
            )
            if not user:
                # 新用户：获取详情并创建
                detail = get_user_detail(wecom_user_id)
                user = User(
                    id=gen_uuid(),
                    wecom_user_id=wecom_user_id,
                    nickname=detail.get('name', wecom_user_id),
                    avatar=detail.get('avatar', ''),
                    department=detail.get('department', ''),
                    is_admin=is_assigned_admin,
                    role='super_admin' if is_assigned_admin else 'user',
                )
                db.add(user)
                db.commit()
                db.refresh(user)
            else:
                # 已有用户：尝试更新昵称/头像/部门（API 异常时保留原值）
                try:
                    detail = get_user_detail(wecom_user_id)
                    user.nickname = detail.get('name', user.nickname)
                    if detail.get('avatar'):
                        user.avatar = detail['avatar']
                    if detail.get('department'):
                        user.department = detail['department']
                except Exception as detail_err:
                    logger.warning(
                        '获取用户详情失败，保留原值: %s', detail_err
                    )
                # 同步管理员状态：白名单用户自动设为 super_admin
                # 非白名单用户保留已有角色（管理员可通过用户管理页面手动设置 admin 角色）
                if admin_wecom_ids and is_assigned_admin:
                    user.is_admin = True
                    user.role = 'super_admin'
                db.commit()

            token, _jti = create_access_token(user.id)
            redirect_url = f'/?token={token}&wecom=1'
            return RedirectResponse(url=redirect_url, status_code=302)
        finally:
            db.close()
    except Exception as e:
        logger.error('企业微信授权回调失败: %s', e, exc_info=True)
        return _error_html('授权失败，请重试', 500)


@router.get('/api/wecom/login-url')
def wecom_login_url():
    """获取企业微信授权链接（前端在需要登录时调用）。

    生成随机 state 存入 Redis，用于 OAuth 回调时验证防止 CSRF。
    """
    try:
        if not settings.wecom_enabled:
            return JSONResponse(
                status_code=400,
                content={'error': '企业微信未配置'},
            )
        redirect_uri = settings.WECOM_OAUTH_REDIRECT_URI
        if not redirect_uri:
            return JSONResponse(
                status_code=500,
                content={'error': '企业微信回调地址未配置'},
            )
        state = secrets.token_urlsafe(16)
        cache_set(f'wecom:oauth_state:{state}', '1', ttl=600)  # 10分钟有效
        url = build_oauth_url(redirect_uri, state)
        return {'url': url}
    except Exception as e:
        logger.error('获取企业微信授权链接失败: %s', e, exc_info=True)
        return JSONResponse(status_code=500, content={'error': '获取授权链接失败，请重试'})
