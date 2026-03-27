"""数字人服务抽象层：统一不同数字人提供商的接口。"""

from app.services.avatar.base import AvatarProvider, AvatarSessionInfo, AvatarVideoResult
from app.services.avatar.heygen_video_service import HeyGenVideoService
from app.services.avatar.liveavatar_service import LiveAvatarStreamService

__all__ = [
    "AvatarProvider",
    "AvatarSessionInfo",
    "AvatarVideoResult",
    "HeyGenVideoService",
    "LiveAvatarStreamService",
]
