"""HeyGen 视频生成服务：通过 v2/video/generate 生成数字人视频。"""

import logging

import httpx
from fastapi import HTTPException

from app.config import settings
from app.services.avatar.base import AvatarVideoResult, VideoAvatarProvider

logger = logging.getLogger(__name__)

HEYGEN_VIDEO_GENERATE_URL = "https://api.heygen.com/v2/video/generate"
HEYGEN_VIDEO_STATUS_URL = "https://api.heygen.com/v1/video_status.get"


class HeyGenVideoService(VideoAvatarProvider):
    """HeyGen 视频生成型数字人服务。"""

    @property
    def provider_name(self) -> str:
        return "heygen"

    async def generate_video(self, text: str, avatar_id: str | None = None) -> AvatarVideoResult:
        """调用 HeyGen v2/video/generate 生成数字人视频。"""
        if not settings.heygen_api_key:
            raise HTTPException(status_code=503, detail="HeyGen API Key 未配置")

        aid = avatar_id or settings.heygen_avatar_id
        payload = {
            "video_inputs": [
                {
                    "character": {
                        "type": "avatar",
                        "avatar_id": aid,
                        "avatar_style": "normal",
                    },
                    "voice": {
                        "type": "text",
                        "input_text": text,
                        "voice_id": "zh-CN-XiaoxiaoNeural",
                    },
                }
            ],
            "dimension": {"width": 720, "height": 480},
        }

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    HEYGEN_VIDEO_GENERATE_URL,
                    headers={
                        "X-Api-Key": settings.heygen_api_key,
                        "Content-Type": "application/json",
                    },
                    json=payload,
                    timeout=30.0,
                )
                resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            logger.error("HeyGen video generate failed: %s %s", e.response.status_code, e.response.text[:200])
            raise HTTPException(status_code=502, detail="HeyGen 视频生成失败") from e
        except httpx.RequestError as e:
            logger.error("HeyGen video generate network error: %s", e)
            raise HTTPException(status_code=502, detail="HeyGen 服务不可用") from e

        data = resp.json()
        video_id = data.get("data", {}).get("video_id")
        if not video_id:
            logger.error("HeyGen video generate: no video_id in response: %s", data)
            raise HTTPException(status_code=502, detail="HeyGen 视频生成响应异常")

        return AvatarVideoResult(video_id=video_id, status="pending", provider="heygen")

    async def check_video_status(self, video_id: str) -> AvatarVideoResult:
        """查询 HeyGen 视频生成状态。"""
        if not settings.heygen_api_key:
            raise HTTPException(status_code=503, detail="HeyGen API Key 未配置")

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    HEYGEN_VIDEO_STATUS_URL,
                    params={"video_id": video_id},
                    headers={"X-Api-Key": settings.heygen_api_key},
                    timeout=15.0,
                )
                resp.raise_for_status()
        except (httpx.HTTPStatusError, httpx.RequestError) as e:
            logger.error("HeyGen video status check failed: %s", e)
            raise HTTPException(status_code=502, detail="HeyGen 视频状态查询失败") from e

        data = resp.json().get("data", {})
        return AvatarVideoResult(
            video_id=video_id,
            status=data.get("status", "unknown"),
            video_url=data.get("video_url"),
            provider="heygen",
        )
