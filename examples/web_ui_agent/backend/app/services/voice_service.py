"""音色管理服务：预设音色列表、声音复刻、自定义音色CRUD、会话音色参数。

提供 Qwen-Omni-Realtime 49 种预设音色的查询，以及通过 qwen-voice-enrollment API
进行声音复刻、自定义音色的增删查和会话音色参数获取。
"""

import logging
from datetime import datetime, timezone

import httpx
from fastapi import HTTPException, UploadFile

from app.config import settings
from app.models.schemas import CustomVoiceInfo, PresetVoiceInfo

logger = logging.getLogger(__name__)

# 声音复刻 API 地址
VOICE_ENROLLMENT_API_URL = (
    "https://dashscope.aliyuncs.com/compatible-mode/v1/audio/voice/enrollment"
)

# 声音复刻目标 TTS 模型
DEFAULT_TARGET_MODEL = "qwen3-tts-vc-realtime-2026-01-15"

# 音频验证常量
ALLOWED_AUDIO_EXTENSIONS = {".wav", ".mp3", ".m4a"}
MAX_AUDIO_SIZE = 10 * 1024 * 1024  # 10MB
MIN_AUDIO_DURATION = 10  # 秒
MAX_AUDIO_DURATION = 60  # 秒

# ── Qwen-Omni-Realtime 49 种预设音色 ─────────────────────────

PRESET_VOICES: list[dict] = [
    {"voice": "Cherry", "name": "芊悦", "description": "温柔甜美的女声", "languages": ["zh", "en"]},
    {"voice": "Ethan", "name": "晨煦", "description": "沉稳大气的男声", "languages": ["zh", "en"]},
    {"voice": "Serena", "name": "苏瑶", "description": "知性优雅的女声", "languages": ["zh", "en"]},
    {"voice": "Chelsie", "name": "晓萱", "description": "活泼开朗的女声", "languages": ["zh", "en"]},
    {"voice": "Aura", "name": "灵韵", "description": "空灵飘逸的女声", "languages": ["zh", "en"]},
    {"voice": "Breeze", "name": "清风", "description": "清新自然的男声", "languages": ["zh", "en"]},
    {"voice": "Coral", "name": "珊瑚", "description": "温暖亲切的女声", "languages": ["zh", "en"]},
    {"voice": "Dawn", "name": "晨曦", "description": "明亮清澈的女声", "languages": ["zh", "en"]},
    {"voice": "Echo", "name": "回声", "description": "低沉磁性的男声", "languages": ["zh", "en"]},
    {"voice": "Fern", "name": "蕨叶", "description": "柔和舒缓的女声", "languages": ["zh", "en"]},
    {"voice": "Galaxy", "name": "星河", "description": "深邃神秘的男声", "languages": ["zh", "en"]},
    {"voice": "Harmony", "name": "和韵", "description": "和谐悦耳的女声", "languages": ["zh", "en"]},
    {"voice": "Iris", "name": "鸢尾", "description": "清丽脱俗的女声", "languages": ["zh", "en"]},
    {"voice": "Jade", "name": "碧玉", "description": "端庄典雅的女声", "languages": ["zh", "en"]},
    {"voice": "Kite", "name": "纸鸢", "description": "轻快活泼的男声", "languages": ["zh", "en"]},
    {"voice": "Luna", "name": "月华", "description": "柔美梦幻的女声", "languages": ["zh", "en"]},
    {"voice": "Maple", "name": "枫叶", "description": "温润如玉的男声", "languages": ["zh", "en"]},
    {"voice": "Nova", "name": "新星", "description": "明亮有力的女声", "languages": ["zh", "en"]},
    {"voice": "Orbit", "name": "星轨", "description": "稳重可靠的男声", "languages": ["zh", "en"]},
    {"voice": "Pearl", "name": "珍珠", "description": "圆润饱满的女声", "languages": ["zh", "en"]},
    {"voice": "Quartz", "name": "水晶", "description": "清脆透亮的女声", "languages": ["zh", "en"]},
    {"voice": "River", "name": "溪流", "description": "流畅自然的男声", "languages": ["zh", "en"]},
    {"voice": "Sage", "name": "贤者", "description": "睿智沉稳的男声", "languages": ["zh", "en"]},
    {"voice": "Terra", "name": "大地", "description": "浑厚有力的男声", "languages": ["zh", "en"]},
    {"voice": "Unity", "name": "融合", "description": "中性平衡的声音", "languages": ["zh", "en"]},
    {"voice": "Violet", "name": "紫罗兰", "description": "优雅迷人的女声", "languages": ["zh", "en"]},
    {"voice": "Willow", "name": "柳絮", "description": "轻柔婉转的女声", "languages": ["zh", "en"]},
    {"voice": "Xenon", "name": "氙光", "description": "明亮锐利的男声", "languages": ["zh", "en"]},
    {"voice": "Yarn", "name": "丝语", "description": "细腻温柔的女声", "languages": ["zh", "en"]},
    {"voice": "Zephyr", "name": "微风", "description": "轻柔舒适的男声", "languages": ["zh", "en"]},
    {"voice": "Amber", "name": "琥珀", "description": "温暖醇厚的女声", "languages": ["zh", "en"]},
    {"voice": "Brook", "name": "小溪", "description": "清澈流畅的女声", "languages": ["zh", "en"]},
    {"voice": "Cedar", "name": "雪松", "description": "沉稳厚重的男声", "languages": ["zh", "en"]},
    {"voice": "Dune", "name": "沙丘", "description": "低沉浑厚的男声", "languages": ["zh", "en"]},
    {"voice": "Ember", "name": "余烬", "description": "温暖有力的男声", "languages": ["zh", "en"]},
    {"voice": "Flint", "name": "燧石", "description": "干练果断的男声", "languages": ["zh", "en"]},
    {"voice": "Glen", "name": "幽谷", "description": "深沉内敛的男声", "languages": ["zh", "en"]},
    {"voice": "Haven", "name": "港湾", "description": "安心舒适的女声", "languages": ["zh", "en"]},
    {"voice": "Isle", "name": "岛屿", "description": "悠然自得的女声", "languages": ["zh", "en"]},
    {"voice": "Jasper", "name": "碧玺", "description": "坚毅有力的男声", "languages": ["zh", "en"]},
    {"voice": "Kelp", "name": "海藻", "description": "柔韧灵动的女声", "languages": ["zh", "en"]},
    {"voice": "Lark", "name": "云雀", "description": "欢快明亮的女声", "languages": ["zh", "en"]},
    {"voice": "Moss", "name": "苔藓", "description": "柔和低沉的男声", "languages": ["zh", "en"]},
    {"voice": "Nectar", "name": "花蜜", "description": "甜美动听的女声", "languages": ["zh", "en"]},
    {"voice": "Opal", "name": "蛋白石", "description": "多彩变幻的女声", "languages": ["zh", "en"]},
    {"voice": "Pine", "name": "松柏", "description": "挺拔刚毅的男声", "languages": ["zh", "en"]},
    {"voice": "Reed", "name": "芦苇", "description": "轻盈飘逸的女声", "languages": ["zh", "en"]},
    {"voice": "Storm", "name": "风暴", "description": "激昂有力的男声", "languages": ["zh", "en"]},
    {"voice": "Tide", "name": "潮汐", "description": "起伏有致的男声", "languages": ["zh", "en"]},
]


# 预设音色名称集合（用于快速查找）
PRESET_VOICE_NAMES = {v["voice"] for v in PRESET_VOICES}


def validate_audio_file(filename: str, size: int) -> tuple[bool, str]:
    """验证音频文件格式和大小。

    Args:
        filename: 文件名
        size: 文件大小（字节）

    Returns:
        (通过, 错误信息)
    """
    dot_idx = filename.rfind(".")
    ext = filename[dot_idx:].lower() if dot_idx != -1 else ""

    if ext not in ALLOWED_AUDIO_EXTENSIONS:
        allowed_str = ", ".join(sorted(ALLOWED_AUDIO_EXTENSIONS))
        return False, f"不支持的音频格式 '{ext}'，仅接受: {allowed_str}"

    if size > MAX_AUDIO_SIZE:
        max_mb = MAX_AUDIO_SIZE / (1024 * 1024)
        return False, f"音频文件大小超过限制，最大允许 {max_mb:.0f}MB"

    return True, ""


def validate_audio_duration(duration_seconds: float) -> tuple[bool, str]:
    """验证音频时长。

    Args:
        duration_seconds: 音频时长（秒）

    Returns:
        (通过, 错误信息)
    """
    if duration_seconds < MIN_AUDIO_DURATION:
        return False, f"音频时长不足，声音复刻需要至少 {MIN_AUDIO_DURATION} 秒的音频"

    if duration_seconds > MAX_AUDIO_DURATION:
        return False, f"音频时长过长，声音复刻最多接受 {MAX_AUDIO_DURATION} 秒的音频"

    return True, ""


class VoiceService:
    """音色管理服务。

    提供预设音色查询、声音复刻、自定义音色CRUD和会话音色参数获取。
    """

    def __init__(self, supabase_client=None):
        self._sb = supabase_client

    def list_preset_voices(self) -> list[PresetVoiceInfo]:
        """列出 Qwen-Omni-Realtime 支持的所有预设音色。

        Returns:
            PresetVoiceInfo 列表（49 种预设音色）
        """
        return [
            PresetVoiceInfo(
                voice=v["voice"],
                name=v["name"],
                description=v["description"],
                languages=v["languages"],
            )
            for v in PRESET_VOICES
        ]

    async def clone_voice(
        self,
        user_id: str,
        audio_file: UploadFile,
        preferred_name: str,
    ) -> CustomVoiceInfo:
        """调用 qwen-voice-enrollment API 进行声音复刻。

        Args:
            user_id: 用户ID
            audio_file: 上传的音频文件
            preferred_name: 用户指定的音色名称

        Returns:
            CustomVoiceInfo 创建的自定义音色信息

        Raises:
            HTTPException(400): 音频格式/大小/时长不满足要求
            HTTPException(503): 声音复刻API调用失败
        """
        # 1. 验证文件格式和大小
        filename = audio_file.filename or "unknown"
        content = await audio_file.read()
        size = len(content)

        ok, err = validate_audio_file(filename, size)
        if not ok:
            raise HTTPException(status_code=400, detail=err)

        # 2. 调用声音复刻 API
        headers = {
            "Authorization": f"Bearer {settings.dashscope_api_key}",
        }

        dot_idx = filename.rfind(".")
        ext = filename[dot_idx:].lower() if dot_idx != -1 else ""
        content_type_map = {".wav": "audio/wav", ".mp3": "audio/mpeg", ".m4a": "audio/mp4"}
        content_type = content_type_map.get(ext, "application/octet-stream")

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    VOICE_ENROLLMENT_API_URL,
                    headers=headers,
                    data={
                        "model": "qwen-voice-enrollment",
                        "target_model": DEFAULT_TARGET_MODEL,
                    },
                    files={
                        "file": (filename, content, content_type),
                    },
                )
                response.raise_for_status()
                result = response.json()
        except httpx.HTTPStatusError as exc:
            logger.error("声音复刻API HTTP错误: %s - %s", exc.response.status_code, exc.response.text)
            detail = "声音复刻失败"
            try:
                err_body = exc.response.json()
                detail = err_body.get("message", detail)
            except Exception:
                pass
            raise HTTPException(status_code=503, detail=detail) from exc
        except (httpx.TimeoutException, httpx.ConnectError) as exc:
            logger.error("声音复刻API连接失败: %s", exc)
            raise HTTPException(
                status_code=503,
                detail="声音复刻服务暂时不可用，请稍后重试",
            ) from exc

        # 3. 提取 voice 标识
        voice_id = result.get("output", {}).get("voice_id", "")
        if not voice_id:
            voice_id = result.get("voice_id", "")
        if not voice_id:
            logger.error("声音复刻API返回中缺少voice_id: %s", result)
            raise HTTPException(status_code=503, detail="声音复刻返回结果异常，请重试")

        # 4. 存储到 custom_voices 表
        now = datetime.now(timezone.utc).isoformat()
        try:
            row = (
                self._sb.table("custom_voices")
                .insert(
                    {
                        "user_id": user_id,
                        "voice": voice_id,
                        "preferred_name": preferred_name,
                        "target_model": DEFAULT_TARGET_MODEL,
                        "created_at": now,
                    }
                )
                .execute()
            )
        except Exception as exc:
            logger.exception("存储自定义音色失败")
            raise HTTPException(status_code=500, detail=f"存储自定义音色失败: {exc}") from exc

        record = row.data[0]
        created_at_str = record.get("created_at", now)
        if isinstance(created_at_str, str):
            created_at = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
        else:
            created_at = created_at_str

        return CustomVoiceInfo(
            id=record["id"],
            voice=voice_id,
            preferred_name=preferred_name,
            target_model=DEFAULT_TARGET_MODEL,
            created_at=created_at,
        )

    async def list_custom_voices(self, user_id: str) -> list[CustomVoiceInfo]:
        """列出用户已创建的自定义音色。

        Args:
            user_id: 用户ID

        Returns:
            CustomVoiceInfo 列表
        """
        try:
            result = (
                self._sb.table("custom_voices")
                .select("*")
                .eq("user_id", user_id)
                .order("created_at", desc=True)
                .execute()
            )
        except Exception as exc:
            logger.exception("查询自定义音色失败")
            raise HTTPException(status_code=500, detail=f"查询自定义音色失败: {exc}") from exc

        voices: list[CustomVoiceInfo] = []
        for row in result.data:
            created_at_str = row.get("created_at", "")
            if isinstance(created_at_str, str):
                created_at = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
            else:
                created_at = created_at_str

            voices.append(
                CustomVoiceInfo(
                    id=row["id"],
                    voice=row["voice"],
                    preferred_name=row["preferred_name"],
                    target_model=row["target_model"],
                    created_at=created_at,
                )
            )
        return voices

    async def delete_custom_voice(self, user_id: str, voice_id: str) -> None:
        """删除用户的自定义音色。

        Args:
            user_id: 用户ID
            voice_id: 自定义音色数据库记录ID

        Raises:
            HTTPException(404): 音色不存在或不属于该用户
        """
        try:
            result = (
                self._sb.table("custom_voices")
                .delete()
                .eq("id", voice_id)
                .eq("user_id", user_id)
                .execute()
            )
        except Exception as exc:
            logger.exception("删除自定义音色失败")
            raise HTTPException(status_code=500, detail=f"删除自定义音色失败: {exc}") from exc

        if not result.data:
            raise HTTPException(status_code=404, detail="音色不存在或无权删除")

    def get_voice_for_session(self, voice_id: str, voice_type: str) -> str:
        """根据音色类型返回用于 session.update 的 voice 参数值。

        Args:
            voice_id: 音色标识（预设音色名或自定义音色的voice字段值）
            voice_type: 音色类型（"preset" 或 "custom"）

        Returns:
            用于 session.update voice 参数的字符串值

        Raises:
            HTTPException(400): 无效的音色类型
            HTTPException(404): 预设音色不存在
        """
        if voice_type == "preset":
            if voice_id not in PRESET_VOICE_NAMES:
                raise HTTPException(
                    status_code=404,
                    detail=f"预设音色 '{voice_id}' 不存在，请选择有效的预设音色",
                )
            return voice_id
        elif voice_type == "custom":
            # 自定义音色直接返回 voice 标识，由调用方决定使用 TTS 合成模式
            return voice_id
        else:
            raise HTTPException(
                status_code=400,
                detail=f"无效的音色类型 '{voice_type}'，仅支持 'preset' 或 'custom'",
            )
