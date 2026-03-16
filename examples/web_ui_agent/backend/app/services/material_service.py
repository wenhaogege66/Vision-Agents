"""材料管理服务：材料上传、版本管理、查询（Supabase Storage + DB）"""

import logging
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
    ) -> MaterialUploadResponse:
        """上传文件到 Supabase Storage，记录版本信息。

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
        storage_path = f"{project_id}/{material_type}/v{next_version}_{filename}"
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
        return self._to_upload_response(row)

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
                .maybe_single()
                .execute()
            )
        except Exception as exc:
            logger.exception("查询最新材料失败")
            raise HTTPException(
                status_code=500, detail=f"查询材料失败: {exc}"
            ) from exc

        return result.data if result.data else None

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
