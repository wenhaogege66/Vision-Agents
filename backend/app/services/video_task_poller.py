"""后台视频任务轮询器：定期检查 HeyGen 视频生成状态并持久化完成的视频。"""

import asyncio
import logging
from datetime import datetime, timezone

import httpx
from supabase import Client

from app.services.avatar.heygen_video_service import HeyGenVideoService

logger = logging.getLogger(__name__)

# 超时阈值：创建超过 1 小时的任务标记为失败
_TIMEOUT_SECONDS = 3600


class VideoTaskPoller:
    """后台视频任务轮询器。

    作为 FastAPI lifespan 中的 asyncio task 运行，每 5 秒轮询一次
    所有 pending/processing 状态的视频任务，更新状态并持久化完成的视频。
    """

    def __init__(self, supabase: Client) -> None:
        self._sb = supabase
        self._heygen = HeyGenVideoService()
        self._running = False
        self._task: asyncio.Task | None = None

    def start(self) -> None:
        """启动轮询循环。"""
        self._running = True
        self._task = asyncio.create_task(self._poll_loop())
        logger.info("VideoTaskPoller started")

    def stop(self) -> None:
        """停止轮询循环。"""
        self._running = False
        if self._task is not None:
            self._task.cancel()
            logger.info("VideoTaskPoller stopped")

    async def _poll_loop(self) -> None:
        """轮询主循环：每 5 秒执行一次 poll_once。"""
        while self._running:
            await self.poll_once()
            await asyncio.sleep(5)

    async def poll_once(self) -> None:
        """执行一次轮询：查询所有活跃任务并逐个处理。"""
        try:
            result = (
                self._sb.table("defense_video_tasks")
                .select("*")
                .in_("status", ["pending", "processing"])
                .execute()
            )
            tasks = result.data or []
        except Exception:
            logger.exception("轮询查询视频任务失败")
            return

        for task in tasks:
            try:
                await self._process_task(task)
            except Exception:
                logger.exception(
                    "处理视频任务失败: task_id=%s", task.get("id")
                )

    async def _process_task(self, task: dict) -> None:
        """处理单个视频任务。"""
        task_id = task["id"]
        heygen_video_id = task["heygen_video_id"]
        created_at_str = task["created_at"]
        now = datetime.now(timezone.utc)

        # 检查超时：创建超过 1 小时则标记失败
        created_at = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
        if (now - created_at).total_seconds() > _TIMEOUT_SECONDS:
            logger.warning("视频任务超时: task_id=%s", task_id)
            self._sb.table("defense_video_tasks").update({
                "status": "failed",
                "error_message": "视频生成超时",
                "updated_at": now.isoformat(),
            }).eq("id", task_id).execute()
            return

        # 查询 HeyGen 视频状态
        status_result = await self._heygen.check_video_status(heygen_video_id)
        heygen_status = status_result.status

        if heygen_status == "completed":
            video_url = status_result.video_url
            logger.info(
                "视频生成完成: task_id=%s, video_url=%s",
                task_id,
                video_url[:80] if video_url else None,
            )
            persistent_url = await self._persist_video(task, video_url)
            self._sb.table("defense_video_tasks").update({
                "status": "completed",
                "persistent_url": persistent_url,
                "heygen_video_url": video_url,
                "updated_at": now.isoformat(),
            }).eq("id", task_id).execute()

        elif heygen_status == "failed":
            error_msg = getattr(status_result, "error", None) or "HeyGen 视频生成失败"
            logger.warning("视频生成失败: task_id=%s, error=%s", task_id, error_msg)
            self._sb.table("defense_video_tasks").update({
                "status": "failed",
                "error_message": error_msg,
                "updated_at": now.isoformat(),
            }).eq("id", task_id).execute()

        elif heygen_status == "processing" and task["status"] == "pending":
            # 从 pending 转为 processing
            logger.info("视频任务进入处理中: task_id=%s", task_id)
            self._sb.table("defense_video_tasks").update({
                "status": "processing",
                "updated_at": now.isoformat(),
            }).eq("id", task_id).execute()

    async def _persist_video(self, task: dict, video_url: str) -> str:
        """下载 HeyGen 视频并上传至 Supabase Storage，返回 persistent_url。"""
        task_id = task["id"]
        project_id = task["project_id"]
        storage_path = f"{project_id}/defense_videos/{task_id}.mp4"

        # 下载视频
        logger.info("下载视频: task_id=%s, url=%s", task_id, video_url[:80] if video_url else None)
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(video_url, timeout=120.0)
                resp.raise_for_status()
                video_data = resp.content
        except Exception as exc:
            logger.exception("视频下载失败: task_id=%s", task_id)
            raise RuntimeError(f"视频下载失败: {exc}") from exc

        # 上传到 Supabase Storage
        logger.info("上传视频到 Storage: path=%s, size=%d bytes", storage_path, len(video_data))
        try:
            self._sb.storage.from_("materials").upload(
                path=storage_path,
                file=video_data,
                file_options={"content-type": "video/mp4"},
            )
        except Exception as exc:
            logger.exception("视频上传失败: task_id=%s", task_id)
            raise RuntimeError(f"视频上传失败: {exc}") from exc

        # 获取公开 URL
        public_url = self._sb.storage.from_("materials").get_public_url(storage_path)
        logger.info("视频持久化完成: task_id=%s, persistent_url=%s", task_id, public_url)
        return public_url
