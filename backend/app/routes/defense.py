"""数字人问辩路由：数字人服务（HeyGen/LiveAvatar）、问题 CRUD、答案提交、记录查询。"""

from fastapi import APIRouter, Depends, File, Form, UploadFile
from pydantic import BaseModel
from supabase import Client

from app.models.database import get_supabase
from app.models.schemas import (
    DefenseQuestionCreate,
    DefenseQuestionResponse,
    DefenseRecordResponse,
    UserInfo,
)
from app.routes.auth import get_current_user
from app.services.avatar import HeyGenVideoService, LiveAvatarStreamService
from app.services.defense_service import DefenseService

router = APIRouter(
    prefix="/api/projects/{project_id}/defense",
    tags=["defense"],
)


def _get_defense_service(supabase: Client = Depends(get_supabase)) -> DefenseService:
    return DefenseService(supabase)


# ── 数字人服务 ────────────────────────────────────────────────


class AvatarVideoRequest(BaseModel):
    text: str
    avatar_id: str | None = None


@router.post("/avatar/liveavatar/session")
async def create_liveavatar_session(
    project_id: str,
    user: UserInfo = Depends(get_current_user),
):
    """创建 LiveAvatar 实时流式会话。"""
    svc = LiveAvatarStreamService()
    info = await svc.create_session()
    return {
        "provider": "liveavatar",
        "mode": "streaming",
        "session_token": info.session_token,
        "session_id": info.session_id,
    }


@router.post("/avatar/heygen/generate")
async def generate_heygen_video(
    project_id: str,
    body: AvatarVideoRequest,
    user: UserInfo = Depends(get_current_user),
):
    """通过 HeyGen 生成数字人视频。"""
    svc = HeyGenVideoService()
    result = await svc.generate_video(body.text, body.avatar_id)
    return {
        "provider": "heygen",
        "mode": "video",
        "video_id": result.video_id,
        "status": result.status,
    }


@router.get("/avatar/heygen/status/{video_id}")
async def check_heygen_video_status(
    project_id: str,
    video_id: str,
    user: UserInfo = Depends(get_current_user),
):
    """查询 HeyGen 视频生成状态。"""
    svc = HeyGenVideoService()
    result = await svc.check_video_status(video_id)
    return {
        "video_id": result.video_id,
        "status": result.status,
        "video_url": result.video_url,
    }


# ── 问题 CRUD ─────────────────────────────────────────────────


@router.get("/questions", response_model=list[DefenseQuestionResponse])
async def list_questions(
    project_id: str,
    user: UserInfo = Depends(get_current_user),
    svc: DefenseService = Depends(_get_defense_service),
):
    return await svc.list_questions(project_id)


@router.post("/questions", response_model=DefenseQuestionResponse)
async def create_question(
    project_id: str,
    body: DefenseQuestionCreate,
    user: UserInfo = Depends(get_current_user),
    svc: DefenseService = Depends(_get_defense_service),
):
    return await svc.create_question(project_id, body.content)


@router.put("/questions/{question_id}", response_model=DefenseQuestionResponse)
async def update_question(
    project_id: str,
    question_id: str,
    body: DefenseQuestionCreate,
    user: UserInfo = Depends(get_current_user),
    svc: DefenseService = Depends(_get_defense_service),
):
    return await svc.update_question(question_id, body.content)


@router.delete("/questions/{question_id}", status_code=204)
async def delete_question(
    project_id: str,
    question_id: str,
    user: UserInfo = Depends(get_current_user),
    svc: DefenseService = Depends(_get_defense_service),
):
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
    return await svc.list_records(project_id)
