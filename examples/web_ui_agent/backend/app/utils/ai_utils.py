"""AI API 调用封装：含重试逻辑和超时配置"""

import asyncio
import json as json_mod
import logging
import re

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# 默认超时（秒）
DEFAULT_TEXT_TIMEOUT = 120
DEFAULT_VIDEO_TIMEOUT = 300

# 重试配置
MAX_RETRIES = 2
RETRY_INTERVAL = 2  # 秒

# 文件解析中的特殊重试配置
PARSE_IN_PROGRESS_MAX_RETRIES = 10
PARSE_IN_PROGRESS_INTERVAL = 5  # 秒


class FileParsingError(Exception):
    """DashScope 文件解析失败（不可恢复）。"""

    def __init__(self, file_id: str, message: str) -> None:
        self.file_id = file_id
        self.message = message
        super().__init__(f"文件解析失败 [{file_id}]: {message}")


async def call_ai_api(
    messages: list[dict],
    model: str | None = None,
    timeout: float = DEFAULT_TEXT_TIMEOUT,
    multimodal: bool = True,
) -> dict:
    """调用通义千问 API（DashScope 兼容模式），带自动重试。

    对 "File parsing in progress" 错误会自动等待重试（最多 50 秒）。
    对 "File parsing error" 错误会抛出 FileParsingError。

    Args:
        messages: OpenAI 格式的消息列表
        model: 模型名称，默认使用 settings.dashscope_model
        timeout: 请求超时时间（秒）
        multimodal: 是否使用多模态 API 地址

    Returns:
        API 响应 JSON（dict）

    Raises:
        FileParsingError: 文件解析失败（不可恢复）
        RuntimeError: 重试耗尽后仍失败
    """
    if model is None:
        model = settings.dashscope_model
    api_url = settings.dashscope_multimodal_url if multimodal else settings.dashscope_text_url
    headers = {
        "Authorization": f"Bearer {settings.dashscope_api_key}",
        "Content-Type": "application/json",
        "X-DashScope-OssResourceResolve": "enable",
    }
    payload = {
        "model": model,
        "messages": messages,
    }

    last_error: Exception | None = None

    payload_size = len(json_mod.dumps(payload))
    logger.info(
        "AI API 请求: url=%s, model=%s, payload_size=%.1fKB, timeout=%ds",
        api_url, model, payload_size / 1024, timeout,
    )

    total_attempts = MAX_RETRIES + 1 + PARSE_IN_PROGRESS_MAX_RETRIES
    parse_wait_count = 0

    for attempt in range(1, total_attempts + 1):
        try:
            timeouts = httpx.Timeout(timeout, connect=30.0)
            async with httpx.AsyncClient(timeout=timeouts) as client:
                response = await client.post(api_url, headers=headers, json=payload)
                response.raise_for_status()
                return response.json()

        except httpx.HTTPStatusError as exc:
            resp_text = exc.response.text[:500]
            last_error = exc

            # 文件解析失败（不可恢复）— 立即抛出
            if exc.response.status_code == 400 and "parsing error" in resp_text.lower():
                # 提取 file-id
                fid_match = re.search(r"file[- ]?\[?id:?\s*([^\]\s,]+)", resp_text, re.IGNORECASE)
                fid = fid_match.group(1) if fid_match else "unknown"
                raise FileParsingError(fid, resp_text) from exc

            # 文件解析中（可恢复）— 等待后重试
            if exc.response.status_code == 400 and "parsing in progress" in resp_text.lower():
                parse_wait_count += 1
                if parse_wait_count <= PARSE_IN_PROGRESS_MAX_RETRIES:
                    logger.info(
                        "文件解析中，%d 秒后重试 (%d/%d)...",
                        PARSE_IN_PROGRESS_INTERVAL, parse_wait_count, PARSE_IN_PROGRESS_MAX_RETRIES,
                    )
                    await asyncio.sleep(PARSE_IN_PROGRESS_INTERVAL)
                    continue
                else:
                    logger.error("文件解析等待超时，已等待 %d 次", parse_wait_count)
                    raise RuntimeError(f"文件解析等待超时: {resp_text}") from exc

            # 其他 HTTP 错误 — 常规重试
            error_detail = f"HTTP {exc.response.status_code}: {resp_text[:200]}"
            normal_attempt = attempt - parse_wait_count
            if normal_attempt <= MAX_RETRIES:
                logger.warning("AI API 调用失败 (第 %d 次)，%d 秒后重试: %s", normal_attempt, RETRY_INTERVAL, error_detail)
                await asyncio.sleep(RETRY_INTERVAL)
            else:
                logger.error("AI API 调用失败，已耗尽重试次数: %s", error_detail)
                break

        except (httpx.TimeoutException, httpx.ConnectError, httpx.ReadError) as exc:
            last_error = exc
            error_detail = f"{type(exc).__name__}: {exc}"
            normal_attempt = attempt - parse_wait_count
            if normal_attempt <= MAX_RETRIES:
                logger.warning("AI API 调用失败 (第 %d 次)，%d 秒后重试: %s", normal_attempt, RETRY_INTERVAL, error_detail)
                await asyncio.sleep(RETRY_INTERVAL)
            else:
                logger.error("AI API 调用失败，已耗尽重试次数: %s", error_detail)
                break

    raise RuntimeError(f"AI API 调用失败，已重试: {last_error}")
