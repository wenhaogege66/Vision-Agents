"""LiveAvatar 实时流式数字人服务：通过 LiveAvatar API 创建会话。"""

import logging

import httpx
from fastapi import HTTPException

from app.config import settings
from app.services.avatar.base import AvatarSessionInfo, StreamingAvatarProvider

logger = logging.getLogger(__name__)

LIVEAVATAR_TOKEN_URL = "https://api.liveavatar.com/v1/sessions/token"


class LiveAvatarStreamService(StreamingAvatarProvider):
    """LiveAvatar 实时流式数字人服务（FULL 模式）。"""

    @property
    def provider_name(self) -> str:
        return "liveavatar"

    async def create_session(self, avatar_id: str | None = None) -> AvatarSessionInfo:
        """创建 LiveAvatar FULL 模式会话，返回 session token。"""
        api_key = settings.liveavatar_api_key
        if not api_key:
            raise HTTPException(status_code=503, detail="LiveAvatar API Key 未配置")

        aid = avatar_id or settings.liveavatar_avatar_id or settings.heygen_avatar_id
        payload = {
            "mode": "FULL",
            "avatar_id": aid,
            "is_sandbox": False,
            "video_settings": {"quality": "high", "encoding": "H264"},
            "avatar_persona": {
                "language": "zh",
            },
        }

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    LIVEAVATAR_TOKEN_URL,
                    headers={
                        "accept": "application/json",
                        "content-type": "application/json",
                        "x-api-key": api_key,
                    },
                    json=payload,
                    timeout=30.0,
                )
                resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            logger.error("LiveAvatar create session failed: %s %s", e.response.status_code, e.response.text[:300])
            raise HTTPException(status_code=502, detail="LiveAvatar 服务暂时不可用") from e
        except httpx.RequestError as e:
            logger.error("LiveAvatar network error: %s", e)
            raise HTTPException(status_code=502, detail="LiveAvatar 服务不可用") from e

        body = resp.json()
        data = body.get("data", body)
        session_token = data.get("session_token") or data.get("token", "")
        session_id = str(data.get("session_id", ""))

        if not session_token:
            logger.error("LiveAvatar: no session_token in response: %s", body)
            raise HTTPException(status_code=502, detail="LiveAvatar 会话创建失败")

        return AvatarSessionInfo(
            session_token=session_token,
            session_id=session_id,
            provider="liveavatar",
        )
