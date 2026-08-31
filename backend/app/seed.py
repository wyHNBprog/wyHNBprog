"""初始化测试数据（仅在数据库为空时执行）。"""
import logging

from sqlalchemy.orm import Session

from app.models.user import User
from app.models.voice import Voice, VoiceTag
from app.models.idea import Idea
from app.models.feedback import Feedback
from app.models.message import Message
from app.models.announce import Announce
from app.models.notification import Notification
from app.utils import gen_uuid, ANON_NAME

logger = logging.getLogger(__name__)


def seed_data(db: Session) -> None:
    """初始化测试数据（仅在数据库为空时）。

    包含：管理员用户、普通用户、心声、金点子、反馈、私信、公告、通知。
    """
    if db.query(User).first() or db.query(Voice).first():
        return

    # 管理员用户
    admin = User(
        id=gen_uuid(),
        wecom_user_id='admin',
        nickname='管理员',
        is_admin=True,
        role='super_admin',
    )
    db.add(admin)
    db.flush()

    # 普通用户
    user = User(
        id=gen_uuid(),
        wecom_user_id='test_user',
        nickname='体验用户',
        is_admin=False,
    )
    db.add(user)

    # 心声
    voices_data = [
        ('最近项目节奏有点快，希望团队能多一些沟通，让大家对整体进度有更清晰的了解。', 'approved', 12, ['工作感悟']),
        ('食堂的麻辣烫真的绝了！本周第三次打卡，推荐给还没试过的同事～', 'approved', 28, ['生活分享']),
        ('关于新办公系统的使用体验：界面简洁了很多，但部分功能入口不太好找，建议做个新手引导。', 'approved', 8, ['建议想法']),
        ('感谢技术部的小王同学，帮我解决了那个困扰一周的bug，真的非常感谢！', 'approved', 35, ['团队协作']),
        ('测试待审核留言，请管理员审核通过。', 'pending', 0, ['吐槽一下']),
    ]
    for content, status, likes, tags in voices_data:
        v = Voice(
            id=gen_uuid(),
            user_id=user.id,
            content=content,
            anon_name=ANON_NAME,
            is_anonymous=True,
            like_count=likes,
            status=status,
        )
        db.add(v)
        db.flush()
        for tag in tags:
            db.add(VoiceTag(id=gen_uuid(), voice_id=v.id, tag=tag))

    # 金点子
    ideas_data = [
        ('每月一次跨部门午餐会', '随机匹配不同部门的同事一起午餐，增进跨部门交流和理解', '文化建设', 'voting', 42, False),
        ('设立"创新星期五"', '每周五下午留出2小时，让大家自由探索感兴趣的技术或项目', '技术升级', 'voting', 67, False),
        ('弹性午休时间', '将午休时间从固定12:00-13:00改为11:30-13:30弹性制', '制度流程', 'voting', 89, True),
        ('优化会议室预约系统', '增加手机端预约功能，支持扫码签到和自动释放', '产品创新', 'adopted', 120, True),
        ('建立技术分享Wiki', '建立内部知识库，鼓励大家分享技术心得和最佳实践', '技术升级', 'completed', 156, True),
    ]
    for title, desc, cat, status, votes, has_flower in ideas_data:
        i = Idea(
            id=gen_uuid(),
            user_id=user.id,
            title=title,
            description=desc,
            category=cat,
            vote_count=votes,
            has_flower=has_flower,
            flower_count=1 if has_flower else 0,
            anon_name=ANON_NAME,
            is_anonymous=True,
            status=status,
        )
        db.add(i)

    # 反馈
    feedbacks_data = [
        ('食堂餐饮', '希望增加素食窗口，现在选择太少了', 'pending'),
        ('IT设备', '开发部的显示器太小了，建议统一升级到27寸', 'replied'),
        ('制度流程', '报销流程太繁琐了，希望能简化审批环节', 'replied'),
    ]
    for ftype, content, status in feedbacks_data:
        f = Feedback(
            id=gen_uuid(),
            user_id=user.id,
            type=ftype,
            content=content,
            anon_name=ANON_NAME,
            is_anonymous=True,
            status=status,
        )
        db.add(f)

    # 私信
    msg = Message(
        id=gen_uuid(),
        user_id=user.id,
        content='建议增加一个技术讨论专区',
        anon_name='好奇的猫头鹰',
        status='unread',
        admin_reply=None,
    )
    db.add(msg)

    # 公告
    ann = Announce(
        id=gen_uuid(),
        title='欢迎来到NNIT论坛',
        content='这是一个匿名分享平台，欢迎大家畅所欲言。请注意文明发言，遵守社区规范。所有内容发布后需经管理员审核。',
        is_pinned=True,
    )
    db.add(ann)

    # 通知
    notif = Notification(
        id=gen_uuid(),
        user_id=user.id,
        type='system',
        text='欢迎来到NNIT论坛！',
        is_read=False,
    )
    db.add(notif)

    db.commit()
    logger.info('seed_data: 测试数据初始化完成')
