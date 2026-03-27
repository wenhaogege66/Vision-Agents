"""数字人问辩服务：问题 CRUD、AI 问题生成、答案提交与反馈生成、记录管理。"""

import json
import logging
import re
from datetime import datetime, timezone

from fastapi import HTTPException
from supabase import Client

from app.services.material_service import MaterialService
from app.services.stt_service import STTService
from app.utils.ai_utils import call_ai_api

logger = logging.getLogger(__name__)

# 中文序数词映射
ORDINALS = ["第一", "第二", "第三", "第四", "第五", "第六", "第七", "第八", "第九", "第十"]

QUESTION_GEN_SYSTEM_PROMPT = (
    "你是一位专业的创业大赛评委。请根据以下项目简介，生成3个评委提问。\n"
    "要求：每个问题不超过40个中文字符，问题应针对项目的核心价值、商业模式、技术可行性等方面。\n"
    '请以 JSON 数组格式返回，如：["问题1", "问题2", "问题3"]'
)

FEEDBACK_SYSTEM_PROMPT = (
    "你是一位专业的创业大赛评委。请根据以下项目信息和选手的回答，给出简短的评价反馈。\n"
    "反馈要求：20-60个中文字符，语言简洁有力，直击要点。请直接输出反馈文本，不要包含其他内容。"
)


def clamp_duration(d: int) -> int:
    """将回答时长钳制到 [10, 120] 范围。"""
    if d < 10:
        return 10
    if d > 120:
        return 120
    return d


def format_questions_speech(project_name: str, questions: list[dict]) -> str:
    """将问题列表组合为自然语言提问文本。

    Args:
        project_name: 项目名称
        questions: 问题列表，每个元素包含 "content" 字段

    Returns:
        组合后的自然语言提问文本
    """
    count = len(questions)
    parts: list[str] = []
    for i, q in enumerate(questions):
        ordinal = ORDINALS[i] if i < len(ORDINALS) else f"第{i + 1}"
        parts.append(f"{ordinal}，{q['content']}")

    questions_text = "；".join(parts)
    return (
        f"你好，我是数字人评委，对于你们的{project_name}项目，"
        f"我有以下{count}个问题：{questions_text}"
    )


class DefenseService:
    """数字人问辩服务。"""

    def __init__(self, supabase: Client) -> None:
        self._sb = supabase
        self._stt = STTService()
        self._material_svc = MaterialService(supabase)

    # ── 问题 CRUD ─────────────────────────────────────────────

    async def list_questions(self, project_id: str) -> list[dict]:
        """获取项目的预定义问题列表，按 sort_order 排序。"""
        try:
            result = (
                self._sb.table("defense_questions")
                .select("*")
                .eq("project_id", project_id)
                .order("sort_order")
                .execute()
            )
        except Exception as exc:
            logger.exception("查询问题列表失败")
            raise HTTPException(status_code=500, detail=f"查询问题列表失败: {exc}") from exc
        return result.data

    async def create_question(self, project_id: str, content: str) -> dict:
        """创建新的预定义问题，自动分配 sort_order。"""
        # 计算下一个 sort_order
        try:
            existing = (
                self._sb.table("defense_questions")
                .select("sort_order")
                .eq("project_id", project_id)
                .order("sort_order", desc=True)
                .limit(1)
                .execute()
            )
        except Exception as exc:
            logger.exception("查询最大 sort_order 失败")
            raise HTTPException(status_code=500, detail=f"查询排序失败: {exc}") from exc

        next_order = (existing.data[0]["sort_order"] + 1) if existing.data else 0

        try:
            result = (
                self._sb.table("defense_questions")
                .insert({
                    "project_id": project_id,
                    "content": content,
                    "sort_order": next_order,
                })
                .execute()
            )
        except Exception as exc:
            logger.exception("创建问题失败")
            raise HTTPException(status_code=500, detail=f"创建问题失败: {exc}") from exc

        return result.data[0]

    async def update_question(self, question_id: str, content: str) -> dict:
        """更新问题内容。"""
        now = datetime.now(timezone.utc).isoformat()
        try:
            result = (
                self._sb.table("defense_questions")
                .update({"content": content, "updated_at": now})
                .eq("id", question_id)
                .execute()
            )
        except Exception as exc:
            logger.exception("更新问题失败")
            raise HTTPException(status_code=500, detail=f"更新问题失败: {exc}") from exc

        if not result.data:
            raise HTTPException(status_code=404, detail="问题不存在")
        return result.data[0]

    async def delete_question(self, question_id: str) -> None:
        """删除问题。"""
        try:
            self._sb.table("defense_questions").delete().eq("id", question_id).execute()
        except Exception as exc:
            logger.exception("删除问题失败")
            raise HTTPException(status_code=500, detail=f"删除问题失败: {exc}") from exc

    # ── AI 问题自动生成 ───────────────────────────────────────

    async def generate_questions(self, project_id: str, profile: dict) -> list[dict]:
        """基于项目简介调用 AI 生成 3 个评委问题。

        Args:
            project_id: 项目 ID
            profile: 项目简介字典，包含 team_intro, domain, startup_status, achievements, next_goals

        Returns:
            插入数据库后的问题列表
        """
        user_content = (
            "项目简介：\n"
            f"- 团队介绍：{profile.get('team_intro') or '未提供'}\n"
            f"- 所属领域：{profile.get('domain') or '未提供'}\n"
            f"- 创业状态：{profile.get('startup_status') or '未提供'}\n"
            f"- 已有成果：{profile.get('achievements') or '未提供'}\n"
            f"- 下一步目标：{profile.get('next_goals') or '未提供'}"
        )

        messages = [
            {"role": "system", "content": QUESTION_GEN_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ]

        try:
            ai_response = await call_ai_api(messages, model="qwen-long", multimodal=False)
        except RuntimeError as exc:
            logger.error("AI 问题生成失败: %s", exc)
            raise HTTPException(status_code=502, detail="AI 问题生成失败，请稍后重试") from exc

        # 解析 AI 响应
        try:
            content = ai_response["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            logger.error("AI 响应结构异常: %s", exc)
            raise HTTPException(status_code=502, detail="AI 问题生成返回格式异常") from exc

        questions = self._parse_questions_json(content)

        # 截断超过 40 字的问题
        questions = [q[:40] for q in questions]

        # 批量插入数据库
        created: list[dict] = []
        for i, q_content in enumerate(questions):
            try:
                result = (
                    self._sb.table("defense_questions")
                    .insert({
                        "project_id": project_id,
                        "content": q_content,
                        "sort_order": i,
                    })
                    .execute()
                )
                created.append(result.data[0])
            except Exception as exc:
                logger.warning("插入生成的问题失败: %s", exc)

        return created

    @staticmethod
    def _parse_questions_json(text: str) -> list[str]:
        """从 AI 响应文本中解析问题 JSON 数组。"""
        # 直接尝试解析
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return [str(q) for q in parsed if q]
        except (json.JSONDecodeError, TypeError):
            pass

        # 尝试从 code block 中提取
        code_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
        if code_match:
            try:
                parsed = json.loads(code_match.group(1).strip())
                if isinstance(parsed, list):
                    return [str(q) for q in parsed if q]
            except (json.JSONDecodeError, TypeError):
                pass

        # 尝试提取 JSON 数组
        first_bracket = text.find("[")
        last_bracket = text.rfind("]")
        if first_bracket != -1 and last_bracket > first_bracket:
            try:
                parsed = json.loads(text[first_bracket : last_bracket + 1])
                if isinstance(parsed, list):
                    return [str(q) for q in parsed if q]
            except (json.JSONDecodeError, TypeError):
                pass

        logger.warning("无法解析 AI 生成的问题: %s", text[:200])
        return []

    # ── 答案提交与反馈生成 ─────────────────────────────────────

    async def submit_answer(
        self,
        project_id: str,
        user_id: str,
        audio_content: bytes,
        answer_duration: int,
    ) -> dict:
        """提交用户回答音频，执行 STT 转写和 AI 反馈生成。

        Args:
            project_id: 项目 ID
            user_id: 用户 ID
            audio_content: 音频文件字节内容
            answer_duration: 回答时长（秒）

        Returns:
            创建的 defense_record 字典
        """
        answer_duration = clamp_duration(answer_duration)

        # 获取当前问题快照
        questions = await self.list_questions(project_id)
        questions_snapshot = [
            {"content": q["content"], "sort_order": q["sort_order"]}
            for q in questions
        ]

        # STT 转写
        try:
            user_answer_text = await self._stt.transcribe(audio_content, "audio/webm")
        except RuntimeError as exc:
            logger.error("STT 转写失败: %s", exc)
            # 记录失败状态
            record = await self._insert_record(
                project_id=project_id,
                user_id=user_id,
                questions_snapshot=questions_snapshot,
                user_answer_text=None,
                ai_feedback_text=None,
                answer_duration=answer_duration,
                status="failed",
            )
            raise HTTPException(status_code=502, detail="语音识别失败，请重试") from exc

        # 加载项目简介和项目名称
        profile = await self._load_profile(project_id)
        project_name = await self._load_project_name(project_id)

        # 构建 AI 反馈 prompt
        questions_text = "\n".join(
            f"{i + 1}. {q['content']}" for i, q in enumerate(questions)
        )

        feedback_user_content = (
            f"项目名称：{project_name}\n"
            f"项目简介：{profile or '未提供'}\n"
            f"评委问题：\n{questions_text}\n"
            f"选手回答：{user_answer_text}"
        )

        messages = [
            {"role": "system", "content": FEEDBACK_SYSTEM_PROMPT},
            {"role": "user", "content": feedback_user_content},
        ]

        # 生成 AI 反馈
        ai_feedback_text = None
        status = "completed"
        try:
            ai_response = await call_ai_api(messages, model="qwen-long", multimodal=False)
            ai_feedback_text = ai_response["choices"][0]["message"]["content"].strip()
        except Exception as exc:
            logger.error("AI 反馈生成失败: %s", exc)
            status = "failed"

        # 插入记录
        record = await self._insert_record(
            project_id=project_id,
            user_id=user_id,
            questions_snapshot=questions_snapshot,
            user_answer_text=user_answer_text,
            ai_feedback_text=ai_feedback_text,
            answer_duration=answer_duration,
            status=status,
        )

        return record

    async def _insert_record(
        self,
        project_id: str,
        user_id: str,
        questions_snapshot: list[dict],
        user_answer_text: str | None,
        ai_feedback_text: str | None,
        answer_duration: int,
        status: str,
    ) -> dict:
        """插入 defense_record 记录。"""
        try:
            result = (
                self._sb.table("defense_records")
                .insert({
                    "project_id": project_id,
                    "user_id": user_id,
                    "questions_snapshot": questions_snapshot,
                    "user_answer_text": user_answer_text,
                    "ai_feedback_text": ai_feedback_text,
                    "answer_duration": answer_duration,
                    "status": status,
                })
                .execute()
            )
        except Exception as exc:
            logger.exception("插入问辩记录失败")
            raise HTTPException(status_code=500, detail=f"保存问辩记录失败: {exc}") from exc

        return result.data[0]

    # ── 记录查询 ──────────────────────────────────────────────

    async def list_records(self, project_id: str) -> list[dict]:
        """获取项目的问辩记录列表，按 created_at 倒序。"""
        try:
            result = (
                self._sb.table("defense_records")
                .select("*")
                .eq("project_id", project_id)
                .order("created_at", desc=True)
                .execute()
            )
        except Exception as exc:
            logger.exception("查询问辩记录失败")
            raise HTTPException(status_code=500, detail=f"查询问辩记录失败: {exc}") from exc
        return result.data

    # ── 内部辅助方法 ──────────────────────────────────────────

    async def _load_profile(self, project_id: str) -> str | None:
        """加载项目简介文本摘要。"""
        try:
            result = (
                self._sb.table("project_profiles")
                .select("team_intro, domain, startup_status, achievements, next_goals")
                .eq("project_id", project_id)
                .limit(1)
                .execute()
            )
        except Exception:
            logger.warning("加载项目简介失败", exc_info=True)
            return None

        if not result.data:
            return None

        p = result.data[0]
        parts = []
        if p.get("team_intro"):
            parts.append(f"团队介绍：{p['team_intro']}")
        if p.get("domain"):
            parts.append(f"领域：{p['domain']}")
        if p.get("startup_status"):
            parts.append(f"创业状态：{p['startup_status']}")
        if p.get("achievements"):
            parts.append(f"已有成果：{p['achievements']}")
        if p.get("next_goals"):
            parts.append(f"下一步目标：{p['next_goals']}")
        return "；".join(parts) if parts else None

    async def _load_project_name(self, project_id: str) -> str:
        """加载项目名称。"""
        try:
            result = (
                self._sb.table("projects")
                .select("name")
                .eq("id", project_id)
                .limit(1)
                .execute()
            )
        except Exception:
            logger.warning("加载项目名称失败", exc_info=True)
            return "未知项目"

        if result.data:
            return result.data[0].get("name", "未知项目")
        return "未知项目"
