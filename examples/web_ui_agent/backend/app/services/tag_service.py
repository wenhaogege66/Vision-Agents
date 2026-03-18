"""自定义标签管理服务：标签 CRUD 和项目-标签关联管理。

支持用户创建彩色标签、关联标签到项目、按标签筛选项目等功能。
数据存储在 project_tags 和 project_tag_associations 两张表中。
"""

import logging

from fastapi import HTTPException
from postgrest.exceptions import APIError
from supabase import Client

logger = logging.getLogger(__name__)


class TagService:
    """封装自定义标签的 CRUD 和项目-标签关联操作。"""

    def __init__(self, supabase: Client) -> None:
        self._sb = supabase

    # ── 标签 CRUD ─────────────────────────────────────────────

    async def create_tag(self, user_id: str, name: str, color: str) -> dict:
        """创建自定义标签。

        Args:
            user_id: 用户 ID
            name: 标签名称
            color: 标签颜色（如 "#f5222d"）

        Returns:
            新创建的标签记录字典

        Raises:
            HTTPException(409): 标签名称已存在（同一用户下唯一）
        """
        try:
            result = (
                self._sb.table("project_tags")
                .insert({"user_id": user_id, "name": name, "color": color})
                .execute()
            )
        except APIError as exc:
            if "duplicate" in str(exc).lower() or "unique" in str(exc).lower():
                raise HTTPException(
                    status_code=409, detail="标签名称已存在"
                ) from exc
            logger.exception("创建标签失败")
            raise HTTPException(
                status_code=500, detail=f"创建标签失败: {exc}"
            ) from exc
        except Exception as exc:
            logger.exception("创建标签失败")
            raise HTTPException(
                status_code=500, detail=f"创建标签失败: {exc}"
            ) from exc

        return result.data[0]

    async def list_tags(self, user_id: str) -> list[dict]:
        """获取用户的所有自定义标签，按创建时间降序排列。

        Args:
            user_id: 用户 ID

        Returns:
            标签记录列表
        """
        try:
            result = (
                self._sb.table("project_tags")
                .select("*")
                .eq("user_id", user_id)
                .order("created_at", desc=True)
                .execute()
            )
        except Exception as exc:
            logger.exception("查询标签列表失败")
            raise HTTPException(
                status_code=500, detail=f"查询标签列表失败: {exc}"
            ) from exc

        return result.data

    async def update_tag(
        self, tag_id: str, user_id: str, name: str, color: str
    ) -> dict:
        """更新标签名称和颜色。

        Args:
            tag_id: 标签 ID
            user_id: 用户 ID（确保只能修改自己的标签）
            name: 新标签名称
            color: 新标签颜色

        Returns:
            更新后的标签记录字典

        Raises:
            HTTPException(404): 标签不存在
            HTTPException(409): 新名称与已有标签重复
        """
        try:
            result = (
                self._sb.table("project_tags")
                .update({"name": name, "color": color})
                .eq("id", tag_id)
                .eq("user_id", user_id)
                .execute()
            )
        except APIError as exc:
            if "duplicate" in str(exc).lower() or "unique" in str(exc).lower():
                raise HTTPException(
                    status_code=409, detail="标签名称已存在"
                ) from exc
            logger.exception("更新标签失败")
            raise HTTPException(
                status_code=500, detail=f"更新标签失败: {exc}"
            ) from exc
        except Exception as exc:
            logger.exception("更新标签失败")
            raise HTTPException(
                status_code=500, detail=f"更新标签失败: {exc}"
            ) from exc

        if not result.data:
            raise HTTPException(status_code=404, detail="标签不存在")

        return result.data[0]

    async def delete_tag(self, tag_id: str, user_id: str) -> None:
        """删除标签（级联删除关联记录）。

        Args:
            tag_id: 标签 ID
            user_id: 用户 ID（确保只能删除自己的标签）

        Raises:
            HTTPException(404): 标签不存在
        """
        try:
            result = (
                self._sb.table("project_tags")
                .delete()
                .eq("id", tag_id)
                .eq("user_id", user_id)
                .execute()
            )
        except Exception as exc:
            logger.exception("删除标签失败")
            raise HTTPException(
                status_code=500, detail=f"删除标签失败: {exc}"
            ) from exc

        if not result.data:
            raise HTTPException(status_code=404, detail="标签不存在")

    # ── 项目-标签关联 ─────────────────────────────────────────

    async def add_tag_to_project(self, project_id: str, tag_id: str) -> dict:
        """将标签关联到项目。

        Args:
            project_id: 项目 ID
            tag_id: 标签 ID

        Returns:
            新创建的关联记录字典

        Raises:
            HTTPException(409): 该标签已关联到此项目
        """
        try:
            result = (
                self._sb.table("project_tag_associations")
                .insert({"project_id": project_id, "tag_id": tag_id})
                .execute()
            )
        except APIError as exc:
            if "duplicate" in str(exc).lower() or "unique" in str(exc).lower():
                raise HTTPException(
                    status_code=409, detail="该标签已关联到此项目"
                ) from exc
            logger.exception("关联标签失败")
            raise HTTPException(
                status_code=500, detail=f"关联标签失败: {exc}"
            ) from exc
        except Exception as exc:
            logger.exception("关联标签失败")
            raise HTTPException(
                status_code=500, detail=f"关联标签失败: {exc}"
            ) from exc

        return result.data[0]

    async def remove_tag_from_project(
        self, project_id: str, tag_id: str
    ) -> None:
        """移除项目上的标签关联。

        Args:
            project_id: 项目 ID
            tag_id: 标签 ID

        Raises:
            HTTPException(404): 关联记录不存在
        """
        try:
            result = (
                self._sb.table("project_tag_associations")
                .delete()
                .eq("project_id", project_id)
                .eq("tag_id", tag_id)
                .execute()
            )
        except Exception as exc:
            logger.exception("移除标签关联失败")
            raise HTTPException(
                status_code=500, detail=f"移除标签关联失败: {exc}"
            ) from exc

        if not result.data:
            raise HTTPException(status_code=404, detail="标签关联不存在")

    async def get_project_tags(self, project_id: str) -> list[dict]:
        """查询项目关联的所有标签。

        通过 project_tag_associations 关联 project_tags 表，
        返回项目关联的标签详情列表。

        Args:
            project_id: 项目 ID

        Returns:
            标签记录列表（包含 id, name, color, created_at）
        """
        try:
            result = (
                self._sb.table("project_tag_associations")
                .select("tag_id, project_tags(id, name, color, created_at)")
                .eq("project_id", project_id)
                .execute()
            )
        except Exception as exc:
            logger.exception("查询项目标签失败")
            raise HTTPException(
                status_code=500, detail=f"查询项目标签失败: {exc}"
            ) from exc

        # 提取嵌套的 project_tags 数据
        tags: list[dict] = []
        for row in result.data:
            tag_data = row.get("project_tags")
            if tag_data:
                tags.append(tag_data)

        return tags
