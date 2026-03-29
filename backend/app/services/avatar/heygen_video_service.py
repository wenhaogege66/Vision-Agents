"""HeyGen 视频生成服务：通过 v2/video/generate 生成数字人视频。

注意：Video API 使用的 avatar_id 和 voice_id 与 Interactive Avatar / LiveAvatar 不同。
- Video avatar_id: 如 "Abigail_expressive_2024112501"（通过 GET /v2/avatars 获取）
- Video voice_id: 如 "de6ad44022104ac0872392d1139e9364"（通过 GET /v2/voices 获取）
- Interactive Avatar ID（如 "80d4afa941c243beb0a1116c95ea48ee"）不能用于 Video API。
"""

import logging

import httpx
from fastapi import HTTPException

from app.config import settings
from app.services.avatar.base import AvatarVideoResult, VideoAvatarProvider

logger = logging.getLogger(__name__)

HEYGEN_VIDEO_GENERATE_URL = "https://api.heygen.com/v2/video/generate"
HEYGEN_VIDEO_STATUS_URL = "https://api.heygen.com/v1/video_status.get"
HEYGEN_VOICES_URL = "https://api.heygen.com/v2/voices"
HEYGEN_TALKING_PHOTOS_URL = "https://api.heygen.com/v1/talking_photo.list"
HEYGEN_AVATARS_URL = "https://api.heygen.com/v2/avatars"


class HeyGenVideoService(VideoAvatarProvider):
    """HeyGen 视频生成型数字人服务。"""

    @property
    def provider_name(self) -> str:
        return "heygen"

    async def generate_video(self, text: str, avatar_id: str | None = None, voice_id: str | None = None) -> AvatarVideoResult:
        """调用 HeyGen v2/video/generate 生成数字人视频。"""
        if not settings.heygen_api_key:
            raise HTTPException(status_code=503, detail="HeyGen API Key 未配置")

        # 使用 Video API 专用的 avatar_id 和 voice_id
        aid = avatar_id or settings.heygen_video_avatar_id
        vid = voice_id or settings.heygen_video_voice_id

        # 判断 character type：如果 ID 是 hex 格式（32位）则为 talking_photo，否则为 avatar
        is_talking_photo = len(aid) == 32 and all(c in '0123456789abcdef' for c in aid)

        if is_talking_photo:
            character = {
                "type": "talking_photo",
                "talking_photo_id": aid,
                "talking_style": settings.heygen_video_talking_style,
            }
        else:
            character = {
                "type": "avatar",
                "avatar_id": aid,
                "avatar_style": "normal",
            }

        payload = {
            "video_inputs": [
                {
                    "character": character,
                    "voice": {
                        "type": "text",
                        "input_text": text,
                        "voice_id": vid,
                    },
                }
            ],
            "dimension": {"width": 720, "height": 480},
            "caption": settings.heygen_video_caption,
        }

        logger.info("HeyGen video generate: avatar_id=%s, voice_id=%s, text_len=%d", aid, vid, len(text))

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
            logger.error("HeyGen video generate failed: %s %s", e.response.status_code, e.response.text[:500])
            raise HTTPException(status_code=502, detail="HeyGen 视频生成失败") from e
        except httpx.RequestError as e:
            logger.error("HeyGen video generate network error: %s", e)
            raise HTTPException(status_code=502, detail="HeyGen 服务不可用") from e

        body = resp.json()
        video_id = body.get("data", {}).get("video_id")
        if not video_id:
            err_msg = body.get("error") or body.get("message") or str(body)
            logger.error("HeyGen video generate: no video_id. response=%s", err_msg[:300])
            raise HTTPException(status_code=502, detail=f"HeyGen 视频生成响应异常: {err_msg[:100]}")

        logger.info("HeyGen video generate success: video_id=%s", video_id)
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

        body = resp.json()
        data = body.get("data", {})
        status = data.get("status", "unknown")
        video_url = data.get("video_url")
        error = data.get("error")

        if status == "failed":
            logger.warning("HeyGen video %s failed: %s", video_id, error)

        return AvatarVideoResult(
            video_id=video_id,
            status=status,
            video_url=video_url,
            provider="heygen",
        )

    async def list_voices(self) -> list[dict]:
        """列出所有可用的 HeyGen 语音。"""
        if not settings.heygen_api_key:
            raise HTTPException(status_code=503, detail="HeyGen API Key 未配置")
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    HEYGEN_VOICES_URL,
                    headers={"X-Api-Key": settings.heygen_api_key, "Accept": "application/json"},
                    timeout=15.0,
                )
                resp.raise_for_status()
        except (httpx.HTTPStatusError, httpx.RequestError) as e:
            logger.error("HeyGen list voices failed: %s", e)
            raise HTTPException(status_code=502, detail="获取语音列表失败") from e
        body = resp.json()
        data = body.get("data", {})
        voices = data.get("voices", []) if isinstance(data, dict) else data if isinstance(data, list) else []
        return [
            {
                "voice_id": v.get("voice_id", ""),
                "name": v.get("name") or v.get("display_name", ""),
                "language": v.get("language", ""),
                "gender": v.get("gender", ""),
                "preview_audio": v.get("preview_audio", ""),
                "is_custom": v.get("is_custom", False),
            }
            for v in voices
            if isinstance(v, dict)
        ]

    async def list_talking_photos(self) -> list[dict]:
        """列出所有可用的 HeyGen Talking Photos。"""
        if not settings.heygen_api_key:
            raise HTTPException(status_code=503, detail="HeyGen API Key 未配置")
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    HEYGEN_TALKING_PHOTOS_URL,
                    headers={"X-Api-Key": settings.heygen_api_key, "Accept": "application/json"},
                    timeout=15.0,
                )
                resp.raise_for_status()
        except (httpx.HTTPStatusError, httpx.RequestError) as e:
            logger.error("HeyGen list talking photos failed: %s", e)
            raise HTTPException(status_code=502, detail="获取 Talking Photos 列表失败") from e
        body = resp.json()
        # v1 API: data 可能直接是 list，也可能是 {"talking_photos": [...]}
        data = body.get("data", [])
        if isinstance(data, dict):
            photos = data.get("talking_photos", [])
        elif isinstance(data, list):
            photos = data
        else:
            photos = []
        return [
            {
                "id": p.get("talking_photo_id", ""),
                "name": p.get("talking_photo_name", ""),
                "preview_image_url": p.get("preview_image_url") or p.get("image_url", ""),
                "type": "talking_photo",
            }
            for p in photos
            if isinstance(p, dict)
        ]

    async def list_avatars(self) -> list[dict]:
        """列出所有可用的 HeyGen Avatars。"""
        if not settings.heygen_api_key:
            raise HTTPException(status_code=503, detail="HeyGen API Key 未配置")
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    HEYGEN_AVATARS_URL,
                    headers={"X-Api-Key": settings.heygen_api_key, "Accept": "application/json"},
                    timeout=15.0,
                )
                resp.raise_for_status()
        except (httpx.HTTPStatusError, httpx.RequestError) as e:
            logger.error("HeyGen list avatars failed: %s", e)
            raise HTTPException(status_code=502, detail="获取 Avatar 列表失败") from e
        body = resp.json()
        data = body.get("data", {})
        avatars = data.get("avatars", []) if isinstance(data, dict) else data if isinstance(data, list) else []
        return [
            {
                "id": a.get("avatar_id", ""),
                "name": a.get("avatar_name", ""),
                "preview_image_url": a.get("preview_image_url", ""),
                "type": "avatar",
            }
            for a in avatars
            if isinstance(a, dict)
        ]
