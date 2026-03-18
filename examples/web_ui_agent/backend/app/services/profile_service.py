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
from app.utils.ai_utils import call_ai_api
from app.utils.dashscope_file import upload_file_to_dashscope

logger = logging.getLogger(__name__)

# Supabase Storage bucket 名称
STORAGE_BUCKET = "materials"

# AI 提取 Prompt
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

    # ── 提取项目简介 ──────────────────────────────────────────

    async def extract_profile(self, project_id: str) -> dict:
        """从 BP 和文本 PPT 中提取结构化项目简介。

        查询 project_materials 中 is_latest=True 的 bp 和 text_ppt，
        调用 AI API 提取六个结构化字段，upsert 到 project_profiles 表。

        Args:
            project_id: 项目 ID

        Returns:
            项目简介字典（匹配 ProjectProfile schema）

        Raises:
            HTTPException(400): 无可用材料
            HTTPException(503): AI 服务不可用
        """
        # 1. 获取最新的 bp 和 text_ppt 材料
        bp = await self._material_svc.get_latest(project_id, "bp")
        text_ppt = await self._material_svc.get_latest(project_id, "text_ppt")

        if not bp and not text_ppt:
            raise HTTPException(
                status_code=400,
                detail="请先上传 BP 或文本 PPT 材料后再提取项目简介",
            )

        # 2. 下载文件并上传到 DashScope，获取 file-id
        file_ids: list[str] = []
        file_descriptions: list[str] = []

        # 文本 PPT
        if text_ppt:
            file_path = text_ppt.get("file_path")
            if file_path:
                try:
                    logger.info("开始处理文本PPT: %s", file_path)
                    content = self._sb.storage.from_(STORAGE_BUCKET).download(file_path)
                    file_name = file_path.rsplit("/", 1)[-1]
                    logger.info("文本PPT下载成功: %s (%.1fMB)", file_path, len(content) / 1024 / 1024)
                    fid = await upload_file_to_dashscope(content, file_name)
                    file_ids.append(fid)
                    file_descriptions.append(f"文本PPT: {text_ppt['file_name']}（版本 {text_ppt['version']}）")
                except Exception as exc:
                    logger.warning("下载/上传文本PPT文件失败: %s, 错误: %s", file_path, exc)

        # BP
        if bp:
            file_path = bp.get("file_path")
            if file_path:
                try:
                    logger.info("开始处理BP: %s", file_path)
                    content = self._sb.storage.from_(STORAGE_BUCKET).download(file_path)
                    file_name = file_path.rsplit("/", 1)[-1]
                    logger.info("BP下载成功: %s (%.1fMB)", file_path, len(content) / 1024 / 1024)
                    fid = await upload_file_to_dashscope(content, file_name)
                    file_ids.append(fid)
                    file_descriptions.append(f"商业计划书（BP）: {bp['file_name']}（版本 {bp['version']}）")
                except Exception as exc:
                    logger.warning("下载/上传BP文件失败: %s, 错误: %s", file_path, exc)

        if not file_ids:
            raise HTTPException(
                status_code=502,
                detail="无法从存储服务下载材料文件，请稍后重试",
            )

        # 3. 构建 Qwen-Long 消息（通过 fileid:// 引用文档）
        fileid_refs = ",".join(f"fileid://{fid}" for fid in file_ids)
        material_desc = "、".join(file_descriptions)

        messages = [
            {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
            {"role": "system", "content": fileid_refs},
            {"role": "user", "content": f"请从以上{material_desc}材料中提取项目简介的六个结构化字段。"},
        ]

        # 4. 调用 Qwen-Long（文档理解模型，非视觉模型）
        extracted = await self._call_ai_for_extraction(messages, model="qwen-long")

        # 5. 构建材料版本信息
        source_versions: dict = {}
        if bp:
            source_versions["bp"] = bp["version"]
        if text_ppt:
            source_versions["text_ppt"] = text_ppt["version"]

        # 6. Upsert 到 project_profiles 表
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
            raise HTTPException(
                status_code=500, detail=f"保存项目简介失败: {exc}"
            ) from exc

        return result.data[0]

    # ── 获取项目简介 ──────────────────────────────────────────

    async def get_profile(self, project_id: str) -> dict | None:
        """查询项目简介。

        Args:
            project_id: 项目 ID

        Returns:
            项目简介字典，不存在则返回 None
        """
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
            raise HTTPException(
                status_code=500, detail=f"查询项目简介失败: {exc}"
            ) from exc

        if result and result.data:
            return result.data[0]
        return None

    # ── 更新项目简介（用户编辑） ──────────────────────────────

    async def update_profile(self, project_id: str, data: dict) -> dict:
        """更新项目简介（用户手动编辑）。

        将 is_ai_generated 设为 False，表示内容已被用户修改。

        Args:
            project_id: 项目 ID
            data: 要更新的字段字典

        Returns:
            更新后的项目简介字典

        Raises:
            HTTPException(404): 项目简介不存在
        """
        now = datetime.now(timezone.utc).isoformat()
        update_data = {
            **data,
            "is_ai_generated": False,
            "updated_at": now,
        }

        try:
            result = (
                self._sb.table("project_profiles")
                .update(update_data)
                .eq("project_id", project_id)
                .execute()
            )
        except Exception as exc:
            logger.exception("更新项目简介失败")
            raise HTTPException(
                status_code=500, detail=f"更新项目简介失败: {exc}"
            ) from exc

        if not result.data:
            raise HTTPException(status_code=404, detail="项目简介不存在")

        return result.data[0]

    # ── AI 提取辅助方法 ───────────────────────────────────────

    async def _call_ai_for_extraction(self, messages: list[dict], model: str | None = None) -> dict:
        """调用 AI API 提取项目简介字段。

        Args:
            messages: OpenAI 格式的消息列表
            model: 模型名称（如 qwen-long）

        Returns:
            包含六个结构化字段的字典

        Raises:
            HTTPException(503): AI 服务不可用
            HTTPException(502): AI 响应格式异常
        """
        try:
            ai_response = await call_ai_api(messages, model=model, multimodal=False)
        except RuntimeError as exc:
            logger.error("AI 简介提取 API 调用失败: %s", exc)
            raise HTTPException(
                status_code=503,
                detail="AI服务暂时不可用，请稍后重试",
            ) from exc

        # 解析 AI 响应
        try:
            content = ai_response["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            logger.error("AI 响应结构异常: %s", exc)
            raise HTTPException(
                status_code=502,
                detail="AI简介提取返回结果格式异常",
            ) from exc

        parsed = self._extract_json(content)
        if parsed is None:
            logger.error("无法从 AI 响应中提取 JSON: %s", content[:500])
            raise HTTPException(
                status_code=502,
                detail="AI简介提取返回结果无法解析",
            )

        # 确保返回的字段都是字符串或 None
        fields = [
            "team_intro",
            "domain",
            "startup_status",
            "achievements",
            "product_links",
            "next_goals",
        ]
        result: dict = {}
        for field in fields:
            value = parsed.get(field)
            result[field] = str(value) if value is not None else None

        return result

    @staticmethod
    def _extract_json(text: str) -> dict | None:
        """从文本中提取 JSON 对象，处理 Markdown 代码块包裹等情况。"""
        # 尝试1：直接解析
        try:
            return json.loads(text)
        except (json.JSONDecodeError, TypeError):
            pass

        # 尝试2：提取 Markdown 代码块中的 JSON
        code_block_match = re.search(
            r"```(?:json)?\s*\n?(.*?)\n?\s*```",
            text,
            re.DOTALL,
        )
        if code_block_match:
            try:
                return json.loads(code_block_match.group(1).strip())
            except (json.JSONDecodeError, TypeError):
                pass

        # 尝试3：查找第一个 { 到最后一个 }
        first_brace = text.find("{")
        last_brace = text.rfind("}")
        if first_brace != -1 and last_brace > first_brace:
            try:
                return json.loads(text[first_brace : last_brace + 1])
            except (json.JSONDecodeError, TypeError):
                pass

        return None
