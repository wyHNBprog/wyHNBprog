"""安全模块：JWT 创建/验证 + 密码哈希工具 + Token 撤销。"""
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import jwt, JWTError
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.config import settings
from app.utils import gen_uuid

# 密码哈希上下文（bcrypt）
pwd_context = CryptContext(schemes=['bcrypt'], deprecated='auto')


def create_access_token(subject: str, expires_delta: Optional[timedelta] = None) -> tuple:
    """创建 JWT access token（包含 jti 用于撤销机制）。

    Args:
        subject: 用户 ID（作为 sub 声明）
        expires_delta: 过期时间增量，默认使用配置的 JWT_ACCESS_TOKEN_EXPIRES

    Returns:
        (编码后的 JWT 字符串, jti 字符串)
    """
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(seconds=settings.JWT_ACCESS_TOKEN_EXPIRES)
    )
    jti = str(uuid.uuid4())
    to_encode = {'exp': expire, 'sub': str(subject), 'jti': jti}
    token = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return token, jti


def decode_token(token: str) -> Optional[dict]:
    """解码并验证 JWT token。

    Returns:
        解码后的 payload 字典，验证失败返回 None
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        return payload
    except JWTError:
        return None


def revoke_token(token: str, db: Session) -> bool:
    """将 token 加入黑名单（撤销）。

    从 token 中提取 jti 和 exp，写入 token_blacklist 表。
    token 过期后黑名单记录由定时任务清理。

    Returns:
        True 表示撤销成功，False 表示 token 无效或已过期
    """
    payload = decode_token(token)
    if not payload:
        return False

    jti = payload.get('jti')
    if not jti:
        return False

    # 检查是否已在黑名单中
    from app.models.token_blacklist import TokenBlacklist
    existing = db.query(TokenBlacklist).filter_by(jti=jti).first()
    if existing:
        return True  # 已撤销，幂等返回

    # 提取过期时间
    exp = payload.get('exp')
    if exp:
        expires_at = datetime.fromtimestamp(exp, tz=timezone.utc).replace(tzinfo=None)
    else:
        expires_at = datetime.utcnow() + timedelta(seconds=settings.JWT_ACCESS_TOKEN_EXPIRES)

    db.add(TokenBlacklist(
        id=gen_uuid(),
        jti=jti,
        expires_at=expires_at,
    ))
    db.commit()
    return True


def is_token_revoked(token: str, db: Session) -> bool:
    """检查 token 是否已被撤销（在黑名单中）。

    Returns:
        True 表示已撤销，False 表示有效
    """
    payload = decode_token(token)
    if not payload:
        return True  # 无效 token 视为已撤销

    jti = payload.get('jti')
    if not jti:
        return False  # 无 jti 的旧 token 不检查（向后兼容）

    from app.models.token_blacklist import TokenBlacklist
    blacklisted = db.query(TokenBlacklist).filter_by(jti=jti).first()
    return blacklisted is not None


def hash_password(password: str) -> str:
    """密码哈希（bcrypt）。"""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证明文密码与哈希是否匹配。"""
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception:
        return False
