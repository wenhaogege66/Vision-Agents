"""HeyGen Streaming Avatar 服务：生成 access token 供前端 SDK 使用。"""

import logging

import httpx
from fastapi import HTTPException

from app.config import settings

logger = logging.getLogger(__name__)

HEYGEN_TOKEN_URL = "https://api.heygen.com/v1/streaming.create_token"


class HeyGenService:
    """HeyGen API 服务，负责生成 streaming access token。"""

    async def create_token(self) -> str:
        """调用 HeyGen API 生成 streaming access token。

        Returns:
            access token 字符串

        Raises:
            HTTPException(503): API Key 未配置
            HTTPException(502): HeyGen API 调用失败
        """
        if not settings.heygen_api_key:
            logger.warning("HEYGEN_API_KEY 未配置，数字人问辩功能不可用")
            raise HTTPException(status_code=503, detail="数字人服务未配置")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    HEYGEN_TOKEN_URL,
                    headers={"x-api-key": settings.heygen_api_key},
                    timeout=30.0,
                )
                response.raise_for_status()
        except httpx.HTTPStatusError as e:
            logger.error("HeyGen API 请求失败: status=%s body=%s", e.response.status_code, e.response.text[:200])
            raise HTTPException(status_code=502, detail="数字人服务暂时不可用，请稍后重试") from e
        except httpx.RequestError as e:
            logger.error("HeyGen API 网络错误: %s", e)
            raise HTTPException(status_code=502, detail="数字人服务暂时不可用，请稍后重试") from e

        data = response.json()
        try:
            token = data["data"]["token"]
        except (KeyError, TypeError) as e:
            logger.error("HeyGen API 响应解析失败: %s", data)
            raise HTTPException(status_code=502, detail="数字人服务响应异常") from e

        return token
