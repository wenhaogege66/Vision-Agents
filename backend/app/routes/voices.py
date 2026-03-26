"""音色管理路由：预设音色列表、自定义音色CRUD、声音复刻。"""

from fastapi import APIRouter, Depends, File, Form, UploadFile
from supabase import Client

from app.models.database import get_supabase
from app.models.schemas import CustomVoiceInfo, PresetVoiceInfo, UserInfo
from app.routes.auth import get_current_user
from app.services.voice_service import VoiceService

router = APIRouter(prefix="/api/voices", tags=["voices"])


def _get_voice_service(
    supabase: Client = Depends(get_supabase),
) -> VoiceService:
    return VoiceService(supabase)


# ── GET /api/voices/presets ───────────────────────────────────


@router.get("/presets", response_model=list[PresetVoiceInfo])
async def list_preset_voices(
    svc: VoiceService = Depends(_get_voice_service),
):
    """获取 Qwen-Omni-Realtime 预设音色列表（无需认证）"""
    return svc.list_preset_voices()


# ── GET /api/voices/custom ────────────────────────────────────


@router.get("/custom", response_model=list[CustomVoiceInfo])
async def list_custom_voices(
    user: UserInfo = Depends(get_current_user),
    svc: VoiceService = Depends(_get_voice_service),
):
    """获取用户已创建的自定义音色列表"""
    return await svc.list_custom_voices(user.id)


# ── POST /api/voices/clone ────────────────────────────────────


@router.post("/clone", response_model=CustomVoiceInfo)
async def clone_voice(
    audio: UploadFile = File(...),
    preferred_name: str = Form(...),
    user: UserInfo = Depends(get_current_user),
    svc: VoiceService = Depends(_get_voice_service),
):
    """上传音频进行声音复刻，创建自定义音色"""
    return await svc.clone_voice(user.id, audio, preferred_name)


# ── DELETE /api/voices/custom/{voice_id} ──────────────────────


@router.delete("/custom/{voice_id}", status_code=204)
async def delete_custom_voice(
    voice_id: str,
    user: UserInfo = Depends(get_current_user),
    svc: VoiceService = Depends(_get_voice_service),
):
    """删除用户的自定义音色"""
    await svc.delete_custom_voice(user.id, voice_id)
