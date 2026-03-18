"""Supabase Storage 工具函数：下载文件并转 base64 编码。

解决通义千问 API 无法直接访问 Supabase Storage 公开 URL 的问题，
改为后端先下载文件再以 base64 data URI 传给 AI API。
"""

import base64
import logging
import mimetypes

from supabase import Client

logger = logging.getLogger(__name__)

# 常见文件扩展名到 MIME 类型的映射
_MIME_MAP: dict[str, str] = {
    ".pdf": "application/pdf",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".ppt": "application/vnd.ms-powerpoint",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".mp4": "video/mp4",
    ".avi": "video/x-msvideo",
    ".mov": "video/quicktime",
}


def _guess_mime(file_path: str) -> str:
    """根据文件路径猜测 MIME 类型。"""
    ext = "." + file_path.rsplit(".", 1)[-1].lower() if "." in file_path else ""
    if ext in _MIME_MAP:
        return _MIME_MAP[ext]
    guessed, _ = mimetypes.guess_type(file_path)
    return guessed or "application/octet-stream"


def download_file_as_base64_data_uri(
    supabase: Client,
    bucket: str,
    file_path: str,
) -> str:
    """从 Supabase Storage 下载文件并返回 base64 data URI。

    使用 Supabase SDK 的 download 方法（走认证通道），
    不依赖公网 URL 可达性。

    Args:
        supabase: Supabase 客户端
        bucket: Storage bucket 名称
        file_path: 文件在 bucket 中的路径

    Returns:
        data URI 字符串，如 "data:image/png;base64,iVBOR..."
    """
    content = supabase.storage.from_(bucket).download(file_path)
    content_type = _guess_mime(file_path)
    b64 = base64.b64encode(content).decode("ascii")
    return f"data:{content_type};base64,{b64}"
