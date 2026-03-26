"""评审路由：文本评审、评审记录查询、评审详情、导出PDF。"""

import io
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from supabase import Client

from app.models.database import get_supabase
from app.models.schemas import (
    DimensionScore,
    ReviewRequest,
    ReviewResult,
    UserInfo,
)
from app.routes.auth import get_current_user
from app.services.offline_review_service import OfflineReviewService
from app.services.text_review_service import TextReviewService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/projects/{project_id}/reviews", tags=["reviews"]
)


def _get_text_review_service(
    supabase: Client = Depends(get_supabase),
) -> TextReviewService:
    return TextReviewService(supabase)


def _get_offline_review_service(
    supabase: Client = Depends(get_supabase),
) -> OfflineReviewService:
    return OfflineReviewService(supabase)


# ── POST /api/projects/{project_id}/reviews/text ─────────────


@router.post("/text", response_model=ReviewResult)
async def create_text_review(
    project_id: str,
    body: ReviewRequest,
    user: UserInfo = Depends(get_current_user),
    svc: TextReviewService = Depends(_get_text_review_service),
):
    """发起文本评审"""
    return await svc.review(
        project_id=project_id,
        user_id=user.id,
        stage=body.stage,
        judge_style=body.judge_style,
        material_types=body.material_types,
    )


# ── POST /api/projects/{project_id}/reviews/offline ──────────


@router.post("/offline", response_model=ReviewResult)
async def create_offline_review(
    project_id: str,
    body: ReviewRequest,
    user: UserInfo = Depends(get_current_user),
    svc: OfflineReviewService = Depends(_get_offline_review_service),
):
    """发起离线路演评审"""
    return await svc.review(
        project_id=project_id,
        user_id=user.id,
        stage=body.stage,
        judge_style=body.judge_style,
    )


# ── GET /api/projects/{project_id}/reviews ────────────────────


@router.get("")
async def list_reviews(
    project_id: str,
    user: UserInfo = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """获取评审记录列表"""
    try:
        result = (
            supabase.table("reviews")
            .select("id, review_type, total_score, stage, judge_style, status, created_at, selected_materials")
            .eq("project_id", project_id)
            .order("created_at", desc=True)
            .execute()
        )
        return result.data
    except Exception as exc:
        logger.exception("查询评审记录列表失败")
        raise HTTPException(status_code=500, detail=f"查询评审记录失败: {exc}") from exc


# ── GET /api/projects/{project_id}/reviews/{review_id} ────────


@router.get("/{review_id}", response_model=ReviewResult)
async def get_review_detail(
    project_id: str,
    review_id: str,
    user: UserInfo = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """获取评审详情（含维度评分和建议）"""
    # 查询评审主记录
    try:
        review_resp = (
            supabase.table("reviews")
            .select("*")
            .eq("id", review_id)
            .eq("project_id", project_id)
            .single()
            .execute()
        )
    except Exception as exc:
        logger.exception("查询评审记录失败")
        raise HTTPException(status_code=404, detail="评审记录不存在") from exc

    review = review_resp.data

    # 查询评审维度详情
    try:
        details_resp = (
            supabase.table("review_details")
            .select("*")
            .eq("review_id", review_id)
            .execute()
        )
    except Exception as exc:
        logger.exception("查询评审维度详情失败")
        raise HTTPException(
            status_code=500, detail=f"查询评审维度详情失败: {exc}"
        ) from exc

    dimensions = [
        DimensionScore(
            dimension=d["dimension"],
            max_score=float(d["max_score"]),
            score=float(d["score"]),
            sub_items=d.get("sub_items") or [],
            suggestions=d.get("suggestions") or [],
        )
        for d in details_resp.data
    ]

    # 解析 created_at
    created_at_str = review.get("created_at", "")
    if isinstance(created_at_str, str):
        created_at = datetime.fromisoformat(
            created_at_str.replace("Z", "+00:00")
        )
    else:
        created_at = created_at_str

    return ReviewResult(
        id=review["id"],
        review_type=review["review_type"],
        total_score=float(review.get("total_score", 0)),
        dimensions=dimensions,
        overall_suggestions=[],
        status=review.get("status", "completed"),
        created_at=created_at,
        selected_materials=review.get("selected_materials"),
        ppt_visual_review=review.get("ppt_visual_review"),
        presenter_evaluation=review.get("presenter_evaluation"),
    )


# ── GET /api/projects/{project_id}/reviews/{review_id}/export ─


@router.get("/{review_id}/export")
async def export_review_pdf(
    project_id: str,
    review_id: str,
    user: UserInfo = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """导出评审报告为PDF"""
    # 获取评审主记录
    try:
        review_resp = (
            supabase.table("reviews")
            .select("*")
            .eq("id", review_id)
            .eq("project_id", project_id)
            .single()
            .execute()
        )
    except Exception as exc:
        logger.exception("查询评审记录失败")
        raise HTTPException(status_code=404, detail="评审记录不存在") from exc

    review = review_resp.data

    # 获取评审维度详情
    try:
        details_resp = (
            supabase.table("review_details")
            .select("*")
            .eq("review_id", review_id)
            .execute()
        )
    except Exception as exc:
        logger.exception("查询评审维度详情失败")
        raise HTTPException(
            status_code=500, detail=f"查询评审维度详情失败: {exc}"
        ) from exc

    dimensions = details_resp.data

    # 尝试使用 reportlab 生成 PDF
    try:
        pdf_bytes = _generate_pdf_reportlab(review, dimensions)
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="review_{review_id}.pdf"'
            },
        )
    except ImportError:
        pass

    # reportlab 不可用，返回 JSON 提示
    return JSONResponse(
        status_code=200,
        content={
            "message": "PDF导出需要安装 reportlab 依赖。请运行: uv add reportlab",
            "review_id": review_id,
            "review_type": review.get("review_type"),
            "total_score": float(review.get("total_score", 0)),
            "dimensions": [
                {
                    "dimension": d["dimension"],
                    "score": float(d["score"]),
                    "max_score": float(d["max_score"]),
                }
                for d in dimensions
            ],
        },
    )


def _generate_pdf_reportlab(review: dict, dimensions: list[dict]) -> bytes:
    """使用 reportlab 生成评审报告 PDF。

    Raises:
        ImportError: 如果 reportlab 未安装
    """
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4)
    styles = getSampleStyleSheet()
    elements: list = []

    # 标题
    title_style = ParagraphStyle(
        "Title_CN",
        parent=styles["Title"],
        fontSize=18,
    )
    elements.append(Paragraph("AI评审报告", title_style))
    elements.append(Spacer(1, 6 * mm))

    # 基本信息
    info_style = styles["Normal"]
    elements.append(
        Paragraph(f"评审类型: {review.get('review_type', '-')}", info_style)
    )
    elements.append(
        Paragraph(f"总分: {review.get('total_score', '-')}", info_style)
    )
    elements.append(
        Paragraph(f"评委风格: {review.get('judge_style', '-')}", info_style)
    )
    elements.append(
        Paragraph(f"比赛阶段: {review.get('stage', '-')}", info_style)
    )
    elements.append(Spacer(1, 6 * mm))

    # 维度评分表格
    if dimensions:
        table_data = [["维度", "得分", "满分"]]
        for d in dimensions:
            table_data.append(
                [d["dimension"], str(d["score"]), str(d["max_score"])]
            )
        table = Table(table_data)
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                    ("ALIGN", (1, 0), (-1, -1), "CENTER"),
                ]
            )
        )
        elements.append(table)
        elements.append(Spacer(1, 6 * mm))

    # 各维度建议
    for d in dimensions:
        suggestions = d.get("suggestions") or []
        if suggestions:
            elements.append(
                Paragraph(f"{d['dimension']} - 改进建议:", styles["Heading3"])
            )
            for s in suggestions:
                elements.append(Paragraph(f"  - {s}", info_style))
            elements.append(Spacer(1, 3 * mm))

    doc.build(elements)
    return buf.getvalue()
