"""项目管理路由：创建、列表、详情、更新。"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from supabase import Client

from app.models.database import get_supabase
from app.models.schemas import (
    ProjectCreate,
    ProjectProfile,
    ProjectProfileUpdate,
    ProjectResponse,
    ProjectUpdate,
    StageConfigResponse,
    UserInfo,
)
from app.routes.auth import get_current_user
from app.services.export_service import ExportService
from app.services.profile_service import ProfileService
from app.services.project_service import ProjectService

router = APIRouter(prefix="/api/projects", tags=["projects"])


def _get_project_service(supabase: Client = Depends(get_supabase)) -> ProjectService:
    return ProjectService(supabase)


def _get_profile_service(supabase: Client = Depends(get_supabase)) -> ProfileService:
    return ProfileService(supabase)


def _get_export_service(supabase: Client = Depends(get_supabase)) -> ExportService:
    return ExportService(supabase)


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

@router.delete("/{project_id}", status_code=204)
async def delete_project(
    project_id: str,
    user: UserInfo = Depends(get_current_user),
    svc: ProjectService = Depends(_get_project_service),
):
    """删除项目及其所有关联数据"""
    await svc.delete_project(project_id, user.id)



@router.get("/{project_id}/stage-dates", response_model=list[StageConfigResponse])
async def get_stage_dates(
    project_id: str,
    user: UserInfo = Depends(get_current_user),
    svc: ProjectService = Depends(_get_project_service),
):
    """获取项目所属赛事各阶段日期配置"""
    project = await svc.get_project(project_id, user.id)
    return await svc.get_stage_dates(project.competition, project.track)


@router.post("/{project_id}/profile/extract", response_model=ProjectProfile)
async def extract_profile(
    project_id: str,
    user: UserInfo = Depends(get_current_user),
    svc: ProfileService = Depends(_get_profile_service),
):
    """触发 AI 提取项目简介"""
    return await svc.extract_profile(project_id)


@router.get("/{project_id}/profile", response_model=ProjectProfile | None)
async def get_profile(
    project_id: str,
    user: UserInfo = Depends(get_current_user),
    svc: ProfileService = Depends(_get_profile_service),
):
    """获取项目简介，不存在时返回 null"""
    return await svc.get_profile(project_id)


@router.put("/{project_id}/profile", response_model=ProjectProfile)
async def update_profile(
    project_id: str,
    data: ProjectProfileUpdate,
    user: UserInfo = Depends(get_current_user),
    svc: ProfileService = Depends(_get_profile_service),
):
    """用户编辑保存项目简介"""
    return await svc.update_profile(project_id, data.model_dump(exclude_unset=True))


@router.get("/{project_id}/export")
async def export_project_report(
    project_id: str,
    user: UserInfo = Depends(get_current_user),
    svc: ExportService = Depends(_get_export_service),
):
    """导出项目评审报告 PDF"""
    pdf_bytes = await svc.generate_report(project_id, user.id)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=report_{project_id}.pdf"},
    )
