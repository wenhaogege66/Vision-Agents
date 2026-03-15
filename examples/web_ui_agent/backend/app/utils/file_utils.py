"""文件工具函数：格式验证、大小检查"""

from app.config import settings

# 各材料类型允许的文件扩展名
ALLOWED_EXTENSIONS: dict[str, set[str]] = {
    "bp": {".docx", ".pdf"},
    "text_ppt": {".pptx", ".pdf"},
    "presentation_ppt": {".pptx", ".pdf"},
    "presentation_video": {".mp4", ".webm"},
}

# 各材料类型对应的大小限制键（映射到 settings 属性）
_SIZE_LIMITS: dict[str, str] = {
    "bp": "max_ppt_size",
    "text_ppt": "max_ppt_size",
    "presentation_ppt": "max_ppt_size",
    "presentation_video": "max_video_size",
}


def validate_file_format(filename: str, material_type: str) -> tuple[bool, str]:
    """验证文件扩展名是否符合材料类型要求。

    Args:
        filename: 上传的文件名
        material_type: 材料类型（bp / text_ppt / presentation_ppt / presentation_video）

    Returns:
        (通过, 错误信息)  通过时错误信息为空字符串
    """
    allowed = ALLOWED_EXTENSIONS.get(material_type)
    if allowed is None:
        return False, f"不支持的材料类型: {material_type}"

    # 取最后一个 '.' 之后的部分作为扩展名
    dot_idx = filename.rfind(".")
    if dot_idx == -1:
        ext = ""
    else:
        ext = filename[dot_idx:].lower()

    if ext not in allowed:
        allowed_str = ", ".join(sorted(allowed))
        return False, f"不支持的文件格式 '{ext}'，{material_type} 仅接受: {allowed_str}"

    return True, ""


def validate_file_size(size: int, material_type: str) -> tuple[bool, str]:
    """验证文件大小是否在限制范围内。

    Args:
        size: 文件大小（字节）
        material_type: 材料类型

    Returns:
        (通过, 错误信息)  通过时错误信息为空字符串
    """
    limit_attr = _SIZE_LIMITS.get(material_type)
    if limit_attr is None:
        return False, f"不支持的材料类型: {material_type}"

    max_size: int = getattr(settings, limit_attr)

    if size > max_size:
        max_mb = max_size / (1024 * 1024)
        return False, f"文件大小超过限制，{material_type} 最大允许 {max_mb:.0f}MB"

    return True, ""
