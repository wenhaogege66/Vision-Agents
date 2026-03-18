"""材料管理路由：上传、查询、版本历史。"""

import logging

from fastapi import APIRouter, Depends, File, Form, UploadFile
from supabase import Client

from app.models.database import get_supabase
from app.models.schemas import DownloadUrlResponse, MaterialStatusResponse, MaterialUploadResponse, UserInfo
from app.routes.auth import get_current_user
from app.services.material_service import MaterialService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/projects/{project_id}/materials", tags=["materials"]
)


def _get_material_service(supabase: Client = Depends(get_supabase)) -> MaterialService:
    return MaterialService(supabase)


@router.post("", response_model=MaterialUploadResponse)
async def upload_material(
    project_id: str,
    material_type: str = Form(...),
    file: UploadFile = File(...),
    user: UserInfo = Depends(get_current_user),
    svc: MaterialService = Depends(_get_material_service),
):
    """上传材料文件。"""
    result, _storage_path = await svc.upload(project_id, material_type, file)
    return result


@router.get("")
async def list_materials(
    project_id: str,
    user: UserInfo = Depends(get_current_user),
    svc: MaterialService = Depends(_get_material_service),
):
    """获取项目所有最新材料列表。"""
    all_types = ["bp", "text_ppt", "presentation_ppt", "presentation_video"]
    materials = []
    for mt in all_types:
        item = await svc.get_latest(project_id, mt)
        if item:
            materials.append(item)
    return materials


@router.get("/status", response_model=MaterialStatusResponse)
async def get_material_status(
    project_id: str,
    user: UserInfo = Depends(get_current_user),
    svc: MaterialService = Depends(_get_material_service),
):
    """获取项目各材料类型的上传和就绪状态。"""
    return await svc.get_status(project_id)


@router.get("/{material_type}")
async def get_material(
    project_id: str,
    material_type: str,
    user: UserInfo = Depends(get_current_user),
    svc: MaterialService = Depends(_get_material_service),
):
    """获取指定类型的最新材料。"""
    item = await svc.get_latest(project_id, material_type)
    if not item:
        return {"detail": f"未找到类型为 {material_type} 的材料"}
    return item


@router.get("/{material_type}/versions")
async def get_material_versions(
    project_id: str,
    material_type: str,
    user: UserInfo = Depends(get_current_user),
    svc: MaterialService = Depends(_get_material_service),
):
    """获取指定类型材料的历史版本列表。"""
    return await svc.get_versions(project_id, material_type)


@router.get("/{material_id}/download", response_model=DownloadUrlResponse)
async def download_material(
    project_id: str,
    material_id: str,
    user: UserInfo = Depends(get_current_user),
    svc: MaterialService = Depends(_get_material_service),
):
    """生成材料文件的签名下载 URL。文件不存在时返回 404。"""
    return await svc.get_download_url(project_id, material_id)
