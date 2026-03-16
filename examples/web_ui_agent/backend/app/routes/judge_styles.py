"""评委风格路由：获取可用评委风格列表。"""

from fastapi import APIRouter

from app.models.schemas import JudgeStyleInfo
from app.services.prompt_service import prompt_service

router = APIRouter(prefix="/api", tags=["judge-styles"])


@router.get("/judge-styles", response_model=list[JudgeStyleInfo])
async def list_judge_styles():
    """获取可用评委风格列表（严厉型、温和型、学术型等）"""
    return prompt_service.list_styles()
