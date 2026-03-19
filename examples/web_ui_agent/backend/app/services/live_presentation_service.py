"""现场路演服务：使用 vision-agents 框架让 AI 评委加入 GetStream 视频通话。

参考 examples/01_simple_agent_example 的实现：
- Agent + getstream.Edge() + qwen.Realtime() 创建 AI 评委
- agent.create_call() 创建通话
- agent.join(call) 让 Agent 通过 WebRTC 加入通话
- edge.open_demo() 的逻辑生成人类用户的 join URL
"""

import asyncio
import logging
import os
import secrets
import uuid
from datetime import datetime, timezone
from urllib.parse import urlencode

from fastapi import HTTPException
from supabase import Client
from vision_agents.core import Agent, User
from vision_agents.plugins import getstream, qwen

from app.config import settings
from app.services.knowledge_service import knowledge_service
from app.services.material_service import MaterialService
from app.services.project_service import ProjectService
from app.services.prompt_service import prompt_service
from app.services.rule_service import rule_service
from app.services.voice_service import VoiceService

logger = logging.getLogger(__name__)

VALID_MODES = {"question", "suggestion"}


def _ensure_stream_env() -> None:
    """getstream SDK 读 STREAM_ 前缀环境变量，后端 .env 用 GETSTREAM_ 前缀，做桥接。"""
    if not os.environ.get("STREAM_API_KEY") and settings.getstream_api_key:
        os.environ["STREAM_API_KEY"] = settings.getstream_api_key
    if not os.environ.get("STREAM_API_SECRET") and settings.getstream_api_secret:
        os.environ["STREAM_API_SECRET"] = settings.getstream_api_secret


class LiveSession:
    """活跃的路演会话。"""

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
        agent: Agent | None,
        agent_task: asyncio.Task | None,
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
        self.agent = agent
        self.agent_task = agent_task
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


_active_sessions: dict[str, LiveSession] = {}
_share_tokens: dict[str, dict] = {}


class LivePresentationService:
    def __init__(self, supabase: Client) -> None:
        self._sb = supabase
        self._material_svc = MaterialService(supabase)
        self._project_svc = ProjectService(supabase)
        self._voice_svc = VoiceService(supabase)

    async def start_session(
        self,
        project_id: str,
        user_id: str,
        mode: str = "question",
        style: str = "strict",
        voice: str = "Cherry",
        voice_type: str = "preset",
    ) -> dict:
        if mode not in VALID_MODES:
            raise HTTPException(
                status_code=400,
                detail=f"无效的交互模式 '{mode}'，仅支持: {', '.join(sorted(VALID_MODES))}",
            )

        _ensure_stream_env()

        # 获取路演PPT
        presentation_ppt = await self._material_svc.get_latest(project_id, "presentation_ppt")
        if not presentation_ppt:
            raise HTTPException(status_code=400, detail="请先上传路演PPT后再发起现场路演")

        # 获取项目信息
        project = await self._project_svc.get_project(project_id, user_id)

        # 加载评审规则 & 知识库
        rules = rule_service.load_rules(project.competition, project.track, project.group)
        kb_ppt = knowledge_service.load_knowledge("presentation_ppt")
        kb_pres = knowledge_service.load_knowledge("presentation")
        knowledge_content = "\n\n".join(p for p in [kb_ppt, kb_pres] if p.strip())

        material_content = (
            f"路演PPT文件: {presentation_ppt['file_name']} "
            f"(版本 {presentation_ppt['version']})"
        )

        assembled_prompt = prompt_service.assemble_prompt(
            template_name="live_presentation",
            style_id=style,
            rules_content=rules.raw_content,
            knowledge_content=knowledge_content,
            material_content=material_content,
            interaction_mode=mode,
        )

        session_id = str(uuid.uuid4())
        call_id = f"live_{session_id[:8]}"

        # 创建 Agent，让它加入通话，生成人类用户的 join URL
        agent, agent_task, join_url = await self._launch_agent(
            call_id=call_id,
            user_id=user_id,
            instructions=assembled_prompt,
        )

        session = LiveSession(
            session_id=session_id,
            project_id=project_id,
            user_id=user_id,
            mode=mode,
            style=style,
            voice=voice,
            voice_type=voice_type,
            call_id=call_id,
            agent=agent,
            agent_task=agent_task,
            prompt_base=assembled_prompt,
            rules_content=rules.raw_content,
            knowledge_content=knowledge_content,
            material_content=material_content,
            competition=project.competition,
            track=project.track,
            group=project.group,
            stage=project.current_stage,
        )
        session.material_versions = {"presentation_ppt": presentation_ppt["version"]}
        _active_sessions[session_id] = session

        return {
            "session_id": session_id,
            "call_id": call_id,
            "mode": mode,
            "style": style,
            "voice": voice,
            "voice_type": voice_type,
            "call_info": {"call_id": call_id, "join_url": join_url, "status": "created"},
        }


    async def _launch_agent(
        self, call_id: str, user_id: str, instructions: str
    ) -> tuple[Agent, asyncio.Task, str]:
        """创建 vision-agents Agent 并在后台启动加入通话。

        完全参照 01_simple_agent_example 的模式：
        1. 创建 Agent(edge=getstream.Edge(), llm=qwen.Realtime())
        2. agent.create_call() 创建通话
        3. 后台 asyncio.Task 中 agent.join(call) 让 Agent 通过 WebRTC 加入
        4. 复用 edge.open_demo 的逻辑为人类用户生成 join URL
        """
        try:
            _ensure_stream_env()

            edge = getstream.Edge()
            llm = qwen.Realtime(
                fps=1,
                api_key=settings.dashscope_api_key,
                base_url="wss://dashscope.aliyuncs.com/api-ws/v1/realtime",
            )

            agent = Agent(
                edge=edge,
                agent_user=User(name="AI评委", id=f"agent_{call_id}"),
                instructions=instructions,
                processors=[],
                llm=llm,
            )

            # 创建通话（内部先 authenticate agent user，再调 edge.create_call）
            call = await agent.create_call("default", call_id)

            # 为人类用户生成 join URL（复用 open_demo 逻辑，但不打开浏览器）
            join_url = await self._build_join_url(edge, call, user_id)

            # 后台任务：Agent 加入通话并保持在线
            async def _run_agent():
                try:
                    async with agent.join(call):
                        logger.info("AI评委 Agent 已加入通话: %s", call_id)
                        await agent.simple_response(
                            "你好，我是本次路演的AI评委。请开始你的路演展示，"
                            "我会认真听取并在结束后给出评价。"
                        )
                        await agent.finish()
                except asyncio.CancelledError:
                    logger.info("Agent 任务被取消 (call_id=%s)", call_id)
                except Exception:
                    logger.exception("Agent 运行异常 (call_id=%s)", call_id)

            agent_task = asyncio.create_task(_run_agent())
            return agent, agent_task, join_url

        except Exception as exc:
            logger.error("创建 Agent 失败: %s", exc, exc_info=True)
            raise HTTPException(status_code=503, detail=f"创建AI评委失败: {exc}") from exc

    async def _build_join_url(self, edge: getstream.Edge, call, user_id: str) -> str:
        """为人类用户生成 GetStream demo 会议室 URL。

        逻辑与 stream_edge_transport.py 中 open_demo() 一致，
        但不调用 webbrowser.open()。
        """
        client = edge.client  # AsyncStream

        human_id = f"user_{user_id[:8]}"
        await client.create_user(name="路演者", id=human_id)
        token = client.create_token(human_id, expiration=3600)

        base_url = "https://getstream.io/video/demos/join/"
        params = {
            "api_key": client.api_key,
            "token": token,
            "skip_lobby": "true",
            "user_name": "路演者",
            "video_encoder": "h264",
            "bitrate": 12000000,
            "w": 1920,
            "h": 1080,
            "channel_type": "messaging",
        }
        url = f"{base_url}{call.id}?{urlencode(params)}"
        logger.info("生成 GetStream 会议室 URL: %s", url)
        return url


    async def switch_mode(self, session_id: str, mode: str) -> dict:
        if mode not in VALID_MODES:
            raise HTTPException(
                status_code=400,
                detail=f"无效的交互模式 '{mode}'，仅支持: {', '.join(sorted(VALID_MODES))}",
            )
        session = _active_sessions.get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="路演会话不存在或已结束")
        if session.mode == mode:
            return {"session_id": session_id, "mode": mode, "changed": False}

        new_prompt = prompt_service.assemble_prompt(
            template_name="live_presentation",
            style_id=session.style,
            rules_content=session.rules_content,
            knowledge_content=session.knowledge_content,
            material_content=session.material_content,
            interaction_mode=mode,
        )

        if session.agent:
            try:
                label = "提问模式" if mode == "question" else "建议模式"
                await session.agent.simple_response(f"现在切换到{label}，请按照新模式继续互动。")
            except Exception as exc:
                logger.warning("发送模式切换提示失败: %s", exc)

        session.mode = mode
        session.prompt_base = new_prompt
        return {"session_id": session_id, "mode": mode, "changed": True}

    async def end_session(self, session_id: str) -> dict:
        session = _active_sessions.get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="路演会话不存在或已结束")

        # 取消后台任务
        if session.agent_task and not session.agent_task.done():
            session.agent_task.cancel()
            try:
                await session.agent_task
            except (asyncio.CancelledError, Exception):
                pass

        # 关闭 Agent
        if session.agent and not session.agent.closed:
            try:
                await session.agent.close()
            except Exception as exc:
                logger.warning("关闭 Agent 失败: %s", exc)

        review_summary = self._generate_review_summary(session)

        now = datetime.now(timezone.utc).isoformat()
        review_id = None
        try:
            row = (
                self._sb.table("reviews")
                .insert({
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
                })
                .execute()
            )
            review_id = row.data[0]["id"]
        except Exception:
            logger.exception("存储路演评审记录失败")

        _active_sessions.pop(session_id, None)
        return {
            "session_id": session_id,
            "review_id": review_id,
            "summary": review_summary,
            "duration_seconds": (datetime.now(timezone.utc) - session.created_at).total_seconds(),
        }

    async def generate_share_link(self, session_id: str, base_url: str) -> dict:
        session = _active_sessions.get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="路演会话不存在或已结束")
        share_token = secrets.token_urlsafe(32)
        share_url = f"{base_url.rstrip('/')}/live/join/{share_token}"
        _share_tokens[share_token] = {
            "session_id": session_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "expires_in": 3600,
        }
        return {"share_url": share_url, "expires_in": 3600}

    @staticmethod
    def _generate_review_summary(session: LiveSession) -> dict:
        duration = (datetime.now(timezone.utc) - session.created_at).total_seconds()
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
    return _active_sessions


def get_share_tokens() -> dict[str, dict]:
    return _share_tokens
