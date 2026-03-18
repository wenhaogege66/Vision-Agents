"""AI API 调用封装：含重试逻辑和超时配置"""

import asyncio
import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# 默认超时（秒）
DEFAULT_TEXT_TIMEOUT = 60
DEFAULT_VIDEO_TIMEOUT = 120

# 重试配置
MAX_RETRIES = 2
RETRY_INTERVAL = 2  # 秒

# DashScope API 地址从配置读取，支持纯文本和多模态分开配置


async def call_ai_api(
    messages: list[dict],
    model: str | None = None,
    timeout: float = DEFAULT_TEXT_TIMEOUT,
    multimodal: bool = True,
) -> dict:
    """调用通义千问 API（DashScope 兼容模式），带自动重试。

    Args:
        messages: OpenAI 格式的消息列表
        model: 模型名称，默认使用 settings.dashscope_model
        timeout: 请求超时时间（秒）
        multimodal: 是否使用多模态 API 地址

    Returns:
        API 响应 JSON（dict）

    Raises:
        httpx.HTTPStatusError: 非重试范围内的 HTTP 错误
        RuntimeError: 重试耗尽后仍失败
    """
    if model is None:
        model = settings.dashscope_model
    api_url = settings.dashscope_multimodal_url if multimodal else settings.dashscope_text_url
    headers = {
        "Authorization": f"Bearer {settings.dashscope_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": messages,
    }

    last_error: Exception | None = None

    for attempt in range(1, MAX_RETRIES + 2):  # 首次 + 最多 MAX_RETRIES 次重试
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    api_url,
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
                return response.json()

        except (httpx.TimeoutException, httpx.HTTPStatusError, httpx.ConnectError) as exc:
            last_error = exc
            error_detail = str(exc)
            if isinstance(exc, httpx.HTTPStatusError):
                error_detail = f"HTTP {exc.response.status_code}: {exc.response.text[:200]}"
            if attempt <= MAX_RETRIES:
                logger.warning(
                    "AI API 调用失败 (第 %d 次)，%d 秒后重试: %s",
                    attempt,
                    RETRY_INTERVAL,
                    error_detail,
                )
                await asyncio.sleep(RETRY_INTERVAL)
            else:
                logger.error("AI API 调用失败，已耗尽重试次数: %s", error_detail)

    raise RuntimeError(f"AI API 调用失败，已重试 {MAX_RETRIES} 次: {last_error}")
