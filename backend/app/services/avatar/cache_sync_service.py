"""HeyGen avatar/voice 缓存同步服务。

负责从 HeyGen API 拉取 avatar 和 voice 数据，upsert 到本地 Supabase 缓存表，
清理过期记录，并维护同步元数据。
"""

import asyncio
import logging
from datetime import datetime, timezone

import httpx
from fastapi import HTTPException
from supabase import Client

from app.config import settings
from app.services.avatar.heygen_video_service import (
    HEYGEN_AVATAR_GROUP_AVATARS_URL,
    HEYGEN_AVATAR_GROUPS_URL,
    HEYGEN_AVATARS_URL,
    HEYGEN_VOICES_URL,
    HeyGenVideoService,
)

logger = logging.getLogger(__name__)

# 同步间隔阈值（秒）
SYNC_INTERVAL_SECONDS = 24 * 60 * 60  # 24 hours


class CacheSyncService:
    """HeyGen avatar/voice 缓存同步服务。"""

    def __init__(self, supabase: Client):
        self._sb = supabase
        self._lock = asyncio.Lock()
        self._syncing = False

    # ── 公开方法 ──────────────────────────────────────────────

    async def maybe_sync(self) -> bool:
        """检查是否需要同步（>24h 或从未同步），需要则执行。返回是否执行了同步。"""
        try:
            resp = (
                self._sb.table("heygen_sync_metadata")
                .select("last_sync_at")
                .eq("resource_type", "avatar")
                .single()
                .execute()
            )
            row = resp.data
        except Exception:
            logger.warning("查询 sync_metadata 失败（可能是网络问题），跳过本次同步检查")
            return False

        need_sync = False
        if row is None or row.get("last_sync_at") is None:
            need_sync = True
        else:
            last_sync_str = row["last_sync_at"]
            try:
                last_sync = datetime.fromisoformat(last_sync_str.replace("Z", "+00:00"))
                elapsed = (datetime.now(timezone.utc) - last_sync).total_seconds()
                if elapsed > SYNC_INTERVAL_SECONDS:
                    need_sync = True
            except (ValueError, TypeError):
                need_sync = True

        if need_sync:
            async with self._lock:
                await self._do_full_sync()
            return True
        return False

    async def force_sync(self) -> None:
        """强制执行全量同步（手动触发）。如果锁被占用则抛出异常。"""
        if self._lock.locked():
            raise HTTPException(status_code=409, detail="同步正在进行中")
        async with self._lock:
            await self._do_full_sync()

    async def get_sync_status(self) -> dict:
        """查询最近一次同步状态。"""
        try:
            resp = (
                self._sb.table("heygen_sync_metadata")
                .select("*")
                .in_("resource_type", ["avatar", "voice"])
                .execute()
            )
            rows = resp.data or []
        except Exception:
            logger.error("查询 sync_metadata 失败", exc_info=True)
            rows = []

        result: dict = {
            "avatar_last_sync_at": None,
            "avatar_last_sync_status": "never",
            "avatar_count": 0,
            "voice_last_sync_at": None,
            "voice_last_sync_status": "never",
            "voice_count": 0,
        }
        for row in rows:
            rt = row.get("resource_type")
            if rt == "avatar":
                result["avatar_last_sync_at"] = row.get("last_sync_at")
                result["avatar_last_sync_status"] = row.get("last_sync_status", "never")
                result["avatar_count"] = row.get("avatar_count", 0)
            elif rt == "voice":
                result["voice_last_sync_at"] = row.get("last_sync_at")
                result["voice_last_sync_status"] = row.get("last_sync_status", "never")
                result["voice_count"] = row.get("voice_count", 0)
        return result

    def is_syncing(self) -> bool:
        """返回当前是否正在同步。"""
        return self._syncing

    # ── 内部方法 ──────────────────────────────────────────────

    async def _do_full_sync(self) -> None:
        """执行全量同步：拉取 HeyGen 数据 → upsert → 清理过期 → 更新元数据。

        Avatar 和 Voice 同步互相独立，一个失败不影响另一个。
        """
        self._syncing = True
        try:
            # ── Avatar 同步 ──
            try:
                avatar_list, avatar_ids = await self._sync_avatars()
                await self._upsert_avatars(avatar_list)
                await self._cleanup_stale("heygen_avatar_cache", "heygen_avatar_id", avatar_ids)
                await self._update_metadata("avatar", "success", len(avatar_list))
                logger.info("Avatar 缓存同步完成: %d 条", len(avatar_list))
            except Exception as exc:
                logger.error("Avatar 缓存同步失败: %s", exc, exc_info=True)
                try:
                    await self._update_metadata("avatar", "failed", 0, error=str(exc))
                except Exception:
                    logger.error("更新 avatar 失败状态元数据时出错", exc_info=True)

            # ── Voice 同步 ──
            try:
                voice_list, voice_ids = await self._sync_voices()
                await self._upsert_voices(voice_list)
                await self._cleanup_stale("heygen_voice_cache", "heygen_voice_id", voice_ids)
                await self._update_metadata("voice", "success", len(voice_list))
                logger.info("Voice 缓存同步完成: %d 条", len(voice_list))
            except Exception as exc:
                logger.error("Voice 缓存同步失败: %s", exc, exc_info=True)
                try:
                    await self._update_metadata("voice", "failed", 0, error=str(exc))
                except Exception:
                    logger.error("更新 voice 失败状态元数据时出错", exc_info=True)
        finally:
            self._syncing = False

    async def _sync_avatars(self) -> tuple[list[dict], set[str]]:
        """从 HeyGen API 拉取所有 avatar，返回 (avatar_list, seen_ids)。

        逻辑与 HeyGenVideoService.list_avatars() 完全一致：
        1. avatar_group.list → 每个 group 的 avatars（is_custom=True）
        2. /v2/avatars 获取公共 avatar（跳过已见 id，is_custom=False）
        """
        if not settings.heygen_api_key:
            raise RuntimeError("HeyGen API Key 未配置")

        headers = {"X-Api-Key": settings.heygen_api_key, "Accept": "application/json"}
        result: list[dict] = []
        seen_ids: set[str] = set()

        # ── 1. 用户自有 avatar（通过 avatar group API）──
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.get(HEYGEN_AVATAR_GROUPS_URL, headers=headers)
                resp.raise_for_status()
            groups = resp.json().get("data", {}).get("avatar_group_list", [])

            for group in groups:
                if not isinstance(group, dict):
                    continue
                group_id = group.get("id", "")
                group_name = group.get("name", "")
                group_type = group.get("group_type", "")
                preview_image = group.get("preview_image", "")

                avatar_type = "photo_avatar" if group_type == "PHOTO" else "digital_twin"

                try:
                    async with httpx.AsyncClient(timeout=60.0) as client:
                        group_resp = await client.get(
                            f"{HEYGEN_AVATAR_GROUP_AVATARS_URL}/{group_id}/avatars",
                            headers=headers,
                        )
                        group_resp.raise_for_status()
                    resp_data = group_resp.json().get("data", {})
                    # API 可能返回 avatar_list 或 avatars
                    avatar_list = resp_data.get("avatar_list", []) or resp_data.get("avatars", [])

                    logger.info(
                        "Avatar group %s (%s, type=%s): 返回 %d 个 avatar, raw keys=%s",
                        group_id, group_name, group_type, len(avatar_list),
                        list(resp_data.keys()),
                    )

                    for a in avatar_list:
                        if not isinstance(a, dict):
                            continue
                        # 兼容不同字段名: id / avatar_id
                        aid = a.get("id", "") or a.get("avatar_id", "")
                        if not aid or aid in seen_ids:
                            continue
                        seen_ids.add(aid)
                        result.append({
                            "heygen_avatar_id": aid,
                            "name": a.get("name", "") or a.get("avatar_name", "") or group_name,
                            "preview_image_url": a.get("image_url", "") or a.get("preview_image_url", "") or preview_image,
                            "avatar_type": avatar_type,
                            "is_custom": True,
                            "group_id": group_id,
                            "status": "active",
                            "default_voice_id": a.get("default_voice_id"),
                        })
                except Exception:
                    logger.warning("获取 avatar group %s 内 avatar 失败", group_id, exc_info=True)
        except Exception:
            logger.warning("获取用户 avatar groups 失败，仅同步公共 avatar", exc_info=True)

        # ── 2. 公共 avatar（通过 /v2/avatars）──
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.get(HEYGEN_AVATARS_URL, headers=headers)
                resp.raise_for_status()
            body = resp.json()
            data = body.get("data", {})
            avatars = data.get("avatars", []) if isinstance(data, dict) else data if isinstance(data, list) else []

            for a in avatars:
                if not isinstance(a, dict):
                    continue
                aid = a.get("avatar_id", "")
                if not aid or aid in seen_ids:
                    continue
                seen_ids.add(aid)
                result.append({
                    "heygen_avatar_id": aid,
                    "name": a.get("avatar_name", ""),
                    "preview_image_url": a.get("preview_image_url", ""),
                    "avatar_type": HeyGenVideoService._map_avatar_type(a.get("avatar_type", "")),
                    "is_custom": False,
                    "group_id": None,
                    "status": "active",
                    "default_voice_id": a.get("default_voice_id"),
                })
        except Exception:
            logger.warning("获取公共 avatar 列表失败", exc_info=True)

        return result, seen_ids

    async def _sync_voices(self) -> tuple[list[dict], set[str]]:
        """从 HeyGen API 拉取所有 voice，返回 (voice_list, seen_ids)。"""
        if not settings.heygen_api_key:
            raise RuntimeError("HeyGen API Key 未配置")

        headers = {"X-Api-Key": settings.heygen_api_key, "Accept": "application/json"}
        result: list[dict] = []
        seen_ids: set[str] = set()

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.get(HEYGEN_VOICES_URL, headers=headers)
                resp.raise_for_status()
            body = resp.json()
            data = body.get("data", {})
            voices = data.get("voices", []) if isinstance(data, dict) else data if isinstance(data, list) else []

            for v in voices:
                if not isinstance(v, dict):
                    continue
                vid = v.get("voice_id", "")
                if not vid or vid in seen_ids:
                    continue
                seen_ids.add(vid)
                result.append({
                    "heygen_voice_id": vid,
                    "name": v.get("name") or v.get("display_name", ""),
                    "language": v.get("language", ""),
                    "gender": v.get("gender", ""),
                    "preview_audio": v.get("preview_audio", ""),
                    "is_custom": v.get("is_custom", False),
                })
        except Exception:
            logger.warning("获取 voice 列表失败", exc_info=True)

        return result, seen_ids

    async def _upsert_avatars(self, avatars: list[dict]) -> None:
        """批量 upsert avatar 到 heygen_avatar_cache。"""
        now = datetime.now(timezone.utc).isoformat()
        for avatar in avatars:
            avatar["synced_at"] = now
            avatar["updated_at"] = now
            self._sb.table("heygen_avatar_cache").upsert(
                avatar, on_conflict="heygen_avatar_id"
            ).execute()

    async def _upsert_voices(self, voices: list[dict]) -> None:
        """批量 upsert voice 到 heygen_voice_cache。"""
        now = datetime.now(timezone.utc).isoformat()
        for voice in voices:
            voice["synced_at"] = now
            voice["updated_at"] = now
            self._sb.table("heygen_voice_cache").upsert(
                voice, on_conflict="heygen_voice_id"
            ).execute()

    async def _cleanup_stale(self, table: str, id_column: str, valid_ids: set[str]) -> None:
        """删除不在 valid_ids 中的记录。

        Supabase client 不直接支持 NOT IN，所以先查出所有 id，计算差集后逐条删除。
        """
        if not valid_ids:
            # 如果 valid_ids 为空，说明 API 返回了空数据，清空整张表
            # 但为安全起见，仅在有数据时才清理
            return

        try:
            resp = self._sb.table(table).select(id_column).execute()
            existing_rows = resp.data or []
            existing_ids = {row[id_column] for row in existing_rows if row.get(id_column)}

            stale_ids = existing_ids - valid_ids
            if stale_ids:
                for stale_id in stale_ids:
                    self._sb.table(table).delete().eq(id_column, stale_id).execute()
                logger.info("清理 %s 中 %d 条过期记录", table, len(stale_ids))
        except Exception:
            logger.error("清理 %s 过期记录失败", table, exc_info=True)
            raise

    async def _update_metadata(
        self, resource_type: str, status: str, count: int, error: str | None = None
    ) -> None:
        """更新 heygen_sync_metadata。"""
        now = datetime.now(timezone.utc).isoformat()
        data: dict = {
            "resource_type": resource_type,
            "last_sync_status": status,
        }
        if status == "success":
            data["last_sync_at"] = now
            data["last_sync_error"] = None
        if status == "failed":
            data["last_sync_error"] = (error or "Unknown error")[:500]

        if resource_type == "avatar":
            data["avatar_count"] = count
        elif resource_type == "voice":
            data["voice_count"] = count

        self._sb.table("heygen_sync_metadata").upsert(
            data, on_conflict="resource_type"
        ).execute()
