"""AI 项目简介提取服务：从 BP 和文本 PPT 中提取结构化项目简介。

调用通义千问 API 分析材料内容，提取团队介绍、所属领域、创业状态、
已有成果、产品链接、下一步目标等结构化字段，存储到 project_profiles 表。
"""

import json
import logging
import re
from datetime import datetime, timezone

from fastapi import HTTPException
from supabase import Client

from app.services.material_service import MaterialService
from app.utils.ai_utils import FileParsingError, call_ai_api
from app.utils.dashscope_file import upload_file_to_dashscope

logger = logging.getLogger(__name__)

STORAGE_BUCKET = "materials"

EXTRACTION_SYSTEM_PROMPT = (
    "你是一个专业的项目信息提取助手。请从用户提供的商业计划书（BP）和文本PPT内容中，"
    "提取以下六个结构化字段。如果某个字段在材料中找不到相关信息，请返回 null。\n\n"
    "请严格以 JSON 格式返回，不要包含其他文字：\n"
    "{\n"
    '  "team_intro": "团队介绍（成员背景、分工等）",\n'
    '  "domain": "所属领域（如人工智能、生物医药、教育科技等）",\n'
    '  "startup_status": "创业状态（如初创期、成长期、已注册公司等）",\n'
    '  "achievements": "已有成果（如专利、获奖、用户数据等）",\n'
    '  "product_links": "产品链接（如官网、演示地址、应用商店链接等）",\n'
    '  "next_goals": "下一步目标（如融资计划、市场拓展、产品迭代等）"\n'
    "}"
)


class ProfileService:
    """AI 项目简介提取与管理服务。"""

    def __init__(self, supabase: Client) -> None:
        self._sb = supabase
        self._material_svc = MaterialService(supabase)

    async def extract_profile(self, project_id: str) -> dict:
        """从 BP 和文本 PPT 中提取结构化项目简介。"""
        bp = await self._material_svc.get_latest(project_id, "bp")
        text_ppt = await self._material_svc.get_latest(project_id, "text_ppt")

        if not bp and not text_ppt:
            raise HTTPException(
                status_code=400,
                detail="请先上传 BP 或文本 PPT 材料后再提取项目简介",
            )

        # 下载文件并上传到 DashScope，获取 file-id
        # 每个文件独立处理，失败不影响其他文件
        uploaded_files: list[dict] = []  # [{"file_id": ..., "desc": ..., "type": ...}]

        for material, label in [(text_ppt, "text_ppt"), (bp, "bp")]:
            if not material:
                continue
            file_path = material.get("file_path")
            if not file_path:
                continue
            try:
                logger.info("开始处理%s: %s", label, file_path)
                content = self._sb.storage.from_(STORAGE_BUCKET).download(file_path)
                file_name = file_path.rsplit("/", 1)[-1]
                logger.info("%s下载成功: %s (%.1fMB)", label, file_path, len(content) / 1024 / 1024)
                fid = await upload_file_to_dashscope(content, file_name)
                desc = f"{material['file_name']}（版本 {material['version']}）"
                uploaded_files.append({"file_id": fid, "desc": desc, "type": label})
            except Exception as exc:
                logger.warning("下载/上传%s文件失败: %s, 错误: %s", label, file_path, exc)

        if not uploaded_files:
            raise HTTPException(status_code=502, detail="无法从存储服务下载材料文件，请稍后重试")

        # 调用 AI，如果某个文件解析失败则排除后重试
        extracted = await self._call_with_fallback(uploaded_files)

        # 构建材料版本信息
        source_versions: dict = {}
        if bp:
            source_versions["bp"] = bp["version"]
        if text_ppt:
            source_versions["text_ppt"] = text_ppt["version"]

        # Upsert 到 project_profiles 表
        now = datetime.now(timezone.utc).isoformat()
        profile_data = {
            "project_id": project_id,
            "team_intro": extracted.get("team_intro"),
            "domain": extracted.get("domain"),
            "startup_status": extracted.get("startup_status"),
            "achievements": extracted.get("achievements"),
            "product_links": extracted.get("product_links"),
            "next_goals": extracted.get("next_goals"),
            "is_ai_generated": True,
            "source_material_versions": source_versions,
            "updated_at": now,
        }

        try:
            result = (
                self._sb.table("project_profiles")
                .upsert(profile_data, on_conflict="project_id")
                .execute()
            )
        except Exception as exc:
            logger.exception("保存项目简介失败")
            raise HTTPException(status_code=500, detail=f"保存项目简介失败: {exc}") from exc

        return result.data[0]

    async def _call_with_fallback(self, uploaded_files: list[dict]) -> dict:
        """调用 AI API，如果某个文件解析失败则排除后重试。"""
        remaining = list(uploaded_files)

        while remaining:
            messages = self._build_messages(remaining)
            try:
                return await self._call_ai_for_extraction(messages)
            except FileParsingError as exc:
                # 找到解析失败的文件并排除
                failed_fid = exc.file_id
                before_count = len(remaining)
                remaining = [f for f in remaining if failed_fid not in f["file_id"]]
                if len(remaining) == before_count:
                    # 无法匹配到具体文件，移除第一个试试
                    logger.warning("无法匹配解析失败的 file-id=%s，移除第一个文件重试", failed_fid)
                    remaining = remaining[1:]
                if remaining:
                    removed_desc = [f["desc"] for f in uploaded_files if f not in remaining]
                    logger.warning("文件解析失败，已排除: %s，用剩余 %d 个文件重试", removed_desc, len(remaining))
                else:
                    raise HTTPException(
                        status_code=502,
                        detail=f"所有材料文件解析失败，AI 无法处理。错误: {exc.message[:100]}",
                    ) from exc

        raise HTTPException(status_code=502, detail="无可用材料文件")

    @staticmethod
    def _build_messages(files: list[dict]) -> list[dict]:
        """构建 Qwen-Long 消息，每个 fileid 单独一条 system message。"""
        messages: list[dict] = [
            {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
        ]
        # 每个文件单独一条 system message（DashScope 官方推荐格式）
        for f in files:
            messages.append({"role": "system", "content": f"fileid://{f['file_id']}"})

        descs = "、".join(f["desc"] for f in files)
        messages.append({"role": "user", "content": f"请从以上{descs}材料中提取项目简介的六个结构化字段。"})
        return messages

    async def get_profile(self, project_id: str) -> dict | None:
        """查询项目简介。"""
        try:
            result = (
                self._sb.table("project_profiles")
                .select("*")
                .eq("project_id", project_id)
                .limit(1)
                .execute()
            )
        except Exception as exc:
            logger.exception("查询项目简介失败")
            raise HTTPException(status_code=500, detail=f"查询项目简介失败: {exc}") from exc

        if result and result.data:
            return result.data[0]
        return None

    async def update_profile(self, project_id: str, data: dict) -> dict:
        """更新项目简介（用户手动编辑）。"""
        now = datetime.now(timezone.utc).isoformat()
        update_data = {**data, "is_ai_generated": False, "updated_at": now}

        try:
            result = (
                self._sb.table("project_profiles")
                .update(update_data)
                .eq("project_id", project_id)
                .execute()
            )
        except Exception as exc:
            logger.exception("更新项目简介失败")
            raise HTTPException(status_code=500, detail=f"更新项目简介失败: {exc}") from exc

        if not result.data:
            raise HTTPException(status_code=404, detail="项目简介不存在")
        return result.data[0]

    async def _call_ai_for_extraction(self, messages: list[dict]) -> dict:
        """调用 AI API 提取项目简介字段。

        Raises:
            FileParsingError: 文件解析失败（由调用方处理）
            HTTPException(503): AI 服务不可用
            HTTPException(502): AI 响应格式异常
        """
        try:
            ai_response = await call_ai_api(messages, model="qwen-long", multimodal=False)
        except FileParsingError:
            raise  # 让调用方处理
        except RuntimeError as exc:
            logger.error("AI 简介提取 API 调用失败: %s", exc)
            raise HTTPException(status_code=503, detail="AI服务暂时不可用，请稍后重试") from exc

        try:
            content = ai_response["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            logger.error("AI 响应结构异常: %s", exc)
            raise HTTPException(status_code=502, detail="AI简介提取返回结果格式异常") from exc

        parsed = self._extract_json(content)
        if parsed is None:
            logger.error("无法从 AI 响应中提取 JSON: %s", content[:500])
            raise HTTPException(status_code=502, detail="AI简介提取返回结果无法解析")

        fields = ["team_intro", "domain", "startup_status", "achievements", "product_links", "next_goals"]
        return {f: (str(parsed[f]) if parsed.get(f) is not None else None) for f in fields}

    @staticmethod
    def _extract_json(text: str) -> dict | None:
        """从文本中提取 JSON 对象。"""
        try:
            return json.loads(text)
        except (json.JSONDecodeError, TypeError):
            pass

        code_block_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
        if code_block_match:
            try:
                return json.loads(code_block_match.group(1).strip())
            except (json.JSONDecodeError, TypeError):
                pass

        first_brace = text.find("{")
        last_brace = text.rfind("}")
        if first_brace != -1 and last_brace > first_brace:
            try:
                return json.loads(text[first_brace : last_brace + 1])
            except (json.JSONDecodeError, TypeError):
                pass

        return None
