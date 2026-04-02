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
from app.services.prompt_service import prompt_service

logger = logging.getLogger(__name__)

HEYGEN_VIDEO_GENERATE_URL = "https://api.heygen.com/v2/video/generate"
HEYGEN_NEW_VIDEO_URL = "https://api.heygen.com/v2/videos"
HEYGEN_VIDEO_STATUS_URL = "https://api.heygen.com/v1/video_status.get"
HEYGEN_VOICES_URL = "https://api.heygen.com/v2/voices"
HEYGEN_TALKING_PHOTOS_URL = "https://api.heygen.com/v1/talking_photo.list"
HEYGEN_AVATAR_GROUPS_URL = "https://api.heygen.com/v2/avatar_group.list"
HEYGEN_AVATAR_GROUP_AVATARS_URL = "https://api.heygen.com/v2/avatar_group"
HEYGEN_ASSET_URL = "https://upload.heygen.com/v1/asset"
HEYGEN_PHOTO_AVATAR_URL = "https://api.heygen.com/v2/photo_avatar/photo/generate"
HEYGEN_PHOTO_AVATAR_STATUS_URL = "https://api.heygen.com/v2/photo_avatar/photo"


class HeyGenVideoService(VideoAvatarProvider):
    """HeyGen 视频生成型数字人服务。"""

    @property
    def provider_name(self) -> str:
        return "heygen"

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
        """调用 HeyGen POST /v2/videos 生成数字人视频。

        Photo Avatar: 附加 motion_prompt + expressiveness
        Digital Twin: 省略 motion_prompt + expressiveness
        """
        if not settings.heygen_api_key:
            raise HTTPException(status_code=503, detail="HeyGen API Key 未配置")

        aid = avatar_id or settings.heygen_video_avatar_id
        vid = voice_id or settings.heygen_video_voice_id

        payload: dict = {
            "avatar_id": aid,
            "script": text,
            "voice_id": vid,
            "voice_settings": {"locale": voice_locale},
            "resolution": resolution,
            "aspect_ratio": aspect_ratio,
            "remove_background": remove_background,
        }

        # Photo Avatar: add motion_prompt and expressiveness
        if avatar_type == "photo_avatar":
            motion_prompt = prompt_service.load_defense_template("motion_prompt")
            payload["motion_prompt"] = motion_prompt
            payload["expressiveness"] = expressiveness

        logger.info(
            "HeyGen video generate (v2/videos): avatar_id=%s, voice_id=%s, avatar_type=%s, text_len=%d",
            aid, vid, avatar_type, len(text),
        )

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    HEYGEN_NEW_VIDEO_URL,
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

    async def upload_asset(self, image_bytes: bytes, filename: str = "bg.png") -> str:
        """通过 POST https://upload.heygen.com/v1/asset 上传图片资源，返回 asset_id。

        HeyGen Asset API 要求 raw binary body + Content-Type header。
        """
        if not settings.heygen_api_key:
            raise HTTPException(status_code=503, detail="HeyGen API Key 未配置")

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    HEYGEN_ASSET_URL,
                    headers={
                        "X-Api-Key": settings.heygen_api_key,
                        "Content-Type": "image/png",
                    },
                    content=image_bytes,
                    timeout=30.0,
                )
                resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            logger.error("HeyGen asset upload failed: %s %s", e.response.status_code, e.response.text[:500])
            raise HTTPException(status_code=502, detail="HeyGen 资源上传失败") from e
        except httpx.RequestError as e:
            logger.error("HeyGen asset upload network error: %s", e)
            raise HTTPException(status_code=502, detail="HeyGen 服务不可用") from e

        body = resp.json()
        asset_id = body.get("data", {}).get("asset_id") or body.get("data", {}).get("id")
        if not asset_id:
            err_msg = body.get("error") or body.get("message") or str(body)
            logger.error("HeyGen asset upload: no asset_id. response=%s", err_msg[:300])
            raise HTTPException(status_code=502, detail=f"HeyGen 资源上传响应异常: {err_msg[:100]}")

        logger.info("HeyGen asset upload success: asset_id=%s", asset_id)
        return asset_id

    async def generate_multi_scene_video(
        self,
        scenes: list[dict],
        avatar_id: str,
        voice_id: str,
        avatar_type: str,
        resolution: str = "720p",
        aspect_ratio: str = "16:9",
        expressiveness: str = "medium",
        voice_locale: str = "zh-CN",
    ) -> AvatarVideoResult:
        """使用 Studio API (POST /v2/video/generate) 生成多场景视频。

        scenes format:
        [
            {"text": str, "background_asset_id": str | None},
            ...
        ]
        First scene (intro) has background_asset_id=None → use color background "#1a1a2e"
        Subsequent scenes have background_asset_id → use image background with avatar scaled/offset
        """
        if not settings.heygen_api_key:
            raise HTTPException(status_code=503, detail="HeyGen API Key 未配置")

        # Build video_inputs from scenes
        video_inputs: list[dict] = []
        for scene in scenes:
            text = scene["text"]
            bg_asset_id = scene.get("background_asset_id")

            # Character config
            character: dict = {
                "type": "avatar",
                "avatar_id": avatar_id,
            }

            if bg_asset_id is None:
                # Intro scene: full-size avatar, color background
                character["scale"] = 1.0
                background: dict = {"type": "color", "value": "#1a1a2e"}
            else:
                # Question scene: scaled-down avatar offset to the left, image background
                character["scale"] = 0.6
                character["offset"] = {"x": -0.3, "y": 0.0}
                background = {"type": "image", "image_asset_id": bg_asset_id}

            # Voice config
            voice: dict = {
                "type": "text",
                "input_text": text,
                "voice_id": voice_id,
            }
            if voice_locale:
                voice["voice_settings"] = {"locale": voice_locale}

            video_inputs.append({
                "character": character,
                "voice": voice,
                "background": background,
            })

        # Map resolution to dimension
        dimension_map = {
            "1080p": {"width": 1920, "height": 1080},
            "720p": {"width": 1280, "height": 720},
        }
        dimension = dimension_map.get(resolution, {"width": 1280, "height": 720})

        # Swap width/height for 9:16 aspect ratio
        if aspect_ratio == "9:16":
            dimension = {"width": dimension["height"], "height": dimension["width"]}

        payload: dict = {
            "video_inputs": video_inputs,
            "dimension": dimension,
        }

        logger.info(
            "HeyGen multi-scene video generate (Studio API): avatar_id=%s, voice_id=%s, scenes=%d, resolution=%s",
            avatar_id, voice_id, len(scenes), resolution,
        )

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
            logger.error("HeyGen multi-scene video generate failed: %s %s", e.response.status_code, e.response.text[:500])
            raise HTTPException(status_code=502, detail="HeyGen 多场景视频生成失败") from e
        except httpx.RequestError as e:
            logger.error("HeyGen multi-scene video generate network error: %s", e)
            raise HTTPException(status_code=502, detail="HeyGen 服务不可用") from e

        body = resp.json()
        video_id = body.get("data", {}).get("video_id")
        if not video_id:
            err_msg = body.get("error") or body.get("message") or str(body)
            logger.error("HeyGen multi-scene video generate: no video_id. response=%s", err_msg[:300])
            raise HTTPException(status_code=502, detail=f"HeyGen 多场景视频生成响应异常: {err_msg[:100]}")

        logger.info("HeyGen multi-scene video generate success: video_id=%s", video_id)
        return AvatarVideoResult(video_id=video_id, status="pending", provider="heygen")

    async def list_voices(self) -> list[dict]:
        """列出所有可用的 HeyGen 语音（实时获取，按 API 默认顺序，用户自己的声音在前）。"""
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
                "support_pause": v.get("support_pause", False),
                "emotion_support": v.get("emotion_support", False),
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

    @staticmethod
    def _map_avatar_type(raw_type: str) -> str:
        """Map HeyGen API avatar_type to our internal type.

        ``video_avatar`` → ``digital_twin``, ``photo_avatar`` stays as-is,
        anything else defaults to ``digital_twin``.
        """
        if raw_type == "video_avatar":
            return "digital_twin"
        if raw_type == "photo_avatar":
            return "photo_avatar"
        return "digital_twin"

    async def list_avatars(self) -> list[dict]:
        """列出用户自有的 HeyGen Avatars（通过 avatar_group API）。

        只获取用户自己的 avatar（包括 photo avatar 和 digital twins），
        不再获取公共 avatar，这样速度快且能实时反映 HeyGen 官网的更新。

        返回格式：
        {
            "id": str,
            "name": str,
            "preview_image_url": str,
            "avatar_type": str,  # "photo_avatar" | "digital_twin"
            "is_custom": bool,
            "group_id": str,
            "group_name": str,
            "default_voice_id": str | None,
        }
        """
        if not settings.heygen_api_key:
            raise HTTPException(status_code=503, detail="HeyGen API Key 未配置")

        headers = {"X-Api-Key": settings.heygen_api_key, "Accept": "application/json"}
        result: list[dict] = []
        seen_ids: set[str] = set()

        # 1. 获取所有 avatar group
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(HEYGEN_AVATAR_GROUPS_URL, headers=headers, timeout=15.0)
                resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            logger.error("获取 avatar groups 失败: %s %s", e.response.status_code, e.response.text[:500])
            raise HTTPException(status_code=502, detail="获取 Avatar 分组列表失败") from e
        except httpx.RequestError as e:
            logger.error("获取 avatar groups 网络错误: %s", e)
            raise HTTPException(status_code=502, detail="HeyGen 服务不可用") from e

        groups = resp.json().get("data", {}).get("avatar_group_list", [])

        # 2. 遍历每个 group，获取组内 avatar
        for group in groups:
            if not isinstance(group, dict):
                continue
            group_id = group.get("id", "")
            group_name = group.get("name", "")
            group_type = group.get("group_type", "")
            preview_image = group.get("preview_image", "")
            default_voice_id = group.get("default_voice_id")

            # group_type: "PHOTO" = Photo Avatar, 其他 (如 "PRIVATE") = Digital Twin
            avatar_type = "photo_avatar" if group_type == "PHOTO" else "digital_twin"

            try:
                async with httpx.AsyncClient() as client:
                    group_resp = await client.get(
                        f"{HEYGEN_AVATAR_GROUP_AVATARS_URL}/{group_id}/avatars",
                        headers=headers,
                        timeout=15.0,
                    )
                    group_resp.raise_for_status()
                resp_data = group_resp.json().get("data", {})
                avatar_list = resp_data.get("avatar_list", []) or resp_data.get("avatars", [])

                for a in avatar_list:
                    if not isinstance(a, dict):
                        continue
                    aid = a.get("id", "") or a.get("avatar_id", "")
                    if not aid or aid in seen_ids:
                        continue
                    seen_ids.add(aid)
                    result.append({
                        "id": aid,
                        "name": a.get("name", "") or a.get("avatar_name", "") or group_name,
                        "preview_image_url": a.get("image_url", "") or a.get("preview_image_url", "") or preview_image,
                        "avatar_type": avatar_type,
                        "is_custom": True,
                        "group_id": group_id,
                        "group_name": group_name,
                        "default_voice_id": a.get("default_voice_id") or default_voice_id,
                    })
            except Exception:
                logger.warning("获取 avatar group %s (%s) 内 avatar 失败", group_id, group_name, exc_info=True)

        return result

    async def create_photo_avatar(self, params: dict) -> dict:
        """调用 POST /v2/photo_avatar/photo/generate 创建 Photo Avatar。"""
        if not settings.heygen_api_key:
            raise HTTPException(status_code=503, detail="HeyGen API Key 未配置")

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    HEYGEN_PHOTO_AVATAR_URL,
                    headers={
                        "X-Api-Key": settings.heygen_api_key,
                        "Content-Type": "application/json",
                    },
                    json=params,
                    timeout=30.0,
                )
                resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            logger.error("HeyGen create photo avatar failed: %s %s", e.response.status_code, e.response.text[:500])
            raise HTTPException(status_code=502, detail="HeyGen Photo Avatar 创建失败") from e
        except httpx.RequestError as e:
            logger.error("HeyGen create photo avatar network error: %s", e)
            raise HTTPException(status_code=502, detail="HeyGen 服务不可用") from e

        body = resp.json()
        generation_id = body.get("data", {}).get("generation_id")
        if not generation_id:
            err_msg = body.get("error") or body.get("message") or str(body)
            logger.error("HeyGen create photo avatar: no generation_id. response=%s", err_msg[:300])
            raise HTTPException(status_code=502, detail=f"HeyGen Photo Avatar 创建响应异常: {err_msg[:100]}")

        logger.info("HeyGen create photo avatar success: generation_id=%s", generation_id)
        return {"generation_id": generation_id}

    async def check_photo_avatar_status(self, generation_id: str) -> dict:
        """调用 GET /v2/photo_avatar/photo/{generation_id} 查询创建状态。"""
        if not settings.heygen_api_key:
            raise HTTPException(status_code=503, detail="HeyGen API Key 未配置")

        url = f"{HEYGEN_PHOTO_AVATAR_STATUS_URL}/{generation_id}"
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    url,
                    headers={"X-Api-Key": settings.heygen_api_key, "Accept": "application/json"},
                    timeout=15.0,
                )
                resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            logger.error("HeyGen check photo avatar status failed: %s %s", e.response.status_code, e.response.text[:500])
            raise HTTPException(status_code=502, detail="HeyGen Photo Avatar 状态查询失败") from e
        except httpx.RequestError as e:
            logger.error("HeyGen check photo avatar status network error: %s", e)
            raise HTTPException(status_code=502, detail="HeyGen 服务不可用") from e

        body = resp.json()
        data = body.get("data", {})
        return {
            "generation_id": generation_id,
            "status": data.get("status", "unknown"),
        }
