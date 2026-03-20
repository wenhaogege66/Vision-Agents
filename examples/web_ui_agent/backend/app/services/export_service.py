"""项目报告导出服务：生成包含项目信息、材料状态、评审结果的 PDF 报告。"""

import io
import logging
from datetime import datetime

from fastapi import HTTPException
from supabase import Client

from app.services.rule_service import COMPETITION_NAMES, TRACK_NAMES, GROUP_NAMES
from app.utils.timing import TimingContext

logger = logging.getLogger(__name__)

# 四种材料类型及其中文名称
MATERIAL_TYPE_LABELS: dict[str, str] = {
    "bp": "商业计划书 (BP)",
    "text_ppt": "文本评审PPT",
    "presentation_ppt": "路演PPT",
    "presentation_video": "路演视频",
}

# 评审类型中文标签
REVIEW_TYPE_LABELS: dict[str, str] = {
    "text_review": "文本评审",
    "offline_presentation": "离线路演",
    "live_presentation": "现场路演",
}


def _resolve_name(value: str, mapping: dict[str, str]) -> str:
    """将英文ID转换为中文名称，映射不存在时回退显示原始值。"""
    return mapping.get(value, value)


class ExportService:
    """生成项目评审报告 PDF"""

    def __init__(self, supabase: Client) -> None:
        self._sb = supabase

    async def generate_report(self, project_id: str, user_id: str) -> bytes:
        """生成项目评审报告 PDF。

        包含：项目基本信息、材料状态、评审结果摘要、评分汇总。
        无评审记录时标注"暂无评审记录"。

        Args:
            project_id: 项目 ID
            user_id: 当前用户 ID（用于权限校验）

        Returns:
            PDF 文件的字节内容
        """
        tc = TimingContext()

        # 1. 查询项目基本信息
        with tc.track("fetch_project"):
            project = await self._fetch_project(project_id, user_id)

        # 2. 查询材料状态
        with tc.track("fetch_materials"):
            materials = await self._fetch_material_status(project_id)

        # 3. 查询评审记录
        with tc.track("fetch_reviews"):
            reviews = await self._fetch_reviews(project_id)

        # 4. 生成 PDF
        with tc.track("build_pdf"):
            pdf_bytes = self._build_pdf(project, materials, reviews)

        logger.info("ExportService.generate_report timing: %s", tc.summary())
        return pdf_bytes

    # ── 数据查询方法 ──────────────────────────────────────────

    async def _fetch_project(self, project_id: str, user_id: str) -> dict:
        """查询项目基本信息，校验归属权。"""
        try:
            result = (
                self._sb.table("projects")
                .select("*")
                .eq("id", project_id)
                .limit(1)
                .execute()
            )
        except Exception as exc:
            logger.exception("查询项目失败")
            raise HTTPException(
                status_code=500, detail=f"查询项目失败: {exc}"
            ) from exc

        if not result or not result.data:
            raise HTTPException(status_code=404, detail="项目不存在")

        project = result.data[0]
        if project.get("user_id") != user_id:
            raise HTTPException(status_code=403, detail="无权访问该项目")
        return project

    async def _fetch_material_status(self, project_id: str) -> list[dict]:
        """查询项目最新材料记录。"""
        try:
            result = (
                self._sb.table("project_materials")
                .select("material_type, file_name, version, created_at")
                .eq("project_id", project_id)
                .eq("is_latest", True)
                .execute()
            )
        except Exception as exc:
            logger.exception("查询材料状态失败")
            raise HTTPException(
                status_code=500, detail=f"查询材料状态失败: {exc}"
            ) from exc
        return result.data

    async def _fetch_reviews(self, project_id: str) -> list[dict]:
        """查询项目所有评审记录。"""
        try:
            result = (
                self._sb.table("reviews")
                .select(
                    "id, review_type, total_score, stage, judge_style, status, created_at"
                )
                .eq("project_id", project_id)
                .order("created_at", desc=True)
                .execute()
            )
        except Exception as exc:
            logger.exception("查询评审记录失败")
            raise HTTPException(
                status_code=500, detail=f"查询评审记录失败: {exc}"
            ) from exc
        return result.data

    # ── PDF 生成 ──────────────────────────────────────────────

    def _build_pdf(
        self,
        project: dict,
        materials: list[dict],
        reviews: list[dict],
    ) -> bytes:
        """使用 reportlab 构建 PDF 报告。"""
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.cidfonts import UnicodeCIDFont
        from reportlab.platypus import (
            Paragraph,
            SimpleDocTemplate,
            Spacer,
            Table,
            TableStyle,
        )

        # 注册中文字体
        pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))

        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=A4)
        styles = getSampleStyleSheet()
        elements: list = []

        title_style = ParagraphStyle(
            "ReportTitle", parent=styles["Title"], fontSize=20,
            fontName="STSong-Light",
        )
        heading_style = ParagraphStyle(
            "SectionHeading", parent=styles["Heading2"], fontSize=14,
            fontName="STSong-Light",
        )
        normal_style = ParagraphStyle(
            "ChineseNormal", parent=styles["Normal"],
            fontName="STSong-Light",
        )

        # ── 标题 ──
        elements.append(Paragraph("项目评审报告", title_style))
        elements.append(Spacer(1, 8 * mm))

        # ── 项目基本信息 ──
        elements.append(Paragraph("项目基本信息", heading_style))
        elements.append(Spacer(1, 3 * mm))

        info_items = [
            ("项目名称", project.get("name", "-")),
            ("赛事", _resolve_name(project.get("competition", "-"), COMPETITION_NAMES)),
            ("赛道", _resolve_name(project.get("track", "-"), TRACK_NAMES)),
            ("组别", _resolve_name(project.get("group", "-"), GROUP_NAMES)),
            ("当前阶段", project.get("current_stage", "-")),
        ]
        for label, value in info_items:
            elements.append(Paragraph(f"{label}: {value}", normal_style))
        elements.append(Spacer(1, 6 * mm))

        # ── 材料状态 ──
        elements.append(Paragraph("材料状态", heading_style))
        elements.append(Spacer(1, 3 * mm))

        uploaded_types = {m["material_type"] for m in materials}
        mat_table_data = [["材料类型", "状态", "文件名", "版本"]]
        for mt, label in MATERIAL_TYPE_LABELS.items():
            if mt in uploaded_types:
                row_data = next(
                    m for m in materials if m["material_type"] == mt
                )
                mat_table_data.append(
                    [
                        label,
                        "已上传",
                        row_data.get("file_name", "-"),
                        f"v{row_data.get('version', '-')}",
                    ]
                )
            else:
                mat_table_data.append([label, "未上传", "-", "-"])

        mat_table = Table(mat_table_data, colWidths=[120, 60, 200, 50])
        mat_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4472C4")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("ALIGN", (1, 0), (1, -1), "CENTER"),
                    ("ALIGN", (3, 0), (3, -1), "CENTER"),
                    ("FONTNAME", (0, 0), (-1, -1), "STSong-Light"),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F2F2F2")]),
                ]
            )
        )
        elements.append(mat_table)
        elements.append(Spacer(1, 6 * mm))

        # ── 评审结果 ──
        elements.append(Paragraph("评审结果", heading_style))
        elements.append(Spacer(1, 3 * mm))

        if not reviews:
            elements.append(Paragraph("暂无评审记录", normal_style))
        else:
            # 评审记录表格
            review_table_data = [["评审类型", "评分", "评委风格", "阶段", "日期"]]
            for r in reviews:
                created_at = r.get("created_at", "")
                if isinstance(created_at, str) and created_at:
                    try:
                        dt = datetime.fromisoformat(
                            created_at.replace("Z", "+00:00")
                        )
                        date_str = dt.strftime("%Y-%m-%d")
                    except (ValueError, TypeError):
                        date_str = created_at[:10] if len(created_at) >= 10 else created_at
                else:
                    date_str = "-"

                review_table_data.append(
                    [
                        _resolve_name(r.get("review_type", "-"), REVIEW_TYPE_LABELS),
                        str(r.get("total_score", "-")),
                        r.get("judge_style", "-"),
                        r.get("stage", "-"),
                        date_str,
                    ]
                )

            review_table = Table(
                review_table_data, colWidths=[80, 60, 80, 100, 80]
            )
            review_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4472C4")),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                        ("ALIGN", (1, 0), (1, -1), "CENTER"),
                        ("FONTNAME", (0, 0), (-1, -1), "STSong-Light"),
                        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F2F2F2")]),
                    ]
                )
            )
            elements.append(review_table)
            elements.append(Spacer(1, 6 * mm))

            # ── 评分汇总 ──
            scores = [
                float(r["total_score"])
                for r in reviews
                if r.get("total_score") is not None
            ]
            if scores:
                elements.append(Paragraph("评分汇总", heading_style))
                elements.append(Spacer(1, 3 * mm))
                avg_score = sum(scores) / len(scores)
                elements.append(
                    Paragraph(f"评审次数: {len(scores)}", normal_style)
                )
                elements.append(
                    Paragraph(f"平均分: {avg_score:.1f}", normal_style)
                )
                elements.append(
                    Paragraph(
                        f"最高分: {max(scores):.1f}", normal_style
                    )
                )
                elements.append(
                    Paragraph(
                        f"最低分: {min(scores):.1f}", normal_style
                    )
                )

        doc.build(elements)
        return buf.getvalue()
