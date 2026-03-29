"""数字人服务抽象基类：定义统一接口供不同提供商实现。"""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class AvatarSessionInfo:
    """实时流式数字人会话信息。"""
    session_token: str
    session_id: str
    provider: str  # "liveavatar"


@dataclass
class AvatarVideoResult:
    """视频生成型数字人结果。"""
    video_id: str
    video_url: str | None = None
    status: str = "pending"  # pending / processing / completed / failed
    provider: str = "heygen"


class AvatarProvider(ABC):
    """数字人服务提供商抽象基类。"""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """提供商名称标识。"""

    @property
    @abstractmethod
    def mode(self) -> str:
        """模式：'streaming' (实时流) 或 'video' (视频生成)。"""


class StreamingAvatarProvider(AvatarProvider):
    """实时流式数字人提供商（如 LiveAvatar）。"""

    @property
    def mode(self) -> str:
        return "streaming"

    @abstractmethod
    async def create_session(self, avatar_id: str | None = None) -> AvatarSessionInfo:
        """创建实时流式会话，返回 session token 供前端 SDK 使用。"""


class VideoAvatarProvider(AvatarProvider):
    """视频生成型数字人提供商（如 HeyGen Video API）。"""

    @property
    def mode(self) -> str:
        return "video"

    @abstractmethod
    async def generate_video(
        self,
        text: str,
        avatar_id: str | None = None,
        voice_id: str | None = None,
        avatar_type: str | None = None,
        resolution: str = "720p",
        aspect_ratio: str = "16:9",
        expressiveness: str = "medium",
        remove_background: bool = False,
        voice_locale: str = "zh-CN",
    ) -> AvatarVideoResult:
        """根据文本生成数字人视频。"""

    @abstractmethod
    async def check_video_status(self, video_id: str) -> AvatarVideoResult:
        """查询视频生成状态。"""
