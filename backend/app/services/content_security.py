"""内容安全审核服务。

接入企业微信 msg_sec_check（文本检测）和 img_sec_check（图片检测）。
匿名 UGC 平台必须接入，违规内容拦截。

设计原则：
- 企业微信未配置时跳过检测（返回安全），不影响开发/测试
- 检测异常时不阻断业务（返回安全 + 警告日志），避免服务不可用导致无法发帖
"""
import base64
import ipaddress
import logging
import socket
from urllib.parse import urlparse

import httpx

from app.config import settings
from app.services.wecom import get_access_token

logger = logging.getLogger(__name__)


def check_text(content, scene=1, openid=''):
    """检测文本是否合规。

    :param content: 待检测文本（最长 2500 字）
    :param scene: 场景值，1=资料，2=评论，3=论坛，4=社交日志
    :param openid: 用户的 openid（可选）
    :return: (is_safe: bool, detail: dict)
    """
    if not content or not content.strip():
        return True, {}

    if not settings.wecom_enabled:
        # 企微未启用（测试阶段 / 备案前），跳过检测
        return True, {}

    try:
        access_token = get_access_token()
        api_base = settings.WECOM_API_BASE
        url = f'{api_base}/msg_sec_check?access_token={access_token}'
        payload = {
            'content': content[:2500],
            'scene': scene,
        }
        if openid:
            payload['openid'] = openid

        with httpx.Client(timeout=10) as client:
            resp = client.post(url, json=payload)
            data = resp.json()

        if data.get('errcode') == 0:
            return True, {'detail': '内容合规'}
        else:
            logger.warning('内容安全检测不通过: %s %s', data.get('errcode'), data.get('errmsg'))
            return False, {
                'errcode': data.get('errcode'),
                'errmsg': data.get('errmsg', '内容不合规'),
            }
    except Exception as e:
        logger.error('内容安全检测异常: %s', e)
        # 检测服务自身不可用时不阻断业务（放行 + 警告日志）
        # 原因：企业微信 API 异常 / 网络不通 / Secret 未配置等属于服务可用性问题，
        # 不应导致用户完全无法发帖。违规内容已有管理员人工审核流程兜底。
        return True, {'warning': str(e)}


def _is_safe_url(url: str) -> bool:
    """检查 URL 是否安全（防止 SSRF 攻击）。

    拒绝指向内网地址（私有 IP、回环地址、链路本地等）的 URL。
    仅允许 HTTP/HTTPS 协议。
    """
    try:
        parsed = urlparse(url)
        # 仅允许 http/https 协议
        if parsed.scheme not in ('http', 'https'):
            return False
        hostname = parsed.hostname
        if not hostname:
            return False
        # 解析主机名获取所有 IP 地址
        try:
            addr_infos = socket.getaddrinfo(hostname, None)
        except socket.gaierror:
            return False
        for addr_info in addr_infos:
            ip = ipaddress.ip_address(addr_info[4][0])
            # 拒绝内网/私有/回环/链路本地地址
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                return False
        return True
    except Exception:
        return False


def check_image(image_base64_or_url, scene=1):
    """检测图片是否合规。

    :param image_base64_or_url: base64 编码的图片或图片 URL
    :param scene: 场景值
    :return: (is_safe: bool, detail: dict)
    """
    if not settings.wecom_enabled:
        return True, {}

    try:
        access_token = get_access_token()
        api_base = settings.WECOM_API_BASE
        url = f'{api_base}/img_sec_check?access_token={access_token}'

        if isinstance(image_base64_or_url, str) and image_base64_or_url.startswith('http'):
            # URL 方式：先下载（SSRF 防护：拒绝内网地址）
            if not _is_safe_url(image_base64_or_url):
                logger.warning('图片 URL 安全检查失败（疑似 SSRF）: %s', image_base64_or_url[:100])
                return False, {'errmsg': '图片 URL 不安全'}
            with httpx.Client(timeout=10) as client:
                img_resp = client.get(image_base64_or_url)
                img_bytes = img_resp.content
        elif isinstance(image_base64_or_url, str):
            # base64 字符串：解码为二进制
            img_bytes = base64.b64decode(image_base64_or_url)
        else:
            img_bytes = image_base64_or_url

        # 企微 img_sec_check 要求 multipart/form-data 上传媒体文件
        with httpx.Client(timeout=15) as client:
            resp = client.post(
                url,
                data={'scene': str(scene)},
                files={'media': ('image.png', img_bytes, 'application/octet-stream')},
            )
            data = resp.json()

        if data.get('errcode') == 0:
            return True, {'detail': '图片合规'}
        else:
            return False, {
                'errcode': data.get('errcode'),
                'errmsg': data.get('errmsg', '图片不合规'),
            }
    except Exception as e:
        logger.error('图片安全检测异常: %s', e)
        # 检测服务自身不可用时不阻断业务（放行 + 警告日志）
        return True, {'warning': str(e)}


def check_ugc_content(content, content_type='text'):
    """UGC 内容统一入口：文本和图片都检测。

    :param content: 文本内容或图片 base64/URL
    :param content_type: 'text' 或 'image'
    :return: (is_safe: bool, message: str)
    """
    if content_type == 'image':
        is_safe, detail = check_image(content)
    else:
        is_safe, detail = check_text(content)

    if not is_safe:
        return False, detail.get('errmsg', '内容不合规，请修改后重试')
    return True, ''
