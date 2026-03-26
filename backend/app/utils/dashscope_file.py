"""DashScope 文件上传工具：通过 OpenAI 兼容的 File API 上传文件获取 file-id。

用于 Qwen-Long 模型的文档理解场景（PDF、PPTX、DOCX 等）。
上传后通过 fileid://{file_id} 在 system message 中引用。

支持格式: TXT, DOCX, PDF, XLSX, EPUB, MOBI, MD, CSV, JSON, BMP, PNG, JPG/JPEG, GIF
单文件最大: 图片 20MB，其他 150MB

参考文档: https://www.alibabacloud.com/help/en/model-studio/long-context-qwen-long
"""

import asyncio
import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_FILES_API = "https://dashscope.aliyuncs.com/compatible-mode/v1/files"

# 解析等待配置
_PARSE_CHECK_INTERVAL = 3  # 每次检查间隔（秒）
_PARSE_MAX_WAIT = 60  # 最长等待时间（秒）


async def upload_file_to_dashscope(
    file_bytes: bytes,
    file_name: str,
) -> str:
    """上传文件到 DashScope 存储，返回 file-id。

    Args:
        file_bytes: 文件内容
        file_name: 文件名（含扩展名）

    Returns:
        file-id 字符串，用于 fileid://{id} 引用

    Raises:
        RuntimeError: 上传失败
    """
    headers = {
        "Authorization": f"Bearer {settings.dashscope_api_key}",
    }

    async with httpx.AsyncClient(timeout=180) as client:
        resp = await client.post(
            _FILES_API,
            headers=headers,
            data={"purpose": "file-extract"},
            files={"file": (file_name, file_bytes)},
        )
        resp.raise_for_status()
        data = resp.json()

    file_id = data.get("id")
    if not file_id:
        raise RuntimeError(f"上传文件失败，未返回 file-id: {data}")

    logger.info("文件上传到 DashScope 成功: %s -> file-id=%s", file_name, file_id)
    return file_id
