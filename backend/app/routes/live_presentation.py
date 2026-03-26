"""现场路演路由：创建路演会话、切换交互模式、结束路演、会议分享。"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from supabase import Client

from app.models.database import get_supabase
from app.models.schemas import (
    LiveSessionCreate,
    LiveSessionEnd,
    ModeSwitch,
    ShareLinkResponse,
    UserInfo,
)
from app.routes.auth import get_current_user
from app.services.live_presentation_service import (
    LivePresentationService,
    get_active_sessions,
    get_share_tokens,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/projects/{project_id}/live", tags=["live_presentation"]
)

# 独立路由器：会议加入端点（不同前缀）
share_join_router = APIRouter(tags=["live_presentation"])


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


# ── POST /api/projects/{project_id}/live/{session_id}/share ───


@router.post("/{session_id}/share", response_model=ShareLinkResponse)
async def generate_share_link(
    project_id: str,
    session_id: str,
    request: Request,
    user: UserInfo = Depends(get_current_user),
    svc: LivePresentationService = Depends(_get_live_service),
):
    """生成会议分享链接"""
    base_url = str(request.base_url).rstrip("/")
    result = await svc.generate_share_link(session_id, base_url)
    return ShareLinkResponse(**result)


# ── GET /api/live/join/{share_token} ──────────────────────────


@share_join_router.get("/api/live/join/{share_token}")
async def join_via_share_link(share_token: str):
    """通过分享链接验证并加入会议"""
    tokens = get_share_tokens()
    token_info = tokens.get(share_token)

    if token_info is None:
        raise HTTPException(status_code=404, detail="分享链接无效或已过期")

    # 检查是否过期
    created_at = datetime.fromisoformat(token_info["created_at"])
    elapsed = (datetime.now(timezone.utc) - created_at).total_seconds()
    if elapsed > token_info["expires_in"]:
        # 清理过期令牌
        tokens.pop(share_token, None)
        raise HTTPException(status_code=404, detail="分享链接无效或已过期")

    # 检查会议是否仍然活跃
    session_id = token_info["session_id"]
    active_sessions = get_active_sessions()
    if session_id not in active_sessions:
        raise HTTPException(status_code=410, detail="会议已结束")

    session = active_sessions[session_id]
    return {
        "session_id": session_id,
        "call_id": session.call_id,
        "project_id": session.project_id,
        "mode": session.mode,
        "style": session.style,
    }
