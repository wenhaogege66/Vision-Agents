"""现场路演路由：创建路演会话、切换交互模式、结束路演。"""

import logging

from fastapi import APIRouter, Depends
from supabase import Client

from app.models.database import get_supabase
from app.models.schemas import LiveSessionCreate, LiveSessionEnd, ModeSwitch, UserInfo
from app.routes.auth import get_current_user
from app.services.live_presentation_service import LivePresentationService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/projects/{project_id}/live", tags=["live_presentation"]
)


def _get_live_service(
    supabase: Client = Depends(get_supabase),
) -> LivePresentationService:
    return LivePresentationService(supabase)


# ── POST /api/projects/{project_id}/live/start ────────────────


@router.post("/start")
async def start_live_session(
    project_id: str,
    body: LiveSessionCreate,
    user: UserInfo = Depends(get_current_user),
    svc: LivePresentationService = Depends(_get_live_service),
):
    """创建现场路演会话，建立GetStream视频通话和Qwen Realtime连接"""
    return await svc.start_session(
        project_id=project_id,
        user_id=user.id,
        mode=body.mode,
        style=body.style,
        voice=body.voice,
        voice_type=body.voice_type,
    )


# ── POST /api/projects/{project_id}/live/mode ─────────────────


@router.post("/mode")
async def switch_mode(
    project_id: str,
    body: ModeSwitch,
    user: UserInfo = Depends(get_current_user),
    svc: LivePresentationService = Depends(_get_live_service),
):
    """切换路演交互模式（提问/建议）"""
    return await svc.switch_mode(
        session_id=body.session_id,
        mode=body.mode,
    )


# ── POST /api/projects/{project_id}/live/end ──────────────────


@router.post("/end")
async def end_live_session(
    project_id: str,
    body: LiveSessionEnd,
    user: UserInfo = Depends(get_current_user),
    svc: LivePresentationService = Depends(_get_live_service),
):
    """结束路演会话，生成评审总结并存储"""
    return await svc.end_session(session_id=body.session_id)
