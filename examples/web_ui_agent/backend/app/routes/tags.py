"""自定义标签路由：标签 CRUD 和项目-标签关联管理。"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from supabase import Client

from app.models.database import get_supabase
from app.models.schemas import TagCreate, TagResponse, UserInfo
from app.routes.auth import get_current_user
from app.services.tag_service import TagService

# ── 标签 CRUD 路由 ────────────────────────────────────────────

tag_router = APIRouter(prefix="/api/tags", tags=["tags"])


def _get_tag_service(supabase: Client = Depends(get_supabase)) -> TagService:
    return TagService(supabase)


@tag_router.post("", response_model=TagResponse)
async def create_tag(
    body: TagCreate,
    user: UserInfo = Depends(get_current_user),
    svc: TagService = Depends(_get_tag_service),
):
    """创建自定义标签。标签名称重复时返回 409。"""
    return await svc.create_tag(user.id, body.name, body.color)


@tag_router.get("", response_model=list[TagResponse])
async def list_tags(
    user: UserInfo = Depends(get_current_user),
    svc: TagService = Depends(_get_tag_service),
):
    """获取当前用户的所有自定义标签。"""
    return await svc.list_tags(user.id)


@tag_router.put("/{tag_id}", response_model=TagResponse)
async def update_tag(
    tag_id: str,
    body: TagCreate,
    user: UserInfo = Depends(get_current_user),
    svc: TagService = Depends(_get_tag_service),
):
    """更新标签名称和颜色。标签名称重复时返回 409。"""
    return await svc.update_tag(tag_id, user.id, body.name, body.color)


@tag_router.delete("/{tag_id}", status_code=204)
async def delete_tag(
    tag_id: str,
    user: UserInfo = Depends(get_current_user),
    svc: TagService = Depends(_get_tag_service),
):
    """删除标签（级联删除关联记录）。"""
    await svc.delete_tag(tag_id, user.id)


# ── 项目-标签关联路由 ─────────────────────────────────────────

project_tag_router = APIRouter(
    prefix="/api/projects/{project_id}/tags", tags=["project-tags"]
)


class AddTagBody(BaseModel):
    """关联标签到项目的请求体"""

    tag_id: str


@project_tag_router.post("", response_model=TagResponse)
async def add_tag_to_project(
    project_id: str,
    body: AddTagBody,
    user: UserInfo = Depends(get_current_user),
    svc: TagService = Depends(_get_tag_service),
):
    """将标签关联到项目。已关联时返回 409。"""
    return await svc.add_tag_to_project(project_id, body.tag_id)


@project_tag_router.delete("/{tag_id}", status_code=204)
async def remove_tag_from_project(
    project_id: str,
    tag_id: str,
    user: UserInfo = Depends(get_current_user),
    svc: TagService = Depends(_get_tag_service),
):
    """移除项目上的标签关联。"""
    await svc.remove_tag_from_project(project_id, tag_id)


@project_tag_router.get("", response_model=list[TagResponse])
async def get_project_tags(
    project_id: str,
    user: UserInfo = Depends(get_current_user),
    svc: TagService = Depends(_get_tag_service),
):
    """获取项目关联的所有标签。"""
    return await svc.get_project_tags(project_id)
