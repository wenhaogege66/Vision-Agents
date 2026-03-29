"""视频任务管理服务：创建、查询和管理 HeyGen 视频生成任务。"""

import hashlib
import logging

from fastapi import HTTPException
from supabase import Client

from app.services.avatar.heygen_video_service import HeyGenVideoService
from app.services.prompt_service import prompt_service

logger = logging.getLogger(__name__)

# 中文序数词映射（与 defense_service.py 保持一致）
ORDINALS = ["首先", "其次", "再者", "第四", "第五", "第六", "第七", "第八", "第九", "第十"]


class VideoTaskService:
    """视频任务管理服务。"""

    def __init__(self, supabase: Client) -> None:
        self._sb = supabase
        self._heygen = HeyGenVideoService()

    async def create_question_video_task(
        self, project_id: str, user_id: str, questions: list[dict],
        avatar_id: str | None = None, voice_id: str | None = None,
    ) -> dict:
        """创建提问视频生成任务。

        如果存在相同 config_hash（问题+形象+音色）的已完成视频，直接复用。
        """
        from app.config import settings as _settings

        # 计算 config_hash = md5(sorted_questions | avatar_id | voice_id)
        sorted_contents = sorted(q["content"] for q in questions)
        effective_avatar = avatar_id or _settings.heygen_video_avatar_id
        effective_voice = voice_id or _settings.heygen_video_voice_id
        hash_input = "|".join(sorted_contents) + f"||{effective_avatar}||{effective_voice}"
        config_hash = hashlib.md5(hash_input.encode()).hexdigest()

        # 检查是否有可复用的已完成视频
        try:
            existing = (
                self._sb.table("defense_video_tasks")
                .select("*")
                .eq("project_id", project_id)
                .eq("video_type", "question")
                .eq("config_hash", config_hash)
                .eq("status", "completed")
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )
            if existing.data and existing.data[0].get("persistent_url"):
                logger.info("复用已有视频: task_id=%s, config_hash=%s", existing.data[0]["id"], config_hash)
                return existing.data[0]
        except Exception:
            logger.warning("查询可复用视频失败，将重新生成", exc_info=True)

        # 加载话术模板
        speech_template = prompt_service.load_defense_template("question_speech")

        # 加载项目名称
        project_name = await self._load_project_name(project_id)

        # 格式化问题文本
        parts: list[str] = []
        for i, q in enumerate(questions):
            ordinal = ORDINALS[i] if i < len(ORDINALS) else f"第{i + 1}"
            parts.append(f"{ordinal}，{q['content']}")
        questions_text = "；".join(parts)

        # 替换模板占位符
        speech_text = speech_template.replace("{{project_name}}", project_name)
        speech_text = speech_text.replace("{{question_count}}", str(len(questions)))
        speech_text = speech_text.replace("{{questions_text}}", questions_text)

        # 调用 HeyGen 生成视频
        result = await self._heygen.generate_video(speech_text, avatar_id=avatar_id, voice_id=voice_id)

        # 同时保留旧的 questions_hash 以兼容
        questions_hash = hashlib.md5("|".join(sorted_contents).encode()).hexdigest()

        # 插入数据库记录
        try:
            row = (
                self._sb.table("defense_video_tasks")
                .insert({
                    "project_id": project_id,
                    "user_id": user_id,
                    "video_type": "question",
                    "heygen_video_id": result.video_id,
                    "status": "pending",
                    "questions_hash": questions_hash,
                    "config_hash": config_hash,
                })
                .execute()
            )
        except Exception as exc:
            logger.exception("插入视频任务记录失败")
            raise HTTPException(
                status_code=500, detail=f"创建视频任务失败: {exc}"
            ) from exc

        return row.data[0]

    async def create_feedback_video_task(
        self,
        project_id: str,
        user_id: str,
        defense_record_id: str,
        feedback_text: str,
    ) -> dict:
        """创建反馈视频生成任务。"""
        # 调用 HeyGen 生成视频
        result = await self._heygen.generate_video(feedback_text)

        # 插入数据库记录
        try:
            row = (
                self._sb.table("defense_video_tasks")
                .insert({
                    "project_id": project_id,
                    "user_id": user_id,
                    "video_type": "feedback",
                    "heygen_video_id": result.video_id,
                    "status": "pending",
                    "defense_record_id": defense_record_id,
                })
                .execute()
            )
        except Exception as exc:
            logger.exception("插入反馈视频任务记录失败")
            raise HTTPException(
                status_code=500, detail=f"创建反馈视频任务失败: {exc}"
            ) from exc

        task = row.data[0]

        # 回写 feedback_video_task_id 到 defense_records
        try:
            self._sb.table("defense_records").update({
                "feedback_video_task_id": task["id"],
                "feedback_type": "video",
            }).eq("id", defense_record_id).execute()
        except Exception:
            logger.warning("回写 feedback_video_task_id 失败: record_id=%s", defense_record_id, exc_info=True)

        return task

    async def get_task(self, task_id: str) -> dict | None:
        """查询单个视频任务。"""
        try:
            result = (
                self._sb.table("defense_video_tasks")
                .select("*")
                .eq("id", task_id)
                .execute()
            )
        except Exception as exc:
            logger.exception("查询视频任务失败")
            raise HTTPException(
                status_code=500, detail=f"查询视频任务失败: {exc}"
            ) from exc

        return result.data[0] if result.data else None

    async def get_latest_question_task(self, project_id: str) -> dict | None:
        """获取项目最新的提问视频任务。"""
        try:
            result = (
                self._sb.table("defense_video_tasks")
                .select("*")
                .eq("project_id", project_id)
                .eq("video_type", "question")
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )
        except Exception as exc:
            logger.exception("查询最新提问视频任务失败")
            raise HTTPException(
                status_code=500, detail=f"查询最新提问视频任务失败: {exc}"
            ) from exc

        return result.data[0] if result.data else None

    async def mark_outdated(self, project_id: str) -> None:
        """将项目所有 completed 状态的 question 类型任务标记为 outdated。"""
        try:
            (
                self._sb.table("defense_video_tasks")
                .update({"status": "outdated"})
                .eq("project_id", project_id)
                .eq("video_type", "question")
                .eq("status", "completed")
                .execute()
            )
        except Exception as exc:
            logger.exception("标记视频任务为 outdated 失败")
            raise HTTPException(
                status_code=500, detail=f"标记视频任务失败: {exc}"
            ) from exc

    async def check_has_active_task(self, project_id: str) -> bool:
        """检查项目是否有 pending/processing 状态的任务。"""
        try:
            result = (
                self._sb.table("defense_video_tasks")
                .select("id", count="exact")
                .eq("project_id", project_id)
                .in_("status", ["pending", "processing"])
                .execute()
            )
        except Exception as exc:
            logger.exception("检查活跃视频任务失败")
            raise HTTPException(
                status_code=500, detail=f"检查活跃视频任务失败: {exc}"
            ) from exc

        return (result.count or 0) > 0

    # ── 内部辅助方法 ──────────────────────────────────────────

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
