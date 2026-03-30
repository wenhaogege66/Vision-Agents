"""数字人问辩路由：数字人服务（HeyGen/LiveAvatar）、视频任务、问题 CRUD、答案提交、记录查询。"""

import asyncio
import math

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from supabase import Client

from app.models.database import get_supabase
from app.models.schemas import (
    AvatarCacheItem,
    DefenseQuestionCreate,
    DefenseQuestionResponse,
    DefenseRecordResponse,
    GenerateFeedbackVideoRequest,
    GenerateQuestionVideoRequest,
    PhotoAvatarCreateRequest,
    UserInfo,
    VoiceCacheItem,
    VideoTaskResponse,
)
from app.routes.auth import get_current_user
from app.services.avatar import HeyGenVideoService, LiveAvatarStreamService
from app.services.avatar.cache_sync_service import CacheSyncService
from app.services.defense_service import DefenseService
from app.services.video_task_service import VideoTaskService

router = APIRouter(
    prefix="/api/projects/{project_id}/defense",
    tags=["defense"],
)


def _get_defense_service(supabase: Client = Depends(get_supabase)) -> DefenseService:
    return DefenseService(supabase)


def _get_video_task_service(
    supabase: Client = Depends(get_supabase),
) -> VideoTaskService:
    return VideoTaskService(supabase)


# ── 数字人资源列表 ────────────────────────────────────────────


@router.get("/avatar/defaults")
async def get_avatar_defaults(
    project_id: str,
    user: UserInfo = Depends(get_current_user),
):
    """返回默认的数字人形象和音色 ID。"""
    from app.config import settings as _s
    return {
        "heygen_video_avatar_id": _s.heygen_video_avatar_id,
        "heygen_video_voice_id": _s.heygen_video_voice_id,
    }


@router.get("/avatar/heygen/voices")
async def list_heygen_voices(
    project_id: str,
    user: UserInfo = Depends(get_current_user),
):
    """列出 HeyGen 可用语音。"""
    svc = HeyGenVideoService()
    return await svc.list_voices()


@router.get("/avatar/heygen/talking-photos")
async def list_heygen_talking_photos(
    project_id: str,
    user: UserInfo = Depends(get_current_user),
):
    """列出 HeyGen Talking Photos。"""
    svc = HeyGenVideoService()
    return await svc.list_talking_photos()


@router.get("/avatar/heygen/avatars")
async def list_heygen_avatars(
    project_id: str,
    user: UserInfo = Depends(get_current_user),
):
    """列出 HeyGen Avatars。"""
    svc = HeyGenVideoService()
    return await svc.list_avatars()


@router.post("/avatar/heygen/photo-avatar")
async def create_photo_avatar(
    project_id: str,
    body: PhotoAvatarCreateRequest,
    user: UserInfo = Depends(get_current_user),
):
    """创建 Photo Avatar。"""
    svc = HeyGenVideoService()
    result = await svc.create_photo_avatar(body.model_dump())
    return result


@router.get("/avatar/heygen/photo-avatar/{generation_id}")
async def check_photo_avatar_status(
    project_id: str,
    generation_id: str,
    user: UserInfo = Depends(get_current_user),
):
    """查询 Photo Avatar 创建状态。"""
    svc = HeyGenVideoService()
    return await svc.check_photo_avatar_status(generation_id)


@router.get("/avatar/liveavatar/avatars")
async def list_liveavatar_avatars(
    project_id: str,
    user: UserInfo = Depends(get_current_user),
):
    """列出 LiveAvatar 可用数字人。"""
    svc = LiveAvatarStreamService()
    return await svc.list_avatars()


# ── 缓存查询 API ─────────────────────────────────────────────


@router.get("/avatar/cache/avatars")
async def list_cached_avatars(
    project_id: str,
    page: int = 1,
    page_size: int = 20,
    search: str | None = None,
    is_custom: bool | None = None,
    user: UserInfo = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """分页查询 avatar 缓存。"""
    # Build count query
    count_query = supabase.table("heygen_avatar_cache").select("*", count="exact")
    if search:
        count_query = count_query.ilike("name", f"%{search}%")
    if is_custom is not None:
        count_query = count_query.eq("is_custom", is_custom)
    count_resp = count_query.limit(0).execute()
    total = count_resp.count or 0

    # Build data query with pagination
    offset = (page - 1) * page_size
    data_query = supabase.table("heygen_avatar_cache").select("*")
    if search:
        data_query = data_query.ilike("name", f"%{search}%")
    if is_custom is not None:
        data_query = data_query.eq("is_custom", is_custom)
    data_resp = data_query.range(offset, offset + page_size - 1).execute()
    rows = data_resp.data or []

    items = [
        AvatarCacheItem(
            id=row["heygen_avatar_id"],
            name=row.get("name", ""),
            preview_image_url=row.get("preview_image_url", ""),
            avatar_type=row.get("avatar_type", "photo_avatar"),
            is_custom=row.get("is_custom", False),
            group_id=row.get("group_id"),
        )
        for row in rows
    ]

    total_pages = math.ceil(total / page_size) if page_size > 0 else 0
    return {
        "items": [item.model_dump() for item in items],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


@router.get("/avatar/cache/voices")
async def list_cached_voices(
    project_id: str,
    page: int = 1,
    page_size: int = 20,
    search: str | None = None,
    user: UserInfo = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """分页查询 voice 缓存。"""
    # Build count query
    count_query = supabase.table("heygen_voice_cache").select("*", count="exact")
    if search:
        count_query = count_query.ilike("name", f"%{search}%")
    count_resp = count_query.limit(0).execute()
    total = count_resp.count or 0

    # Build data query with pagination
    offset = (page - 1) * page_size
    data_query = supabase.table("heygen_voice_cache").select("*")
    if search:
        data_query = data_query.ilike("name", f"%{search}%")
    data_resp = data_query.range(offset, offset + page_size - 1).execute()
    rows = data_resp.data or []

    items = [
        VoiceCacheItem(
            voice_id=row["heygen_voice_id"],
            name=row.get("name", ""),
            language=row.get("language", ""),
            gender=row.get("gender", ""),
            preview_audio=row.get("preview_audio", ""),
            is_custom=row.get("is_custom", False),
        )
        for row in rows
    ]

    total_pages = math.ceil(total / page_size) if page_size > 0 else 0
    return {
        "items": [item.model_dump() for item in items],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


@router.post("/avatar/cache/sync", status_code=202)
async def trigger_cache_sync(
    project_id: str,
    user: UserInfo = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """手动触发缓存同步。"""
    svc = CacheSyncService(supabase)
    if svc.is_syncing():
        raise HTTPException(status_code=409, detail="同步正在进行中")
    asyncio.create_task(svc.force_sync())
    return {"message": "同步任务已启动"}


@router.get("/avatar/cache/sync-status")
async def get_cache_sync_status(
    project_id: str,
    user: UserInfo = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """查询缓存同步状态。"""
    svc = CacheSyncService(supabase)
    return await svc.get_sync_status()


# ── 数字人服务 ────────────────────────────────────────────────


class AvatarVideoRequest(BaseModel):
    text: str
    avatar_id: str | None = None


class LiveAvatarSessionRequest(BaseModel):
    avatar_id: str | None = None


@router.post("/avatar/liveavatar/session")
async def create_liveavatar_session(
    project_id: str,
    body: LiveAvatarSessionRequest | None = None,
    user: UserInfo = Depends(get_current_user),
):
    """创建 LiveAvatar 实时流式会话。"""
    svc = LiveAvatarStreamService()
    info = await svc.create_session(avatar_id=body.avatar_id if body else None)
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


# ── 视频任务 ────────────────────────────────────────────────


@router.post("/video-tasks/generate-question", response_model=VideoTaskResponse)
async def generate_question_video(
    project_id: str,
    body: GenerateQuestionVideoRequest | None = None,
    user: UserInfo = Depends(get_current_user),
    defense_svc: DefenseService = Depends(_get_defense_service),
    video_svc: VideoTaskService = Depends(_get_video_task_service),
):
    """创建提问视频生成任务。"""
    questions = await defense_svc.list_questions(project_id)
    if not questions:
        raise HTTPException(status_code=400, detail="项目没有预定义问题，无法生成提问视频")

    has_active = await video_svc.check_has_active_task(project_id)
    if has_active:
        raise HTTPException(status_code=409, detail="已有视频正在生成中")

    # Convert Pydantic models to dicts if needed
    q_dicts = [q if isinstance(q, dict) else q.model_dump() for q in questions]
    task = await video_svc.create_question_video_task(
        project_id, user.id, q_dicts,
        avatar_id=body.avatar_id if body else None,
        voice_id=body.voice_id if body else None,
        avatar_type=body.avatar_type if body else None,
        resolution=body.resolution if body else "720p",
        aspect_ratio=body.aspect_ratio if body else "16:9",
        expressiveness=body.expressiveness if body else "medium",
        remove_background=body.remove_background if body else False,
        voice_locale=body.voice_locale if body else "zh-CN",
    )
    return task


@router.post("/video-tasks/generate-feedback", response_model=VideoTaskResponse)
async def generate_feedback_video(
    project_id: str,
    body: GenerateFeedbackVideoRequest,
    user: UserInfo = Depends(get_current_user),
    video_svc: VideoTaskService = Depends(_get_video_task_service),
):
    """创建反馈视频生成任务。"""
    task = await video_svc.create_feedback_video_task(
        project_id, user.id, body.defense_record_id, body.feedback_text
    )
    return task


@router.get("/video-tasks/latest-question", response_model=VideoTaskResponse | None)
async def get_latest_question_task(
    project_id: str,
    user: UserInfo = Depends(get_current_user),
    video_svc: VideoTaskService = Depends(_get_video_task_service),
):
    """获取项目最新的提问视频任务。"""
    task = await video_svc.get_latest_question_task(project_id)
    return task


@router.get("/video-tasks/{task_id}", response_model=VideoTaskResponse)
async def get_video_task(
    project_id: str,
    task_id: str,
    user: UserInfo = Depends(get_current_user),
    video_svc: VideoTaskService = Depends(_get_video_task_service),
):
    """查询视频任务状态。"""
    task = await video_svc.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="视频任务不存在")
    return task


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
    return await svc.update_question(question_id, body.content, project_id=project_id)


@router.delete("/questions/{question_id}", status_code=204)
async def delete_question(
    project_id: str,
    question_id: str,
    user: UserInfo = Depends(get_current_user),
    svc: DefenseService = Depends(_get_defense_service),
):
    await svc.delete_question(question_id, project_id=project_id)


# ── 答案提交 ──────────────────────────────────────────────────


@router.post("/submit-answer", response_model=DefenseRecordResponse)
async def submit_answer(
    project_id: str,
    audio: UploadFile = File(...),
    answer_duration: int = Form(30),
    question_video_task_id: str | None = Form(None),
    user: UserInfo = Depends(get_current_user),
    svc: DefenseService = Depends(_get_defense_service),
):
    audio_bytes = await audio.read()
    return await svc.submit_answer(
        project_id=project_id,
        user_id=user.id,
        audio_content=audio_bytes,
        answer_duration=answer_duration,
        question_video_task_id=question_video_task_id,
    )


# ── 问辩记录 ──────────────────────────────────────────────────


@router.get("/records", response_model=list[DefenseRecordResponse])
async def list_records(
    project_id: str,
    user: UserInfo = Depends(get_current_user),
    svc: DefenseService = Depends(_get_defense_service),
):
    return await svc.list_records(project_id)


@router.delete("/records/{record_id}", status_code=204)
async def delete_record(
    project_id: str,
    record_id: str,
    user: UserInfo = Depends(get_current_user),
    svc: DefenseService = Depends(_get_defense_service),
):
    await svc.delete_record(record_id, project_id)
