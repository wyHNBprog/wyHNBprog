"""心声相关 Pydantic 模型（含输入校验）。"""
from typing import List, Optional

from pydantic import BaseModel, Field, StringConstraints, field_validator
from typing_extensions import Annotated


class VoiceCreate(BaseModel):
    """创建心声请求。"""
    content: str = Field(..., min_length=1, max_length=500, description='留言内容（1-500字）')
    anonName: Optional[str] = Field(None, max_length=64, description='匿名昵称')
    isAnonymous: bool = False
    tags: Optional[List[Annotated[str, StringConstraints(max_length=32)]]] = Field(None, description='标签列表（最多10个，每个最长32字符）')

    @field_validator('tags')
    @classmethod
    def validate_tags_length(cls, v):
        if v is not None and len(v) > 10:
            raise ValueError('标签最多10个')
        return v


class CommentCreate(BaseModel):
    """创建评论请求。"""
    content: str = Field(..., min_length=1, max_length=500, description='评论内容（1-500字）')
    anonName: Optional[str] = Field(None, max_length=64, description='匿名昵称')


class StatusUpdate(BaseModel):
    """审核状态更新请求。"""
    status: str = Field(..., pattern='^(pending|approved|rejected|voting)$', description='审核状态')
    rejectReason: Optional[str] = Field('', max_length=512, description='驳回原因')


class AnnouncementCreate(BaseModel):
    """创建公告请求。"""
    title: str = Field(..., min_length=1, max_length=200, description='公告标题')
    content: str = Field(..., min_length=1, max_length=5000, description='公告内容')
    pinned: bool = False


class AnnouncementUpdate(BaseModel):
    """更新公告请求。"""
    title: Optional[str] = Field(None, max_length=200, description='公告标题')
    content: Optional[str] = Field(None, max_length=5000, description='公告内容')
    pinned: Optional[bool] = None


class NotificationReadByType(BaseModel):
    """按分类标记通知已读请求。"""
    type: str = Field(..., description='通知类型：voice|idea|message|feedback|system')


class ChatMessageCreate(BaseModel):
    """发送聊天消息请求。"""
    content: str = Field(..., min_length=1, max_length=2000, description='消息内容')
