"""项目管理路由：创建、列表、详情、更新。"""

from fastapi import APIRouter, Depends
from supabase import Client

from app.models.database import get_supabase
from app.models.schemas import (
    ProjectCreate,
    ProjectResponse,
    ProjectUpdate,
    UserInfo,
)
from app.routes.auth import get_current_user
from app.services.project_service import ProjectService

router = APIRouter(prefix="/api/projects", tags=["projects"])


def _get_project_service(supabase: Client = Depends(get_supabase)) -> ProjectService:
    return ProjectService(supabase)


@router.post("", response_model=ProjectResponse)
async def create_project(
    body: ProjectCreate,
    user: UserInfo = Depends(get_current_user),
    svc: ProjectService = Depends(_get_project_service),
):
    """创建新项目"""
    return await svc.create(user.id, body)


@router.get("", response_model=list[ProjectResponse])
async def list_projects(
    user: UserInfo = Depends(get_current_user),
    svc: ProjectService = Depends(_get_project_service),
):
    """获取当前用户的项目列表"""
    return await svc.list_projects(user.id)


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: str,
    user: UserInfo = Depends(get_current_user),
    svc: ProjectService = Depends(_get_project_service),
):
    """获取项目详情"""
    return await svc.get_project(project_id, user.id)


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: str,
    body: ProjectUpdate,
    user: UserInfo = Depends(get_current_user),
    svc: ProjectService = Depends(_get_project_service),
):
    """更新项目信息"""
    return await svc.update_project(
        project_id, user.id, body.model_dump(exclude_unset=True)
    )
