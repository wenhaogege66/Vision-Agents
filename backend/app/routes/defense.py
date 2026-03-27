"""数字人问辩路由：HeyGen token、问题 CRUD、答案提交、记录查询。"""

from fastapi import APIRouter, Depends, File, Form, UploadFile
from supabase import Client

from app.models.database import get_supabase
from app.models.schemas import (
    DefenseQuestionCreate,
    DefenseQuestionResponse,
    DefenseRecordResponse,
    UserInfo,
)
from app.routes.auth import get_current_user
from app.services.defense_service import DefenseService
from app.services.heygen_service import HeyGenService

router = APIRouter(
    prefix="/api/projects/{project_id}/defense",
    tags=["defense"],
)


def _get_defense_service(supabase: Client = Depends(get_supabase)) -> DefenseService:
    return DefenseService(supabase)


# ── HeyGen Token ──────────────────────────────────────────────


@router.post("/token")
async def create_heygen_token(
    project_id: str,
    user: UserInfo = Depends(get_current_user),
):
    """获取 HeyGen streaming access token。"""
    svc = HeyGenService()
    token = await svc.create_token()
    return {"token": token}


# ── 问题 CRUD ─────────────────────────────────────────────────


@router.get("/questions", response_model=list[DefenseQuestionResponse])
async def list_questions(
    project_id: str,
    user: UserInfo = Depends(get_current_user),
    svc: DefenseService = Depends(_get_defense_service),
):
    """获取项目的预定义问题列表。"""
    return await svc.list_questions(project_id)


@router.post("/questions", response_model=DefenseQuestionResponse)
async def create_question(
    project_id: str,
    body: DefenseQuestionCreate,
    user: UserInfo = Depends(get_current_user),
    svc: DefenseService = Depends(_get_defense_service),
):
    """创建新的预定义问题。"""
    return await svc.create_question(project_id, body.content)


@router.put("/questions/{question_id}", response_model=DefenseQuestionResponse)
async def update_question(
    project_id: str,
    question_id: str,
    body: DefenseQuestionCreate,
    user: UserInfo = Depends(get_current_user),
    svc: DefenseService = Depends(_get_defense_service),
):
    """更新预定义问题内容。"""
    return await svc.update_question(question_id, body.content)


@router.delete("/questions/{question_id}", status_code=204)
async def delete_question(
    project_id: str,
    question_id: str,
    user: UserInfo = Depends(get_current_user),
    svc: DefenseService = Depends(_get_defense_service),
):
    """删除预定义问题。"""
    await svc.delete_question(question_id)


# ── 答案提交 ──────────────────────────────────────────────────


@router.post("/submit-answer", response_model=DefenseRecordResponse)
async def submit_answer(
    project_id: str,
    audio: UploadFile = File(...),
    answer_duration: int = Form(30),
    user: UserInfo = Depends(get_current_user),
    svc: DefenseService = Depends(_get_defense_service),
):
    """提交用户回答音频，执行 STT 转写和 AI 反馈生成。"""
    audio_bytes = await audio.read()
    return await svc.submit_answer(
        project_id=project_id,
        user_id=user.id,
        audio_content=audio_bytes,
        answer_duration=answer_duration,
    )


# ── 问辩记录 ──────────────────────────────────────────────────


@router.get("/records", response_model=list[DefenseRecordResponse])
async def list_records(
    project_id: str,
    user: UserInfo = Depends(get_current_user),
    svc: DefenseService = Depends(_get_defense_service),
):
    """获取项目的问辩记录列表，按时间倒序。"""
    return await svc.list_records(project_id)
