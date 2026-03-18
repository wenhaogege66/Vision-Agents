"""材料管理服务：材料上传、版本管理、查询（Supabase Storage + DB）"""

import logging
import os
import uuid
from datetime import datetime

from fastapi import HTTPException, UploadFile
from supabase import Client

from app.models.schemas import MaterialUploadResponse
from app.utils.file_utils import validate_file_format, validate_file_size

logger = logging.getLogger(__name__)

# Supabase Storage bucket 名称
STORAGE_BUCKET = "materials"


class MaterialService:
    """封装项目材料的上传、版本管理和查询操作"""

    def __init__(self, supabase: Client) -> None:
        self._sb = supabase

    # ── 上传材料 ──────────────────────────────────────────────

    async def upload(
        self, project_id: str, material_type: str, file: UploadFile
    ) -> tuple[MaterialUploadResponse, str]:
        """上传文件到 Supabase Storage，记录版本信息。

        Returns:
            (MaterialUploadResponse, storage_path) 元组

        流程：
        1. 验证文件格式和大小
        2. 计算新版本号
        3. 上传文件到 Storage
        4. 将旧版本 is_latest 设为 false
        5. 插入新版本记录（is_latest = true）
        """
        filename = file.filename or "unknown"

        # 1. 验证文件格式
        ok, err = validate_file_format(filename, material_type)
        if not ok:
            raise HTTPException(status_code=400, detail=err)

        # 读取文件内容并验证大小
        content = await file.read()
        file_size = len(content)

        ok, err = validate_file_size(file_size, material_type)
        if not ok:
            raise HTTPException(status_code=413, detail=err)

        # 2. 计算新版本号
        next_version = await self._next_version(project_id, material_type)

        # 3. 上传文件到 Supabase Storage
        # Storage path 只使用 ASCII 安全字符（UUID），避免中文文件名导致 InvalidKey 错误
        ext = os.path.splitext(filename)[1].lower()  # e.g. ".pdf", ".pptx"
        safe_name = f"v{next_version}_{uuid.uuid4().hex[:8]}{ext}"
        storage_path = f"{project_id}/{material_type}/{safe_name}"
        try:
            self._sb.storage.from_(STORAGE_BUCKET).upload(
                path=storage_path,
                file=content,
                file_options={"content-type": file.content_type or "application/octet-stream"},
            )
        except Exception as exc:
            logger.exception("上传文件到 Storage 失败")
            raise HTTPException(
                status_code=500, detail=f"文件上传失败: {exc}"
            ) from exc

        # 4. 将旧版本 is_latest 设为 false
        try:
            self._sb.table("project_materials").update(
                {"is_latest": False}
            ).eq("project_id", project_id).eq(
                "material_type", material_type
            ).eq("is_latest", True).execute()
        except Exception as exc:
            logger.exception("更新旧版本 is_latest 失败")
            raise HTTPException(
                status_code=500, detail=f"更新版本状态失败: {exc}"
            ) from exc

        # 5. 插入新版本记录
        try:
            result = (
                self._sb.table("project_materials")
                .insert(
                    {
                        "project_id": project_id,
                        "material_type": material_type,
                        "file_path": storage_path,
                        "file_name": filename,
                        "file_size": file_size,
                        "version": next_version,
                        "is_latest": True,
                    }
                )
                .execute()
            )
        except Exception as exc:
            logger.exception("插入材料记录失败")
            raise HTTPException(
                status_code=500, detail=f"保存材料记录失败: {exc}"
            ) from exc

        row = result.data[0]
        return self._to_upload_response(row), storage_path

    # ── 获取最新版本材料 ──────────────────────────────────────

    async def get_latest(
        self, project_id: str, material_type: str
    ) -> dict | None:
        """获取指定类型的最新版本材料，不存在则返回 None。"""
        try:
            result = (
                self._sb.table("project_materials")
                .select("*")
                .eq("project_id", project_id)
                .eq("material_type", material_type)
                .eq("is_latest", True)
                .limit(1)
                .execute()
            )
        except Exception as exc:
            logger.exception("查询最新材料失败")
            raise HTTPException(
                status_code=500, detail=f"查询材料失败: {exc}"
            ) from exc

        if result and result.data:
            return result.data[0]
        return None

    # ── 获取材料历史版本列表 ──────────────────────────────────

    async def get_versions(
        self, project_id: str, material_type: str
    ) -> list[dict]:
        """获取指定类型材料的所有历史版本，按版本号降序排列。"""
        try:
            result = (
                self._sb.table("project_materials")
                .select("*")
                .eq("project_id", project_id)
                .eq("material_type", material_type)
                .order("version", desc=True)
                .execute()
            )
        except Exception as exc:
            logger.exception("查询材料版本列表失败")
            raise HTTPException(
                status_code=500, detail=f"查询版本列表失败: {exc}"
            ) from exc

        return result.data

    # ── 材料就绪状态查询 ────────────────────────────────────────

    async def get_status(self, project_id: str) -> dict:
        """查询项目各材料类型的上传和就绪状态。

        Returns:
            匹配 MaterialStatusResponse schema 的字典
        """
        try:
            result = (
                self._sb.table("project_materials")
                .select("material_type")
                .eq("project_id", project_id)
                .eq("is_latest", True)
                .execute()
            )
        except Exception as exc:
            logger.exception("查询材料状态失败")
            raise HTTPException(
                status_code=500, detail=f"查询材料状态失败: {exc}"
            ) from exc

        uploaded_types = {row["material_type"] for row in result.data}
        all_types = ["bp", "text_ppt", "presentation_ppt", "presentation_video"]

        status: dict[str, dict] = {}
        for mt in all_types:
            uploaded = mt in uploaded_types
            status[mt] = {"uploaded": uploaded, "ready": uploaded}

        any_text_material_ready = (
            status["bp"]["ready"]
            or status["text_ppt"]["ready"]
            or status["presentation_ppt"]["ready"]
        )

        offline_review_ready = status["presentation_video"]["uploaded"]

        offline_review_reasons: list[str] = []
        if not status["presentation_video"]["uploaded"]:
            offline_review_reasons.append("请先上传路演视频")

        return {
            **status,
            "any_text_material_ready": any_text_material_ready,
            "offline_review_ready": offline_review_ready,
            "offline_review_reasons": offline_review_reasons,
        }

    # ── 材料版本下载 URL ──────────────────────────────────────────

    async def get_download_url(self, project_id: str, material_id: str) -> dict:
        """生成材料文件的签名下载 URL。

        Args:
            project_id: 项目 ID（用于安全校验）
            material_id: 材料记录 ID

        Returns:
            匹配 DownloadUrlResponse schema 的字典

        Raises:
            HTTPException 404: 材料记录不存在或不属于该项目
        """
        try:
            result = (
                self._sb.table("project_materials")
                .select("file_path, file_name")
                .eq("id", material_id)
                .eq("project_id", project_id)
                .limit(1)
                .execute()
            )
        except Exception as exc:
            logger.exception("查询材料记录失败")
            raise HTTPException(
                status_code=500, detail=f"查询材料记录失败: {exc}"
            ) from exc

        if not result.data:
            raise HTTPException(status_code=404, detail="文件不存在或已过期")

        row = result.data[0]
        file_path: str = row["file_path"]
        file_name: str = row["file_name"]

        try:
            signed = self._sb.storage.from_(STORAGE_BUCKET).create_signed_url(
                file_path, 3600
            )
        except Exception as exc:
            logger.exception("生成签名下载 URL 失败")
            raise HTTPException(
                status_code=500, detail=f"生成下载链接失败: {exc}"
            ) from exc

        url = signed.get("signedURL") or signed.get("signedUrl", "")

        return {
            "download_url": url,
            "file_name": file_name,
            "expires_in": 3600,
        }

    # ── 内部辅助方法 ──────────────────────────────────────────

    async def _next_version(self, project_id: str, material_type: str) -> int:
        """计算下一个版本号（当前最大版本 + 1）。"""
        try:
            result = (
                self._sb.table("project_materials")
                .select("version")
                .eq("project_id", project_id)
                .eq("material_type", material_type)
                .order("version", desc=True)
                .limit(1)
                .execute()
            )
        except Exception as exc:
            logger.exception("查询当前最大版本号失败")
            raise HTTPException(
                status_code=500, detail=f"查询版本号失败: {exc}"
            ) from exc

        if result.data:
            return result.data[0]["version"] + 1
        return 1

    @staticmethod
    def _to_upload_response(row: dict) -> MaterialUploadResponse:
        created_at = row.get("created_at", "")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        return MaterialUploadResponse(
            id=row["id"],
            material_type=row["material_type"],
            file_name=row["file_name"],
            version=row["version"],
            created_at=created_at,
        )
