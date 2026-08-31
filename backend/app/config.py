"""应用配置：从 .env 读取环境变量。

合并了 Flask 版 + Socket 版的全部配置：
- 数据库连接池
- JWT 认证
- Redis 缓存 + 限流
- 企业微信 OAuth
"""
import os
from dotenv import load_dotenv

# 加载 .env 文件（不存在时自动跳过，使用系统环境变量）
load_dotenv()


class Settings:
    """全局配置（纯类方式，从环境变量读取）。"""

    # ===== 数据库 =====
    DATABASE_URL: str = os.getenv(
        'DATABASE_URL',
        'mysql+pymysql://root:root@localhost:3306/voicehub?charset=utf8mb4',
    )

    # SQLAlchemy 引擎选项
    POOL_SIZE: int = int(os.getenv('POOL_SIZE', '20'))
    POOL_RECYCLE: int = int(os.getenv('POOL_RECYCLE', '3600'))
    POOL_PRE_PING: bool = os.getenv('POOL_PRE_PING', 'true').lower() == 'true'
    SQLALCHEMY_ECHO: bool = os.getenv('SQLALCHEMY_ECHO', 'false').lower() == 'true'

    # ===== JWT =====
    JWT_SECRET_KEY: str = os.getenv('JWT_SECRET_KEY', 'jwt-secret-key-change-in-production')
    JWT_ALGORITHM: str = os.getenv('JWT_ALGORITHM', 'HS256')
    JWT_ACCESS_TOKEN_EXPIRES: int = int(os.getenv('JWT_ACCESS_TOKEN_EXPIRES', '86400'))

    # ===== CORS =====
    CORS_ORIGINS: list = [
        x.strip() for x in os.getenv('CORS_ORIGINS', '*').split(',') if x.strip()
    ]

    # ===== 运行环境 =====
    FLASK_ENV: str = os.getenv('FLASK_ENV', 'development')

    @property
    def is_production(self) -> bool:
        return self.FLASK_ENV == 'production'

    # ===== Redis 配置 =====
    REDIS_URL: str = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

    # 缓存 TTL（秒）
    CACHE_TTL_STATS: int = 30       # 数据看板统计
    CACHE_TTL_DATA: int = 10        # 首页数据（频繁变化，短缓存）

    # 限流配置
    RATE_LIMIT_VOICE: int = 5       # 留言：每窗口最多5条
    RATE_LIMIT_IDEA: int = 5        # 金点子：每窗口最多5条
    RATE_LIMIT_COMMENT: int = 10    # 评论：每窗口最多10条
    RATE_LIMIT_MESSAGE: int = 10    # 私信：每窗口最多10条
    RATE_LIMIT_WINDOW: int = 60     # 限流窗口（秒）

    # ===== 企业微信（WeCom）配置 =====
    # 总开关：备案完成后设为 true 启用企微功能（OAuth 登录、内容安全检测）
    WECOM_ENABLED: bool = os.getenv('WECOM_ENABLED', 'false').lower() == 'true'
    # 凭证获取位置（企业微信管理后台 work.weixin.qq.com）：
    #   WECOM_CORP_ID : 我的企业 → 企业信息 → 企业ID
    #   WECOM_AGENT_ID: 应用管理 → 自建应用 → 应用详情 → AgentId
    #   WECOM_SECRET  : 应用管理 → 自建应用 → 应用详情 → Secret
    WECOM_CORP_ID: str = os.getenv('WECHAT_WORK_CORP_ID', '')
    WECOM_AGENT_ID: str = os.getenv('WECHAT_WORK_AGENT_ID', '')
    WECOM_SECRET: str = os.getenv('WECHAT_WORK_SECRET', '')
    # 通讯录同步应用 Secret（用于拉取组织架构和成员），与 WECOM_SECRET 不同，单独配置
    WECOM_CONTACT_SECRET: str = os.getenv('WECOM_CONTACT_SECRET', '')
    # 网页授权回调地址：必须与企微后台配置的「可信域名」完全一致（HTTPS、已备案）
    WECOM_OAUTH_REDIRECT_URI: str = os.getenv('WECHAT_WORK_OAUTH_REDIRECT_URI', '')
    # 企业微信服务端 API 根地址
    WECOM_API_BASE: str = 'https://qyapi.weixin.qq.com/cgi-bin'
    # 管理员企微 UserId 白名单（逗号分隔）
    WECOM_ADMIN_IDS: str = os.getenv('WECOM_ADMIN_IDS', '')
    # 应用访问地址（用于企微推送卡片点击跳转，备案后填写 HTTPS 域名）
    WECOM_APP_URL: str = os.getenv('WECOM_APP_URL', '')

    @property
    def wecom_admin_id_list(self) -> list:
        return [x.strip() for x in self.WECOM_ADMIN_IDS.split(',') if x.strip()]

    @property
    def wecom_enabled(self) -> bool:
        return self.WECOM_ENABLED and bool(self.WECOM_CORP_ID and self.WECOM_SECRET)

    # ===== WebSocket 配置 =====
    WS_HEARTBEAT_INTERVAL: int = 30  # WebSocket 心跳间隔（秒）


settings = Settings()
