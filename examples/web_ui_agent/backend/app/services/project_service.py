"""项目管理服务：项目CRUD操作（创建、列表、详情、更新）"""

import logging
from datetime import datetime

from fastapi import HTTPException
from supabase import Client

from app.models.schemas import ProjectCreate, ProjectResponse

logger = logging.getLogger(__name__)

# 四大核心材料类型
MATERIAL_TYPES = ("bp", "text_ppt", "presentation_ppt", "presentation_video")


class ProjectService:
    """封装项目管理的数据库操作"""

    def __init__(self, supabase: Client) -> None:
        self._sb = supabase

    # ── 创建项目 ──────────────────────────────────────────────

    async def create(self, user_id: str, data: ProjectCreate) -> ProjectResponse:
        """创建新项目，验证必填字段非空。"""
        # 验证必填字段非空
        errors: list[str] = []
        if not data.name or not data.name.strip():
            errors.append("项目名称不能为空")
        if not data.competition or not data.competition.strip():
            errors.append("赛事类型不能为空")
        if not data.track or not data.track.strip():
            errors.append("赛道不能为空")
        if not data.group or not data.group.strip():
            errors.append("组别不能为空")
        if errors:
            raise HTTPException(status_code=422, detail="；".join(errors))

        try:
            result = (
                self._sb.table("projects")
                .insert(
                    {
                        "user_id": user_id,
                        "name": data.name.strip(),
                        "competition": data.competition.strip(),
                        "track": data.track.strip(),
                        "group": data.group.strip(),
                    }
                )
                .execute()
            )
        except Exception as exc:
            logger.exception("创建项目失败")
            raise HTTPException(status_code=500, detail=f"创建项目失败: {exc}") from exc

        row = result.data[0]
        return self._to_response(row, self._empty_materials_status())

    # ── 项目列表 ──────────────────────────────────────────────

    async def list_projects(self, user_id: str) -> list[ProjectResponse]:
        """列出用户的所有项目，附带材料上传状态。"""
        try:
            result = (
                self._sb.table("projects")
                .select("*")
                .eq("user_id", user_id)
                .order("created_at", desc=True)
                .execute()
            )
        except Exception as exc:
            logger.exception("查询项目列表失败")
            raise HTTPException(status_code=500, detail=f"查询项目列表失败: {exc}") from exc

        projects: list[ProjectResponse] = []
        for row in result.data:
            materials_status = await self._get_materials_status(row["id"])
            projects.append(self._to_response(row, materials_status))
        return projects

    # ── 项目详情 ──────────────────────────────────────────────

    async def get_project(self, project_id: str, user_id: str) -> ProjectResponse:
        """获取单个项目详情，验证归属权。"""
        row = await self._fetch_project(project_id)
        if row["user_id"] != user_id:
            raise HTTPException(status_code=403, detail="无权访问该项目")

        materials_status = await self._get_materials_status(project_id)
        return self._to_response(row, materials_status)

    # ── 更新项目 ──────────────────────────────────────────────

    async def update_project(
        self, project_id: str, user_id: str, data: dict
    ) -> ProjectResponse:
        """更新项目字段（name, current_stage），验证归属权。"""
        row = await self._fetch_project(project_id)
        if row["user_id"] != user_id:
            raise HTTPException(status_code=403, detail="无权修改该项目")

        # 过滤掉 None 值，只更新有值的字段
        update_fields = {k: v for k, v in data.items() if v is not None}
        if not update_fields:
            raise HTTPException(status_code=422, detail="没有需要更新的字段")

        try:
            result = (
                self._sb.table("projects")
                .update(update_fields)
                .eq("id", project_id)
                .execute()
            )
        except Exception as exc:
            logger.exception("更新项目失败")
            raise HTTPException(status_code=500, detail=f"更新项目失败: {exc}") from exc

        updated_row = result.data[0]
        materials_status = await self._get_materials_status(project_id)
        return self._to_response(updated_row, materials_status)

    # ── 内部辅助方法 ──────────────────────────────────────────

    async def _fetch_project(self, project_id: str) -> dict:
        """根据ID查询项目，不存在则抛404。"""
        try:
            result = (
                self._sb.table("projects")
                .select("*")
                .eq("id", project_id)
                .limit(1)
                .execute()
            )
        except Exception as exc:
            logger.exception("查询项目失败")
            raise HTTPException(status_code=500, detail=f"查询项目失败: {exc}") from exc

        if not result or not result.data:
            raise HTTPException(status_code=404, detail="项目不存在")
        return result.data[0]

    async def _get_materials_status(self, project_id: str) -> dict[str, bool]:
        """查询项目的材料上传状态。"""
        status = self._empty_materials_status()
        try:
            result = (
                self._sb.table("project_materials")
                .select("material_type")
                .eq("project_id", project_id)
                .eq("is_latest", True)
                .execute()
            )
        except Exception:
            logger.warning("查询材料状态失败，返回默认值")
            return status

        for row in result.data:
            mt = row.get("material_type")
            if mt in status:
                status[mt] = True
        return status

    @staticmethod
    def _empty_materials_status() -> dict[str, bool]:
        return {mt: False for mt in MATERIAL_TYPES}

    @staticmethod
    def _to_response(row: dict, materials_status: dict) -> ProjectResponse:
        created_at = row.get("created_at", "")
        if isinstance(created_at, str):
            # Supabase 返回 ISO 格式字符串
            created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        return ProjectResponse(
            id=row["id"],
            name=row["name"],
            competition=row["competition"],
            track=row["track"],
            group=row["group"],
            current_stage=row.get("current_stage", "school_text"),
            materials_status=materials_status,
            created_at=created_at,
        )
