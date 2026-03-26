"""离线路演评审服务：获取路演PPT+视频/音频→STT转录→加载规则→组装Prompt→调用AI→PPT视觉评审→解析结果→存储。

基于多模态AI（通义千问）分析路演视频/音频和路演PPT图像，
按照赛事/赛道/组别的评审规则生成综合评审报告，
包含演讲表现评价、PPT内容评价、PPT视觉评审、路演者评价、综合评分和改进建议。
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
from app.services.stt_service import STTService
from app.utils.ai_utils import DEFAULT_VIDEO_TIMEOUT, call_ai_api
from app.utils.dashscope_file import upload_file_to_dashscope
from app.utils.storage_utils import download_and_upload_to_dashscope
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

# 文件扩展名到 MIME 类型的映射
_EXT_TO_MIME: dict[str, str] = {
    ".mp4": "audio/mp4",
    ".webm": "audio/mp4",
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".m4a": "audio/x-m4a",
    ".aac": "audio/aac",
}


class OfflineReviewService:
    """离线路演评审服务。

    协调 MaterialService、RuleService、KnowledgeService、PromptService、STTService
    完成离线路演评审的完整流程。
    """

    def __init__(self, supabase: Client) -> None:
        self._sb = supabase
        self._material_svc = MaterialService(supabase)
        self._project_svc = ProjectService(supabase)
        self._stt_svc = STTService()

    async def review(
        self,
        project_id: str,
        user_id: str,
        stage: str,
        judge_style: str = "strict",
    ) -> ReviewResult:
        """执行离线路演评审完整流程。

        Args:
            project_id: 项目ID
            user_id: 用户ID
            stage: 当前比赛阶段
            judge_style: 评委风格（strict/gentle/academic）

        Returns:
            ReviewResult 评审结果

        Raises:
            HTTPException(400): 路演PPT未上传或视频/音频均未上传
            HTTPException(502): STT转录失败
            HTTPException(503): AI API调用失败
        """
        # 1. 获取最新路演PPT
        presentation_ppt = await self._material_svc.get_latest(
            project_id, "presentation_ppt"
        )
        if not presentation_ppt:
            raise HTTPException(
                status_code=400,
                detail="请先上传路演PPT后再发起离线路演评审",
            )

        # 2. 获取路演视频和路演音频（至少需要一种）
        presentation_video = await self._material_svc.get_latest(
            project_id, "presentation_video"
        )
        presentation_audio = await self._material_svc.get_latest(
            project_id, "presentation_audio"
        )

        if not presentation_video and not presentation_audio:
            raise HTTPException(
                status_code=400,
                detail="请先上传路演视频或路演音频后再发起离线评审",
            )

        # 优先使用视频，其次使用音频
        media_material = presentation_video or presentation_audio

        tc = TimingContext()

        # 3. 下载媒体文件并进行 STT 转录
        media_path = media_material["file_path"]
        try:
            with tc.track("supabase_download_media"):
                media_content = self._sb.storage.from_(STORAGE_BUCKET).download(media_path)
        except Exception as exc:
            logger.error("下载媒体文件失败: %s, 错误: %s", media_path, exc)
            raise HTTPException(
                status_code=502,
                detail="无法下载媒体文件，请稍后重试",
            ) from exc

        # 根据文件扩展名确定 MIME 类型
        ext = "." + media_path.rsplit(".", 1)[-1].lower() if "." in media_path else ""
        mime_type = _EXT_TO_MIME.get(ext, "audio/mp4")

        try:
            with tc.track("stt_deepgram_transcribe"):
                stt_transcript = await self._stt_svc.transcribe(media_content, mime_type)
        except RuntimeError as exc:
            logger.error("STT 转录失败: %s", exc)
            raise HTTPException(
                status_code=502,
                detail="语音转文字失败，请检查音频质量或稍后重试",
            ) from exc

        # 4. 获取项目信息（赛事/赛道/组别）
        project = await self._project_svc.get_project(project_id, user_id)

        # 5. 加载评审规则
        rules = rule_service.load_rules(
            project.competition, project.track, project.group
        )

        # 6. 加载知识库
        kb_presentation_ppt = knowledge_service.load_knowledge("presentation_ppt")
        kb_presentation = knowledge_service.load_knowledge("presentation")
        knowledge_content = "\n\n".join(
            part
            for part in [kb_presentation_ppt, kb_presentation]
            if part.strip()
        )

        # 7. 构建材料内容描述（包含转录文本和路演者评价要求）
        media_label = "路演视频" if presentation_video else "路演音频"
        material_content = (
            f"路演PPT文件: {presentation_ppt['file_name']} "
            f"(版本 {presentation_ppt['version']})\n"
            f"{media_label}文件: {media_material['file_name']} "
            f"(版本 {media_material['version']})\n\n"
            f"## 路演语音转录文本\n\n{stt_transcript}\n\n"
            f"## 路演表现评价要求\n\n"
            f"请基于以上转录文本，对路演者的路演表现进行专项评价，"
            f"输出以下维度的评价结果（JSON格式，字段名为英文）：\n"
            f"- language_expression（语言表达）：评价路演者的用词准确性、表达流畅度、专业术语使用\n"
            f"- rhythm_control（节奏控制）：评价路演者的语速、停顿、时间分配\n"
            f"- logic_clarity（逻辑清晰度）：评价路演者的论述逻辑、层次感、过渡衔接\n"
            f"- engagement（互动感）：评价路演者的感染力、与听众的互动意识\n"
            f"- overall_comment（总体评价）：对路演者表现的综合评价\n"
            f"- suggestions（改进建议）：具体可操作的改进建议列表\n\n"
            f"请在评审结果JSON中增加 presenter_evaluation 字段，包含以上维度。"
        )

        # 8. 组装Prompt
        assembled_prompt = prompt_service.assemble_prompt(
            template_name="offline_review",
            style_id=judge_style,
            rules_content=rules.raw_content,
            knowledge_content=knowledge_content,
            material_content=material_content,
        )

        # 9. 构建多模态消息并调用AI API
        user_content: list[dict] = []

        # 路演视频（上传到 DashScope 临时 OSS）— 仅当有视频时
        if presentation_video:
            video_path = presentation_video["file_path"]
            try:
                with tc.track("dashscope_upload_video"):
                    video_oss_url = await download_and_upload_to_dashscope(
                        self._sb, STORAGE_BUCKET, video_path
                    )
                user_content.append(
                    {"type": "video_url", "video_url": {"url": video_oss_url}}
                )
            except Exception as exc:
                logger.error("下载/上传路演视频失败: %s, 错误: %s", video_path, exc)
                raise HTTPException(
                    status_code=502,
                    detail="无法上传路演视频到 AI 服务，请稍后重试",
                ) from exc

        user_content.append(
            {
                "type": "text",
                "text": (
                    "请结合路演转录文本和路演PPT进行综合评审。"
                    "评审报告需包含：演讲表现评价、PPT内容评价、综合评分、改进建议，"
                    "以及路演者表现评价（presenter_evaluation）。"
                ),
            }
        )

        messages = [
            {"role": "system", "content": assembled_prompt},
            {"role": "user", "content": user_content},
        ]

        # 调用AI API（视频分析使用更长超时）
        try:
            with tc.track("qwen_long_review"):
                ai_response = await call_ai_api(
                    messages, timeout=DEFAULT_VIDEO_TIMEOUT
                )
        except RuntimeError as exc:
            logger.error("离线路演评审AI API调用失败: %s", exc)
            raise HTTPException(
                status_code=503,
                detail="AI评审服务暂时不可用，请稍后重试",
            ) from exc

        # 10. 解析AI响应
        dimensions = self._parse_ai_response(ai_response)

        # 计算总分
        total_score = sum(d.score for d in dimensions)

        # 提取总体建议
        overall_suggestions = self._extract_overall_suggestions(ai_response)

        # 提取路演者评价
        presenter_evaluation = self._extract_presenter_evaluation(ai_response)

        # 11. PPT 视觉评审
        with tc.track("qwen_vl_ppt_visual_review"):
            ppt_visual_review = await self._ppt_visual_review(presentation_ppt)

        # 12. 构建材料版本信息
        material_versions: dict = {
            "presentation_ppt": presentation_ppt["version"],
        }
        if presentation_video:
            material_versions["presentation_video"] = presentation_video["version"]
        if presentation_audio:
            material_versions["presentation_audio"] = presentation_audio["version"]

        # 13. 存储评审记录到 reviews 表
        now = datetime.now(timezone.utc).isoformat()
        try:
            with tc.track("supabase_insert_review"):
                review_row = (
                    self._sb.table("reviews")
                    .insert(
                        {
                            "project_id": project_id,
                            "user_id": user_id,
                            "review_type": "offline_presentation",
                            "competition": project.competition,
                            "track": project.track,
                            "group": project.group,
                            "stage": stage,
                            "judge_style": judge_style,
                            "total_score": float(total_score),
                            "material_versions": material_versions,
                            "stt_transcript": stt_transcript,
                            "ppt_visual_review": ppt_visual_review,
                            "presenter_evaluation": presenter_evaluation,
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

        # 14. 存储评审维度详情到 review_details 表
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

        # 15. 构建并返回 ReviewResult
        created_at_str = review_row.data[0].get("created_at", now)
        if isinstance(created_at_str, str):
            created_at = datetime.fromisoformat(
                created_at_str.replace("Z", "+00:00")
            )
        else:
            created_at = created_at_str

        logger.info("OfflineReviewService.review timing: %s", tc.summary())

        return ReviewResult(
            id=review_id,
            review_type="offline_presentation",
            total_score=total_score,
            dimensions=dimensions,
            overall_suggestions=overall_suggestions,
            status="completed",
            created_at=created_at,
            ppt_visual_review=ppt_visual_review,
            presenter_evaluation=presenter_evaluation,
        )


    # ── PPT 视觉评审 ─────────────────────────────────────────────

    async def _ppt_visual_review(self, presentation_ppt: dict) -> dict | None:
        """使用 Qwen-VL-Max 对路演PPT进行视觉评审。

        流程：下载 PPT → 上传 DashScope OSS → 组装 prompt → 调用 Qwen-VL-Max → 解析结果。
        任何步骤失败时降级返回 None，不影响主评审流程。

        Args:
            presentation_ppt: 路演PPT材料记录（含 file_path 等字段）

        Returns:
            PPTVisualReviewResult 的 dict 表示，或 None（失败时）
        """
        try:
            # 1. 下载 PPT 文件
            file_path = presentation_ppt.get("file_path")
            if not file_path:
                logger.warning("PPT视觉评审跳过：presentation_ppt 缺少 file_path")
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

    # ── 路演者评价提取 ────────────────────────────────────────────

    def _extract_presenter_evaluation(self, ai_response: dict) -> dict | None:
        """从AI响应中提取路演者表现评价。

        Args:
            ai_response: AI API 返回的完整 JSON 响应

        Returns:
            PresenterEvaluation 结构的 dict，提取失败返回 None
        """
        try:
            content = ai_response["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            return None

        parsed = self._extract_json(content)
        if parsed is None:
            return None

        presenter_eval = parsed.get("presenter_evaluation")
        if not isinstance(presenter_eval, dict):
            return None

        # 确保包含所有必需字段
        required_fields = [
            "language_expression",
            "rhythm_control",
            "logic_clarity",
            "engagement",
            "overall_comment",
            "suggestions",
        ]

        result: dict = {}
        for field in required_fields:
            value = presenter_eval.get(field)
            if field == "suggestions":
                result[field] = value if isinstance(value, list) else []
            else:
                result[field] = str(value) if value is not None else ""

        return result

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
        try:
            content = ai_response["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            logger.error("AI响应结构异常: %s", exc)
            raise HTTPException(
                status_code=502,
                detail="AI评审返回结果格式异常",
            ) from exc

        parsed = self._extract_json(content)
        if parsed is None:
            logger.error("无法从AI响应中提取JSON: %s", content[:500])
            raise HTTPException(
                status_code=502,
                detail="AI评审返回结果无法解析",
            )

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
