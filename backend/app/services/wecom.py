"""企业微信 (WeCom) 服务层。

access_token 获取与缓存 + OAuth 辅助函数 + 应用消息推送。
从 Flask 版迁移，使用 settings 代替 current_app.config，内存缓存代替 Redis。
"""
import time
import logging
import urllib.parse

import requests

from app.config import settings

logger = logging.getLogger(__name__)

# access_token 内存缓存（生产环境建议改用 Redis 实现多 worker 共享）
_token_cache = {'token': '', 'expires_at': 0}
# 通讯录 access_token 独立缓存（通讯录 secret 与应用 secret 不同，token 各自独立）
_contact_token_cache = {'token': '', 'expires_at': 0}


def get_access_token() -> str:
    """获取企业微信 access_token，带内存缓存（有效期 7200 秒，提前 600 秒刷新）。"""
    corpid = settings.WECOM_CORP_ID
    secret = settings.WECOM_SECRET
    if not corpid or not secret:
        raise ValueError('企业微信 CorpID 或 Secret 未配置，请在 .env 中设置')

    now = time.time()
    if _token_cache['token'] and _token_cache['expires_at'] > now + 600:
        return _token_cache['token']

    api_base = settings.WECOM_API_BASE
    url = f'{api_base}/gettoken?corpid={corpid}&corpsecret={secret}'
    resp = requests.get(url, timeout=10)
    data = resp.json()

    if data.get('errcode') != 0:
        errcode = data.get('errcode')
        errmsg = data.get('errmsg')
        logger.error('获取 access_token 失败: %s %s', errcode, errmsg)
        raise RuntimeError(f'获取 access_token 失败: {errmsg} (code={errcode})')

    _token_cache['token'] = data['access_token']
    _token_cache['expires_at'] = now + 7200
    return _token_cache['token']


def get_contact_access_token() -> str:
    """获取企业微信通讯录 access_token，带内存缓存。

    通讯录同步应用使用独立的 secret（WECOM_CONTACT_SECRET），
    用于拉取组织架构和成员列表。
    """
    corpid = settings.WECOM_CORP_ID
    secret = settings.WECOM_CONTACT_SECRET
    if not corpid or not secret:
        raise ValueError('企业微信 CorpID 或通讯录 Secret 未配置，请在 .env 中设置')

    now = time.time()
    if _contact_token_cache['token'] and _contact_token_cache['expires_at'] > now + 600:
        return _contact_token_cache['token']

    api_base = settings.WECOM_API_BASE
    url = f'{api_base}/gettoken?corpid={corpid}&corpsecret={secret}'
    resp = requests.get(url, timeout=10)
    data = resp.json()

    if data.get('errcode') != 0:
        errcode = data.get('errcode')
        errmsg = data.get('errmsg')
        logger.error('获取通讯录 access_token 失败: %s %s', errcode, errmsg)
        raise RuntimeError(f'获取通讯录 access_token 失败: {errmsg} (code={errcode})')

    _contact_token_cache['token'] = data['access_token']
    _contact_token_cache['expires_at'] = now + 7200
    return _contact_token_cache['token']


def get_user_id_by_code(code: str) -> str:
    """通过 OAuth code 获取企业微信 UserId。"""
    access_token = get_access_token()
    api_base = settings.WECOM_API_BASE
    url = f'{api_base}/user/getuserinfo?access_token={access_token}&code={code}'
    resp = requests.get(url, timeout=10)
    data = resp.json()

    if data.get('errcode') != 0:
        logger.error('获取 UserId 失败: %s %s', data.get('errcode'), data.get('errmsg'))
        return None

    return data.get('UserId')


def get_department_name(dept_id) -> str:
    """通过部门 ID 获取部门名称。"""
    access_token = get_access_token()
    api_base = settings.WECOM_API_BASE
    url = f'{api_base}/department/get?access_token={access_token}&id={dept_id}'
    try:
        resp = requests.get(url, timeout=10)
        data = resp.json()
        if data.get('errcode') == 0:
            return data.get('department', {}).get('name', '')
    except Exception as e:
        logger.warning('获取部门名称失败: %s', e)
    return ''


def get_all_departments() -> list:
    """获取企业微信全部部门列表。"""
    access_token = get_contact_access_token()
    api_base = settings.WECOM_API_BASE
    url = f'{api_base}/department/list?access_token={access_token}'
    try:
        resp = requests.get(url, timeout=10)
        data = resp.json()
        if data.get('errcode') == 0:
            return data.get('department', [])
    except Exception as e:
        logger.warning('获取部门列表失败: %s', e)
    return []


def get_all_wecom_members() -> tuple:
    """拉取企业微信通讯录全部成员（含未登录论坛的用户）。

    通过部门 ID=1（根部门）+ fetch_child=1 递归获取所有部门的成员。
    返回 (members, error)：members 为 [{userid, name, department, avatar}] 列表；
    error 为 None 表示成功，否则为可展示给前端的错误描述（含企微 errcode/errmsg）。
    """
    try:
        access_token = get_contact_access_token()
    except Exception as e:
        logger.error('获取通讯录 access_token 失败: %s', e)
        return [], str(e)

    api_base = settings.WECOM_API_BASE

    # 先获取部门列表，建立 dept_id -> name 映射
    departments = get_all_departments()
    dept_map = {d.get('id'): d.get('name', '') for d in departments}

    # 从根部门递归获取所有成员（简化版，不含敏感信息）
    url = f'{api_base}/user/simplelist?access_token={access_token}&department_id=1&fetch_child=1'
    try:
        resp = requests.get(url, timeout=15)
        data = resp.json()
    except Exception as e:
        logger.error('拉取通讯录成员异常: %s', e)
        return [], f'拉取通讯录失败：{e}'

    if data.get('errcode') != 0:
        errcode = data.get('errcode')
        errmsg = data.get('errmsg')
        logger.error('拉取通讯录成员失败: %s %s', errcode, errmsg)
        return [], f'企业微信通讯录接口报错 (errcode={errcode})：{errmsg or "请检查通讯录权限和IP白名单"}'

    members = []
    for m in data.get('userlist', []):
        dept_ids = m.get('department', [])
        dept_name = ''
        if dept_ids:
            dept_name = dept_map.get(dept_ids[0], '')
        members.append({
            'userid': m.get('userid', ''),
            'name': m.get('name', m.get('userid', '')),
            'department': dept_name,
            'avatar': m.get('avatar', ''),
        })
    logger.info('拉取通讯录成员成功: %d 人', len(members))
    return members, None


def get_user_detail(user_id: str) -> dict:
    """获取企业微信用户详情（昵称、头像、部门等）。"""
    access_token = get_access_token()
    api_base = settings.WECOM_API_BASE
    url = f'{api_base}/user/get?access_token={access_token}&userid={user_id}'
    resp = requests.get(url, timeout=10)
    data = resp.json()

    if data.get('errcode') != 0:
        logger.warning('获取用户详情失败: %s %s', data.get('errcode'), data.get('errmsg'))
        return {'userid': user_id, 'name': user_id, 'avatar': '', 'department': ''}

    dept_ids = data.get('department', [])
    dept_name = ''
    if dept_ids:
        dept_name = get_department_name(dept_ids[0])

    return {
        'userid': data.get('userid', user_id),
        'name': data.get('name', user_id),
        'avatar': data.get('avatar', ''),
        'department': dept_name,
    }


def build_oauth_url(redirect_uri: str, state: str = '') -> str:
    """构造企业微信网页授权链接。"""
    corpid = settings.WECOM_CORP_ID
    agent_id = settings.WECOM_AGENT_ID
    if not corpid:
        raise ValueError('企业微信 CorpID 未配置')
    encoded_uri = urllib.parse.quote(redirect_uri, safe='')
    return (
        f'https://open.weixin.qq.com/connect/oauth2/authorize'
        f'?appid={corpid}'
        f'&redirect_uri={encoded_uri}'
        f'&response_type=code'
        f'&scope=snsapi_base'
        f'&state={state}'
        f'&agentid={agent_id}'
        f'#wechat_redirect'
    )


# ===== 应用消息推送（手机端通知） =====

def send_text_message(wecom_user_id: str, content: str) -> bool:
    """发送企业微信应用文本消息给指定用户。

    用于手机端推送通知：即使用户未打开应用，也能在企业微信中收到消息提醒。

    Args:
        wecom_user_id: 接收人的企业微信 UserId
        content: 消息文本内容

    Returns:
        True 表示发送成功，False 表示失败
    """
    if not settings.wecom_enabled:
        return False
    if not wecom_user_id or not content:
        return False

    try:
        access_token = get_access_token()
        api_base = settings.WECOM_API_BASE
        url = f'{api_base}/message/send?access_token={access_token}'

        payload = {
            'touser': wecom_user_id,
            'msgtype': 'text',
            'agentid': int(settings.WECOM_AGENT_ID),
            'text': {'content': content},
            'enable_duplicate_check': 1,
            'duplicate_check_interval': 1800,
        }
        resp = requests.post(url, json=payload, timeout=10)
        data = resp.json()

        if data.get('errcode') != 0:
            logger.error('企微推送失败: errcode=%s errmsg=%s', data.get('errcode'), data.get('errmsg'))
            return False
        logger.info('企微推送成功: user=%s', wecom_user_id)
        return True
    except Exception as e:
        logger.error('企微推送异常: %s', e)
        return False


def send_textcard_message(wecom_user_id: str, title: str, description: str, url: str, btn_text: str = '查看详情') -> bool:
    """发送企业微信文本卡片消息（带可点击链接）。

    用户点击卡片后在企微内打开应用页面，适合审核结果、私信回复等通知场景。

    Args:
        wecom_user_id: 接收人的企业微信 UserId
        title: 卡片标题（最多128字节）
        description: 卡片描述（最多512字节）
        url: 点击后跳转的 URL
        btn_text: 按钮文字，默认"查看详情"

    Returns:
        True 表示发送成功，False 表示失败
    """
    if not settings.wecom_enabled:
        return False
    if not wecom_user_id or not title:
        return False

    try:
        access_token = get_access_token()
        api_base = settings.WECOM_API_BASE
        api_url = f'{api_base}/message/send?access_token={access_token}'

        payload = {
            'touser': wecom_user_id,
            'msgtype': 'textcard',
            'agentid': int(settings.WECOM_AGENT_ID),
            'textcard': {
                'title': title,
                'description': description or '',
                'url': url or '',
                'btntxt': btn_text,
            },
            'enable_duplicate_check': 1,
            'duplicate_check_interval': 1800,
        }
        resp = requests.post(api_url, json=payload, timeout=10)
        data = resp.json()

        if data.get('errcode') != 0:
            logger.error('企微卡片推送失败: errcode=%s errmsg=%s', data.get('errcode'), data.get('errmsg'))
            return False
        logger.info('企微卡片推送成功: user=%s', wecom_user_id)
        return True
    except Exception as e:
        logger.error('企微卡片推送异常: %s', e)
        return False
