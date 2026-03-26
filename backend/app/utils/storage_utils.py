"""Supabase Storage 工具函数：下载文件并上传到 DashScope 临时 OSS。

解决通义千问 API 无法直接访问 Supabase Storage 公开 URL 的问题，
同时绕过 DashScope 10MB base64 限制。

流程：Supabase Storage → 后端下载 → 上传到 DashScope 临时 OSS → 获取 oss:// URL
"""

import logging
from pathlib import PurePosixPath

from supabase import Client

from app.utils.dashscope_upload import upload_bytes_to_dashscope

logger = logging.getLogger(__name__)


def _extract_filename(file_path: str) -> str:
    """从存储路径中提取文件名。"""
    return PurePosixPath(file_path).name


async def download_and_upload_to_dashscope(
    supabase: Client,
    bucket: str,
    file_path: str,
    model: str | None = None,
) -> str:
    """从 Supabase Storage 下载文件，上传到 DashScope 临时 OSS，返回 oss:// URL。

    Args:
        supabase: Supabase 客户端
        bucket: Storage bucket 名称
        file_path: 文件在 bucket 中的路径
        model: DashScope 目标模型名称

    Returns:
        oss:// 格式的临时 URL（有效期 48 小时）
    """
    # 1. 从 Supabase 下载
    try:
        content = supabase.storage.from_(bucket).download(file_path)
    except Exception as exc:
        logger.error("Supabase Storage 下载失败: bucket=%s, path=%s, error=%s", bucket, file_path, exc)
        raise

    file_name = _extract_filename(file_path)
    logger.info("文件下载成功: %s (%.1fMB)", file_path, len(content) / 1024 / 1024)

    # 2. 上传到 DashScope 临时 OSS
    oss_url = await upload_bytes_to_dashscope(content, file_name, model)
    return oss_url
