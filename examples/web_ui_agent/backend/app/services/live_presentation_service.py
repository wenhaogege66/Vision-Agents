"""现场路演服务：管理实时路演会话（GetStream视频 + Qwen Realtime WebSocket）。

提供路演会话的创建、交互模式切换和结束功能。
会话创建时：获取路演PPT → 加载规则和知识库 → 组装Prompt → 获取音色参数
→ 创建GetStream视频通话 → 建立Qwen Realtime WebSocket连接。
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import HTTPException
from getstream import Stream
from supabase import Client

from app.config import settings
from app.services.knowledge_service import knowledge_service
from app.services.material_service import MaterialService
from app.services.project_service import ProjectService
from app.services.prompt_service import prompt_service
from app.services.rule_service import rule_service
from app.services.voice_service import VoiceService

logger = logging.getLogger(__name__)

# Qwen Realtime WebSocket API 地址
QWEN_REALTIME_WS_URL = (
    "wss://dashscope.aliyuncs.com/api-ws/v1/inference"
)

# 有效的交互模式
VALID_MODES = {"question", "suggestion"}


class LiveSession:
    """活跃的路演会话信息，存储在内存中。"""

    def __init__(
        self,
        session_id: str,
        project_id: str,
        user_id: str,
        mode: str,
        style: str,
        voice: str,
        voice_type: str,
        call_id: str,
        ws_connection: Any | None,
        prompt_base: str,
        rules_content: str,
        knowledge_content: str,
        material_content: str,
        competition: str,
        track: str,
        group: str,
        stage: str,
    ):
        self.session_id = session_id
        self.project_id = project_id
        self.user_id = user_id
        self.mode = mode
        self.style = style
        self.voice = voice
        self.voice_type = voice_type
        self.call_id = call_id
        self.ws_connection = ws_connection
        self.prompt_base = prompt_base
        self.rules_content = rules_content
        self.knowledge_content = knowledge_content
        self.material_content = material_content
        self.competition = competition
        self.track = track
        self.group = group
        self.stage = stage
        self.created_at = datetime.now(timezone.utc)
        self.material_versions: dict = {}


# 活跃会话存储（内存字典）
_active_sessions: dict[str, LiveSession] = {}


class LivePresentationService:
    """现场路演服务。

    管理实时路演会话的完整生命周期：创建、模式切换、结束。
    使用 GetStream API 创建视频通话会话，
    使用 Qwen Realtime WebSocket 进行AI实时交互。
    """

    def __init__(self, supabase: Client) -> None:
        self._sb = supabase
        self._material_svc = MaterialService(supabase)
        self._project_svc = ProjectService(supabase)
        self._voice_svc = VoiceService(supabase)

    # ── 创建路演会话 ──────────────────────────────────────────

    async def start_session(
        self,
        project_id: str,
        user_id: str,
        mode: str = "question",
        style: str = "strict",
        voice: str = "Cherry",
        voice_type: str = "preset",
    ) -> dict:
        """创建现场路演会话。

        流程：
        1. 从MaterialService获取最新路演PPT
        2. 加载评审规则和路演知识库
        3. 通过PromptService组装prompt（含交互模式指令）
        4. 通过VoiceService获取音色参数
        5. 创建GetStream视频通话会话
        6. 建立Qwen Realtime WebSocket连接，发送session.update

        Args:
            project_id: 项目ID
            user_id: 用户ID
            mode: 交互模式（question/suggestion）
            style: 评委风格（strict/gentle/academic）
            voice: 音色标识
            voice_type: 音色类型（preset/custom）

        Returns:
            包含 session_id、call_id 等信息的字典

        Raises:
            HTTPException(400): 路演PPT未上传或参数无效
            HTTPException(503): 外部服务不可用
        """
        # 验证交互模式
        if mode not in VALID_MODES:
            raise HTTPException(
                status_code=400,
                detail=f"无效的交互模式 '{mode}'，仅支持: {', '.join(sorted(VALID_MODES))}",
            )

        # 1. 获取最新路演PPT
        presentation_ppt = await self._material_svc.get_latest(
            project_id, "presentation_ppt"
        )
        if not presentation_ppt:
            raise HTTPException(
                status_code=400,
                detail="请先上传路演PPT后再发起现场路演",
            )

        # 2. 获取项目信息
        project = await self._project_svc.get_project(project_id, user_id)

        # 3. 加载评审规则
        rules = rule_service.load_rules(
            project.competition, project.track, project.group
        )

        # 4. 加载知识库
        kb_presentation_ppt = knowledge_service.load_knowledge("presentation_ppt")
        kb_presentation = knowledge_service.load_knowledge("presentation")
        knowledge_content = "\n\n".join(
            part
            for part in [kb_presentation_ppt, kb_presentation]
            if part.strip()
        )

        # 5. 构建材料内容描述
        material_content = (
            f"路演PPT文件: {presentation_ppt['file_name']} "
            f"(版本 {presentation_ppt['version']})"
        )

        # 6. 组装Prompt（含交互模式指令）
        assembled_prompt = prompt_service.assemble_prompt(
            template_name="live_presentation",
            style_id=style,
            rules_content=rules.raw_content,
            knowledge_content=knowledge_content,
            material_content=material_content,
            interaction_mode=mode,
        )

        # 7. 获取音色参数
        voice_param = self._voice_svc.get_voice_for_session(voice, voice_type)

        # 8. 创建GetStream视频通话会话
        session_id = str(uuid.uuid4())
        call_id = f"live_{session_id[:8]}"

        call_info = await self._create_getstream_call(call_id, user_id)

        # 9. 建立Qwen Realtime WebSocket连接并发送session.update
        ws_connection = await self._create_qwen_realtime_session(
            assembled_prompt, voice_param, voice_type
        )

        # 10. 存储会话到内存
        session = LiveSession(
            session_id=session_id,
            project_id=project_id,
            user_id=user_id,
            mode=mode,
            style=style,
            voice=voice,
            voice_type=voice_type,
            call_id=call_id,
            ws_connection=ws_connection,
            prompt_base=assembled_prompt,
            rules_content=rules.raw_content,
            knowledge_content=knowledge_content,
            material_content=material_content,
            competition=project.competition,
            track=project.track,
            group=project.group,
            stage=project.current_stage,
        )
        session.material_versions = {
            "presentation_ppt": presentation_ppt["version"],
        }

        _active_sessions[session_id] = session

        return {
            "session_id": session_id,
            "call_id": call_id,
            "mode": mode,
            "style": style,
            "voice": voice,
            "voice_type": voice_type,
            "call_info": call_info,
        }

    # ── 切换交互模式 ──────────────────────────────────────────

    async def switch_mode(self, session_id: str, mode: str) -> dict:
        """切换路演交互模式（提问/建议）。

        仅替换prompt中的交互模式指令部分，保持角色描述和规则不变。

        Args:
            session_id: 会话ID
            mode: 新的交互模式（question/suggestion）

        Returns:
            包含更新后模式信息的字典

        Raises:
            HTTPException(400): 无效的模式
            HTTPException(404): 会话不存在
        """
        if mode not in VALID_MODES:
            raise HTTPException(
                status_code=400,
                detail=f"无效的交互模式 '{mode}'，仅支持: {', '.join(sorted(VALID_MODES))}",
            )

        session = _active_sessions.get(session_id)
        if not session:
            raise HTTPException(
                status_code=404,
                detail="路演会话不存在或已结束",
            )

        if session.mode == mode:
            return {"session_id": session_id, "mode": mode, "changed": False}

        # 重新组装prompt，仅交互模式指令部分变化
        new_prompt = prompt_service.assemble_prompt(
            template_name="live_presentation",
            style_id=session.style,
            rules_content=session.rules_content,
            knowledge_content=session.knowledge_content,
            material_content=session.material_content,
            interaction_mode=mode,
        )

        # 发送session.update到Qwen Realtime WebSocket
        await self._send_session_update(
            session.ws_connection,
            new_prompt,
            session.voice,
            session.voice_type,
        )

        # 更新会话状态
        session.mode = mode
        session.prompt_base = new_prompt

        return {"session_id": session_id, "mode": mode, "changed": True}

    # ── 结束路演会话 ──────────────────────────────────────────

    async def end_session(self, session_id: str) -> dict:
        """结束路演会话，生成评审总结并存储。

        Args:
            session_id: 会话ID

        Returns:
            包含评审总结信息的字典

        Raises:
            HTTPException(404): 会话不存在
        """
        session = _active_sessions.get(session_id)
        if not session:
            raise HTTPException(
                status_code=404,
                detail="路演会话不存在或已结束",
            )

        # 1. 关闭WebSocket连接
        if session.ws_connection is not None:
            try:
                await self._close_ws_connection(session.ws_connection)
            except Exception as exc:
                logger.warning("关闭WebSocket连接失败: %s", exc)

        # 2. 生成评审总结
        review_summary = self._generate_review_summary(session)

        # 3. 存储评审记录到Supabase reviews表
        now = datetime.now(timezone.utc).isoformat()
        try:
            review_row = (
                self._sb.table("reviews")
                .insert(
                    {
                        "project_id": session.project_id,
                        "user_id": session.user_id,
                        "review_type": "live_presentation",
                        "competition": session.competition,
                        "track": session.track,
                        "group": session.group,
                        "stage": session.stage,
                        "judge_style": session.style,
                        "total_score": None,
                        "material_versions": session.material_versions,
                        "status": "completed",
                        "created_at": session.created_at.isoformat(),
                        "completed_at": now,
                    }
                )
                .execute()
            )
            review_id = review_row.data[0]["id"]
        except Exception as exc:
            logger.exception("存储路演评审记录失败")
            review_id = None

        # 4. 从活跃会话中移除
        _active_sessions.pop(session_id, None)

        return {
            "session_id": session_id,
            "review_id": review_id,
            "summary": review_summary,
            "duration_seconds": (
                datetime.now(timezone.utc) - session.created_at
            ).total_seconds(),
        }

    # ── GetStream 视频通话 ────────────────────────────────────

    async def _create_getstream_call(
        self, call_id: str, user_id: str
    ) -> dict:
        """通过GetStream SDK创建视频通话会话。

        Args:
            call_id: 通话ID
            user_id: 创建者用户ID

        Returns:
            包含 call_id、token 等信息的字典

        Raises:
            HTTPException(503): GetStream API不可用
        """
        if not settings.getstream_api_key or not settings.getstream_api_secret:
            logger.warning("GetStream API未配置，返回模拟通话信息")
            return {
                "call_id": call_id,
                "call_type": "default",
                "token": "",
                "status": "mock",
            }

        try:
            client = Stream(
                api_key=settings.getstream_api_key,
                api_secret=settings.getstream_api_secret,
            )

            # 确保用户存在
            client.upsert_users(
                {"users": {user_id: {"id": user_id, "name": user_id}}}
            )

            # 创建视频通话
            call = client.video.call("default", call_id)
            response = call.get_or_create(
                data={
                    "created_by_id": user_id,
                    "settings_override": {
                        "audio": {"mic_default_on": True},
                        "video": {"camera_default_on": True},
                    },
                }
            )

            # 为用户生成访问 token
            token = client.create_token(user_id, expiration=3600)

            return {
                "call_id": call_id,
                "call_type": "default",
                "token": token,
                "status": "created",
            }
        except Exception as exc:
            logger.error("GetStream API调用失败: %s", exc)
            raise HTTPException(
                status_code=503,
                detail="创建视频通话失败，请稍后重试",
            ) from exc

    # ── Qwen Realtime WebSocket ───────────────────────────────

    async def _create_qwen_realtime_session(
        self,
        prompt: str,
        voice_param: str,
        voice_type: str,
    ) -> Any:
        """建立Qwen Realtime WebSocket连接并发送session.update。

        Args:
            prompt: 组装后的完整prompt
            voice_param: 音色参数值
            voice_type: 音色类型（preset/custom）

        Returns:
            WebSocket连接对象（或None如果API未配置）

        Raises:
            HTTPException(503): Qwen Realtime API不可用
        """
        if not settings.dashscope_api_key:
            logger.warning("DashScope API未配置，跳过WebSocket连接")
            return None

        try:
            import websockets

            ws_url = f"{QWEN_REALTIME_WS_URL}?model=qwen-omni-realtime"
            headers = {
                "Authorization": f"Bearer {settings.dashscope_api_key}",
            }

            ws = await websockets.connect(ws_url, extra_headers=headers)

            # 发送session.update事件
            session_update = self._build_session_update(
                prompt, voice_param, voice_type
            )
            await ws.send(json.dumps(session_update))

            return ws
        except ImportError:
            logger.warning("websockets库未安装，跳过WebSocket连接")
            return None
        except Exception as exc:
            logger.error("Qwen Realtime WebSocket连接失败: %s", exc)
            raise HTTPException(
                status_code=503,
                detail="AI实时交互服务暂时不可用，请稍后重试",
            ) from exc

    @staticmethod
    def _build_session_update(
        prompt: str,
        voice_param: str,
        voice_type: str,
    ) -> dict:
        """构建Qwen Realtime session.update事件消息。

        Args:
            prompt: 系统prompt
            voice_param: 音色参数值
            voice_type: 音色类型

        Returns:
            session.update事件JSON结构
        """
        session_config: dict[str, Any] = {
            "type": "session.update",
            "session": {
                "instructions": prompt,
                "voice": voice_param,
                "input_audio_format": "pcm16",
                "output_audio_format": "pcm16",
                "turn_detection": {
                    "type": "server_vad",
                },
            },
        }

        # 自定义音色需要额外设置TTS模型
        if voice_type == "custom":
            session_config["session"]["tts_model"] = "qwen3-tts-vc-realtime-2026-01-15"

        return session_config

    async def _send_session_update(
        self,
        ws_connection: Any,
        prompt: str,
        voice_param: str,
        voice_type: str,
    ) -> None:
        """向已有WebSocket连接发送session.update以更新prompt。

        Args:
            ws_connection: WebSocket连接对象
            prompt: 新的系统prompt
            voice_param: 音色参数值
            voice_type: 音色类型
        """
        if ws_connection is None:
            logger.warning("WebSocket连接不存在，跳过session.update")
            return

        session_update = self._build_session_update(
            prompt, voice_param, voice_type
        )

        try:
            await ws_connection.send(json.dumps(session_update))
        except Exception as exc:
            logger.error("发送session.update失败: %s", exc)
            raise HTTPException(
                status_code=503,
                detail="更新AI交互模式失败，请稍后重试",
            ) from exc

    @staticmethod
    async def _close_ws_connection(ws_connection: Any) -> None:
        """关闭WebSocket连接。"""
        if ws_connection is not None:
            try:
                await ws_connection.close()
            except Exception as exc:
                logger.warning("关闭WebSocket连接异常: %s", exc)

    # ── 评审总结生成 ──────────────────────────────────────────

    @staticmethod
    def _generate_review_summary(session: LiveSession) -> dict:
        """根据会话信息生成评审总结。

        Args:
            session: 路演会话对象

        Returns:
            评审总结字典
        """
        duration = (
            datetime.now(timezone.utc) - session.created_at
        ).total_seconds()

        return {
            "project_id": session.project_id,
            "style": session.style,
            "mode_history": session.mode,
            "voice": session.voice,
            "duration_seconds": duration,
            "competition": session.competition,
            "track": session.track,
            "group": session.group,
            "material_versions": session.material_versions,
        }


def get_active_sessions() -> dict[str, LiveSession]:
    """获取活跃会话字典的引用（用于测试和调试）。"""
    return _active_sessions
