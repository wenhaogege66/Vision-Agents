"""AI文本评审服务：获取材料→加载规则→组装Prompt→调用AI→解析结果→存储。

基于多模态AI（通义千问）分析文本PPT图像和BP文本内容，
按照赛事/赛道/组别的评审规则进行评分和建议生成。
"""

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException
from supabase import Client

from app.models.schemas import DimensionScore, ReviewResult
from app.services.knowledge_service import knowledge_service
from app.services.material_service import MaterialService
from app.services.project_service import ProjectService
from app.services.prompt_service import prompt_service
from app.services.rule_service import rule_service
from app.utils.ai_utils import FileParsingError, call_ai_api
from app.utils.dashscope_file import upload_file_to_dashscope
from app.utils.timing import TimingContext

logger = logging.getLogger(__name__)

# Supabase Storage bucket 名称
STORAGE_BUCKET = "materials"

# PPT 视觉评审 prompt 模板路径
_PPT_VISUAL_PROMPT_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "prompts"
    / "templates"
    / "ppt_visual_review.md"
)


class TextReviewService:
    """AI文本评审服务。

    协调 MaterialService、RuleService、KnowledgeService、PromptService
    完成文本评审的完整流程。
    """

    def __init__(self, supabase: Client) -> None:
        self._sb = supabase
        self._material_svc = MaterialService(supabase)
        self._project_svc = ProjectService(supabase)

    # 文本评审支持的材料类型
    VALID_MATERIAL_TYPES = {"text_ppt", "bp"}

    async def review(
        self,
        project_id: str,
        user_id: str,
        stage: str,
        judge_style: str = "strict",
        material_types: list[str] | None = None,
        auto_triggered: bool = False,
    ) -> ReviewResult:
        """执行文本评审完整流程。

        Args:
            project_id: 项目ID
            user_id: 用户ID
            stage: 当前比赛阶段
            judge_style: 评委风格（strict/gentle/academic）
            material_types: 指定使用的材料类型列表，为 None 时使用所有已就绪材料

        Returns:
            ReviewResult 评审结果

        Raises:
            HTTPException(400): 无可用材料
            HTTPException(503): AI API调用失败
        """
        # 1. 确定要使用的材料类型
        if material_types is not None:
            # 过滤无效类型
            requested = [mt for mt in material_types if mt in self.VALID_MATERIAL_TYPES]
            if not requested:
                raise HTTPException(
                    status_code=400,
                    detail="请先上传文本PPT或BP材料",
                )
        else:
            # 向后兼容：使用所有类型
            requested = list(self.VALID_MATERIAL_TYPES)

        tc = TimingContext()

        # 2. 加载请求的材料
        text_ppt = None
        bp = None

        if "text_ppt" in requested:
            text_ppt = await self._material_svc.get_latest(project_id, "text_ppt")
        if "bp" in requested:
            bp = await self._material_svc.get_latest(project_id, "bp")

        # 至少需要一种材料可用
        if not text_ppt and not bp:
            raise HTTPException(
                status_code=400,
                detail="请先上传文本PPT或BP材料",
            )

        # 2. 获取项目信息（赛事/赛道/组别）
        project = await self._project_svc.get_project(project_id, user_id)

        # 3. 加载评审规则
        rules = rule_service.load_rules(
            project.competition, project.track, project.group
        )

        # 4. 加载知识库
        kb_text_ppt = knowledge_service.load_knowledge("text_ppt")
        kb_bp = knowledge_service.load_knowledge("bp")
        knowledge_content = "\n\n".join(
            part for part in [kb_text_ppt, kb_bp] if part.strip()
        )

        # 5. 构建材料内容描述
        material_parts: list[str] = []
        has_bp = bp is not None
        has_text_ppt = text_ppt is not None

        if has_bp:
            material_parts.append(f"文本BP文件: {bp['file_name']} (版本 {bp['version']})")
        if has_text_ppt:
            material_parts.append(
                f"文本PPT文件: {text_ppt['file_name']} (版本 {text_ppt['version']})"
            )
        material_content = "\n".join(material_parts)

        missing_notes: list[str] = []
        if not has_bp:
            missing_notes.append("文本BP")
        if not has_text_ppt:
            missing_notes.append("文本PPT")
        if missing_notes:
            material_content += f"\n\n注意：本次评审未包含{'/'.join(missing_notes)}，仅基于已选材料进行评审。"

        # 6. 组装Prompt
        assembled_prompt = prompt_service.assemble_prompt(
            template_name="text_review",
            style_id=judge_style,
            rules_content=rules.raw_content,
            knowledge_content=knowledge_content,
            material_content=material_content,
        )

        # 7. 下载文件并上传到 DashScope，获取 file-id
        uploaded_files: list[dict] = []  # [{"file_id": ..., "label": ...}]

        materials_to_upload = []
        if has_text_ppt:
            materials_to_upload.append((text_ppt, "文本PPT"))
        if has_bp:
            materials_to_upload.append((bp, "BP"))

        failed_labels: list[str] = []
        for material, label in materials_to_upload:
            file_path = material.get("file_path")
            if not file_path:
                continue
            try:
                with tc.track(f"supabase_download_{label}"):
                    content = self._sb.storage.from_(STORAGE_BUCKET).download(file_path)
                file_name = file_path.rsplit("/", 1)[-1]
                with tc.track(f"dashscope_upload_{label}"):
                    fid = await upload_file_to_dashscope(content, file_name)
                uploaded_files.append({"file_id": fid, "label": label})
            except Exception as exc:
                logger.warning("下载/上传%s文件失败: %s, 错误: %s", label, file_path, exc)
                failed_labels.append(label)

        if not uploaded_files:
            failed_info = "、".join(failed_labels) if failed_labels else "所有材料"
            raise HTTPException(
                status_code=400,
                detail=f"以下材料文件在存储中不存在或已损坏：{failed_info}，请重新上传后再发起评审",
            )

        # 构建 Qwen-Long 消息（每个 fileid 单独一条 system message）
        # 如果某个文件解析失败，排除后重试
        with tc.track("qwen_long_review"):
            ai_response = await self._call_with_fallback(assembled_prompt, uploaded_files)

        # 8. 解析AI响应
        dimensions = self._parse_ai_response(ai_response)

        # 计算总分
        total_score = sum(d.score for d in dimensions)

        # 提取总体建议
        overall_suggestions = self._extract_overall_suggestions(ai_response)

        # 9. PPT 视觉评审（如果选择了 text_ppt）
        ppt_visual_review = None
        if has_text_ppt and text_ppt:
            with tc.track("qwen_vl_ppt_visual_review"):
                ppt_visual_review = await self._ppt_visual_review(text_ppt)

        # 10. 构建材料版本信息
        material_versions: dict = {}
        if has_text_ppt:
            material_versions["text_ppt"] = text_ppt["version"]
        if has_bp:
            material_versions["bp"] = bp["version"]

        # 11. 存储评审记录到 reviews 表
        now = datetime.now(timezone.utc).isoformat()
        try:
            with tc.track("supabase_insert_review"):
                review_row = (
                    self._sb.table("reviews")
                    .insert(
                        {
                            "project_id": project_id,
                            "user_id": user_id,
                            "review_type": "text_review",
                            "competition": project.competition,
                            "track": project.track,
                            "group": project.group,
                            "stage": stage,
                            "judge_style": judge_style,
                            "total_score": float(total_score),
                            "material_versions": material_versions,
                            "selected_materials": requested,
                            "ppt_visual_review": ppt_visual_review,
                            "auto_triggered": auto_triggered,
                            "status": "completed",
                            "created_at": now,
                        }
                    )
                    .execute()
                )
        except Exception as exc:
            logger.exception("存储评审记录失败")
            raise HTTPException(
                status_code=500, detail=f"存储评审记录失败: {exc}"
            ) from exc

        review_id = review_row.data[0]["id"]

        # 12. 存储评审维度详情到 review_details 表
        for dim in dimensions:
            try:
                self._sb.table("review_details").insert(
                    {
                        "review_id": review_id,
                        "dimension": dim.dimension,
                        "max_score": float(dim.max_score),
                        "score": float(dim.score),
                        "sub_items": dim.sub_items,
                        "suggestions": dim.suggestions,
                    }
                ).execute()
            except Exception as exc:
                logger.error(
                    "存储评审维度详情失败 (dimension=%s): %s",
                    dim.dimension,
                    exc,
                )

        # 13. 构建并返回 ReviewResult
        created_at_str = review_row.data[0].get("created_at", now)
        if isinstance(created_at_str, str):
            created_at = datetime.fromisoformat(
                created_at_str.replace("Z", "+00:00")
            )
        else:
            created_at = created_at_str

        logger.info("TextReviewService.review timing: %s", tc.summary())

        return ReviewResult(
            id=review_id,
            review_type="text_review",
            total_score=total_score,
            dimensions=dimensions,
            overall_suggestions=overall_suggestions,
            status="completed",
            created_at=created_at,
            ppt_visual_review=ppt_visual_review,
        )

    # ── PPT 视觉评审 ─────────────────────────────────────────────

    async def _ppt_visual_review(self, text_ppt: dict) -> dict | None:
        """使用 Qwen-VL-Max 对文本PPT进行视觉评审。

        流程：下载 PPT → 上传 DashScope OSS → 组装 prompt → 调用 Qwen-VL-Max → 解析结果。
        任何步骤失败时降级返回 None，不影响主评审流程。

        Args:
            text_ppt: 文本PPT材料记录（含 file_path 等字段）

        Returns:
            PPTVisualReviewResult 的 dict 表示，或 None（失败时）
        """
        try:
            # 1. 下载 PPT 文件
            file_path = text_ppt.get("file_path")
            if not file_path:
                logger.warning("PPT视觉评审跳过：text_ppt 缺少 file_path")
                return None

            content = self._sb.storage.from_(STORAGE_BUCKET).download(file_path)
            file_name = file_path.rsplit("/", 1)[-1]

            # 2. 上传到 DashScope OSS
            file_id = await upload_file_to_dashscope(content, file_name)

            # 3. 读取 prompt 模板
            if not _PPT_VISUAL_PROMPT_PATH.is_file():
                logger.warning("PPT视觉评审跳过：prompt 模板不存在: %s", _PPT_VISUAL_PROMPT_PATH)
                return None
            prompt_text = _PPT_VISUAL_PROMPT_PATH.read_text(encoding="utf-8")

            # 4. 组装消息并调用 Qwen-VL-Max
            messages: list[dict] = [
                {"role": "system", "content": prompt_text},
                {"role": "system", "content": f"fileid://{file_id}"},
                {"role": "user", "content": "请对这份PPT进行视觉评审，按照六个维度逐一评价并输出JSON结果。"},
            ]
            ai_response = await call_ai_api(
                messages, model="qwen-vl-max", multimodal=True
            )

            # 5. 解析结果
            result = self._parse_ppt_visual_response(ai_response)
            return result

        except Exception as exc:
            logger.error("PPT视觉评审失败（降级处理）: %s", exc)
            return None

    def _parse_ppt_visual_response(self, ai_response: dict) -> dict | None:
        """解析 Qwen-VL-Max 返回的 PPT 视觉评审结果。

        Args:
            ai_response: AI API 返回的完整 JSON 响应

        Returns:
            PPTVisualReviewResult 结构的 dict，解析失败返回 None
        """
        try:
            content = ai_response["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            logger.error("PPT视觉评审响应结构异常: %s", exc)
            return None

        parsed = self._extract_json(content)
        if parsed is None:
            logger.error("PPT视觉评审无法提取JSON: %s", content[:500])
            return None

        # 校验 dimensions 字段
        dimensions = parsed.get("dimensions", [])
        if not isinstance(dimensions, list) or len(dimensions) == 0:
            logger.error("PPT视觉评审缺少 dimensions 字段")
            return None

        overall_comment = parsed.get("overall_comment", "")

        return {
            "dimensions": dimensions,
            "overall_comment": overall_comment,
        }

    # ── AI 调用（含文件解析失败容错） ──────────────────────────

    async def _call_with_fallback(
        self, system_prompt: str, uploaded_files: list[dict]
    ) -> dict:
        """调用 AI API，如果某个文件解析失败则排除后重试。"""
        remaining = list(uploaded_files)

        while remaining:
            messages: list[dict] = [{"role": "system", "content": system_prompt}]
            for f in remaining:
                messages.append({"role": "system", "content": f"fileid://{f['file_id']}"})
            labels = "、".join(f["label"] for f in remaining)
            messages.append({"role": "user", "content": f"本次评审基于以下材料：{labels}。请按照评审规则进行评分。"})

            try:
                return await call_ai_api(messages, model="qwen-long", multimodal=False)
            except FileParsingError as exc:
                failed_fid = exc.file_id
                before_count = len(remaining)
                remaining = [f for f in remaining if failed_fid not in f["file_id"]]
                if len(remaining) == before_count:
                    remaining = remaining[1:]
                if remaining:
                    logger.warning("文件解析失败 (file-id=%s)，用剩余 %d 个文件重试", failed_fid, len(remaining))
                else:
                    raise HTTPException(
                        status_code=502,
                        detail=f"所有材料文件解析失败: {exc.message[:100]}",
                    ) from exc
            except RuntimeError as exc:
                logger.error("文本评审AI API调用失败: %s", exc)
                raise HTTPException(status_code=503, detail="AI评审服务暂时不可用，请稍后重试") from exc

        raise HTTPException(status_code=502, detail="无可用材料文件")

    # ── AI响应解析辅助方法 ────────────────────────────────────

    def _parse_ai_response(self, ai_response: dict) -> list[DimensionScore]:
        """从AI API响应中解析评审维度评分。

        Args:
            ai_response: AI API返回的完整JSON响应

        Returns:
            DimensionScore列表

        Raises:
            HTTPException(502): AI响应格式异常无法解析
        """
        # 提取AI回复文本内容
        try:
            content = (
                ai_response["choices"][0]["message"]["content"]
            )
        except (KeyError, IndexError, TypeError) as exc:
            logger.error("AI响应结构异常: %s", exc)
            raise HTTPException(
                status_code=502,
                detail="AI评审返回结果格式异常",
            ) from exc

        # 从内容中提取JSON
        parsed = self._extract_json(content)
        if parsed is None:
            logger.error("无法从AI响应中提取JSON: %s", content[:500])
            raise HTTPException(
                status_code=502,
                detail="AI评审返回结果无法解析",
            )

        # 解析dimensions数组
        raw_dimensions = parsed.get("dimensions", [])
        if not raw_dimensions:
            logger.error("AI响应中缺少dimensions字段")
            raise HTTPException(
                status_code=502,
                detail="AI评审返回结果缺少评分维度",
            )

        dimensions: list[DimensionScore] = []
        for raw in raw_dimensions:
            try:
                dim = DimensionScore(
                    dimension=raw.get("dimension", "未知维度"),
                    max_score=float(raw.get("max_score", 0)),
                    score=float(raw.get("score", 0)),
                    sub_items=raw.get("sub_items", []),
                    suggestions=raw.get("suggestions", []),
                )
                dimensions.append(dim)
            except (ValueError, TypeError) as exc:
                logger.warning("解析维度评分失败: %s, 错误: %s", raw, exc)
                continue

        return dimensions

    def _extract_overall_suggestions(self, ai_response: dict) -> list[str]:
        """从AI响应中提取总体建议。"""
        try:
            content = ai_response["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            return []

        parsed = self._extract_json(content)
        if parsed is None:
            return []

        suggestions = parsed.get("overall_suggestions", [])
        if isinstance(suggestions, list):
            return [str(s) for s in suggestions]
        return []

    @staticmethod
    def _extract_json(text: str) -> dict | None:
        """从文本中提取JSON对象，处理Markdown代码块包裹等情况。

        Args:
            text: 可能包含JSON的文本

        Returns:
            解析后的dict，解析失败返回None
        """
        # 尝试1：直接解析整个文本
        try:
            return json.loads(text)
        except (json.JSONDecodeError, TypeError):
            pass

        # 尝试2：提取Markdown代码块中的JSON
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

        # 尝试3：查找第一个 { 到最后一个 } 之间的内容
        first_brace = text.find("{")
        last_brace = text.rfind("}")
        if first_brace != -1 and last_brace > first_brace:
            try:
                return json.loads(text[first_brace : last_brace + 1])
            except (json.JSONDecodeError, TypeError):
                pass

        return None
