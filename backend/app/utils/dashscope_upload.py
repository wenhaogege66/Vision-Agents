"""DashScope 临时文件上传工具：上传文件到百炼临时 OSS 空间，获取 oss:// URL。

解决 DashScope API 的 10MB base64 限制问题。
上传后的 oss:// URL 有效期 48 小时，调用 API 时需添加
X-DashScope-OssResourceResolve: enable 请求头。

参考文档: https://www.alibabacloud.com/help/en/model-studio/get-temporary-file-url
"""

import logging
from pathlib import Path

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# 获取上传凭证的 API 地址
_UPLOADS_API = "https://dashscope.aliyuncs.com/api/v1/uploads"


async def get_upload_policy(model: str | None = None) -> dict:
    """获取 DashScope 临时文件上传凭证。

    Args:
        model: 目标模型名称，默认使用 settings.dashscope_model

    Returns:
        上传凭证字典，包含 upload_host, upload_dir, policy, signature 等字段
    """
    if model is None:
        model = settings.dashscope_model

    headers = {
        "Authorization": f"Bearer {settings.dashscope_api_key}",
        "Content-Type": "application/json",
    }
    params = {"action": "getPolicy", "model": model}

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(_UPLOADS_API, headers=headers, params=params)
        resp.raise_for_status()
        data = resp.json()

    policy_data = data.get("data")
    if not policy_data:
        raise RuntimeError(f"获取上传凭证失败: {data}")

    logger.info(
        "获取 DashScope 上传凭证成功: upload_host=%s, max_file_size=%sMB",
        policy_data.get("upload_host"),
        policy_data.get("max_file_size_mb"),
    )
    return policy_data


async def upload_bytes_to_dashscope(
    file_bytes: bytes,
    file_name: str,
    model: str | None = None,
) -> str:
    """将文件字节上传到 DashScope 临时 OSS 空间。

    Args:
        file_bytes: 文件内容（bytes）
        file_name: 文件名（用于构建 OSS key）
        model: 目标模型名称

    Returns:
        oss:// 格式的临时 URL，有效期 48 小时
    """
    policy = await get_upload_policy(model)

    key = f"{policy['upload_dir']}/{file_name}"

    # multipart/form-data 上传到 OSS
    # file 字段必须放在最后
    fields = {
        "OSSAccessKeyId": policy["oss_access_key_id"],
        "Signature": policy["signature"],
        "policy": policy["policy"],
        "x-oss-object-acl": policy["x_oss_object_acl"],
        "x-oss-forbid-overwrite": policy["x_oss_forbid_overwrite"],
        "key": key,
        "success_action_status": "200",
    }

    # httpx 的 files 参数会自动构建 multipart
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            policy["upload_host"],
            data=fields,
            files={"file": (file_name, file_bytes)},
        )
        if resp.status_code != 200:
            raise RuntimeError(
                f"上传文件到 DashScope OSS 失败: HTTP {resp.status_code}, {resp.text[:200]}"
            )

    oss_url = f"oss://{key}"
    logger.info(
        "文件上传到 DashScope OSS 成功: %s (%.1fMB) -> %s",
        file_name,
        len(file_bytes) / 1024 / 1024,
        oss_url,
    )
    return oss_url
