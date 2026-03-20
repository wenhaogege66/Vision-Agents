"""语音转文字服务：使用 Deepgram REST API 将音频/视频内容转录为文本。"""

import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

SUPPORTED_MIME_TYPES = {
    "audio/mp4",
    "audio/mpeg",
    "audio/wav",
    "audio/x-m4a",
    "audio/aac",
}

DEEPGRAM_API_URL = "https://api.deepgram.com/v1/listen"


class STTService:
    """语音转文字服务，使用 Deepgram API。"""

    def __init__(self):
        self._api_key = settings.deepgram_api_key

    async def transcribe(self, audio_content: bytes, mime_type: str = "audio/mp4") -> str:
        """将音频/视频内容转录为文本。

        Args:
            audio_content: 音频/视频文件的字节内容
            mime_type: MIME 类型，支持 audio/mp4, audio/mpeg, audio/wav, audio/x-m4a, audio/aac

        Returns:
            转录文本

        Raises:
            RuntimeError: API Key 未配置、MIME 类型不支持或转录失败时抛出
        """
        if not self._api_key:
            raise RuntimeError("STT 服务未配置：缺少 DEEPGRAM_API_KEY")

        if mime_type not in SUPPORTED_MIME_TYPES:
            raise RuntimeError(f"不支持的音频格式：{mime_type}")

        params = {
            "language": "zh",
            "model": "nova-2",
            "smart_format": "true",
        }
        headers = {
            "Authorization": f"Token {self._api_key}",
            "Content-Type": mime_type,
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    DEEPGRAM_API_URL,
                    params=params,
                    headers=headers,
                    content=audio_content,
                    timeout=300.0,
                )
                response.raise_for_status()
        except httpx.HTTPStatusError as e:
            logger.error("Deepgram API 请求失败: status=%s body=%s", e.response.status_code, e.response.text)
            raise RuntimeError(f"语音转文字失败：Deepgram API 返回 {e.response.status_code}") from e
        except httpx.RequestError as e:
            logger.error("Deepgram API 网络错误: %s", e)
            raise RuntimeError("语音转文字失败：网络连接错误，请稍后重试") from e

        data = response.json()
        try:
            transcript = data["results"]["channels"][0]["alternatives"][0]["transcript"]
        except (KeyError, IndexError) as e:
            logger.error("Deepgram 响应解析失败: %s", data)
            raise RuntimeError("语音转文字失败：无法解析转录结果") from e

        if not transcript:
            logger.warning("Deepgram 返回空转录文本")

        return transcript
