"""离线路演评审服务单元测试与属性测试。

测试 OfflineReviewService 的完整评审流程、错误处理，
以及使用 hypothesis 验证离线评审报告的完整性属性。
"""

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.models.schemas import (
    DimensionScore,
    EvaluationDimension,
    EvaluationRules,
    ProjectResponse,
    ReviewResult,
)
from app.services.offline_review_service import OfflineReviewService


# ── Helpers ───────────────────────────────────────────────────


def _mock_supabase() -> MagicMock:
    """Create a mock Supabase client."""
    return MagicMock()


def _make_material(
    material_type: str = "presentation_ppt",
    version: int = 1,
    file_name: str = "slides.pptx",
) -> dict:
    return {
        "id": f"mat-{material_type}-{version}",
        "project_id": "proj-1",
        "material_type": material_type,
        "file_path": f"proj-1/{material_type}/v{version}_{file_name}",
        "file_name": file_name,
        "file_size": 1024,
        "version": version,
        "is_latest": True,
        "image_paths": (
            ["proj-1/presentation_ppt/images/page_001.png"]
            if "ppt" in material_type
            else None
        ),
        "created_at": "2025-01-01T00:00:00+00:00",
    }


def _make_project() -> ProjectResponse:
    return ProjectResponse(
        id="proj-1",
        name="测试项目",
        competition="guochuangsai",
        track="gaojiao",
        group="benke_chuangyi",
        current_stage="school_presentation",
        materials_status={
            "bp": False,
            "text_ppt": False,
            "presentation_ppt": True,
            "presentation_video": True,
        },
        created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )


def _make_rules() -> EvaluationRules:
    return EvaluationRules(
        competition="guochuangsai",
        track="gaojiao",
        group="benke_chuangyi",
        dimensions=[
            EvaluationDimension(
                name="个人成长", max_score=30, sub_items=["立德树人", "调研深入"]
            ),
            EvaluationDimension(
                name="项目创新", max_score=30, sub_items=["技术创新", "模式创新"]
            ),
            EvaluationDimension(
                name="产业价值", max_score=25, sub_items=["市场前景", "商业模式"]
            ),
            EvaluationDimension(
                name="团队协作", max_score=15, sub_items=["分工合理", "执行力"]
            ),
        ],
        raw_content="# 评审规则\n## 个人成长（30分）\n## 项目创新（30分）",
    )


def _make_ai_response(dimensions: list[dict] | None = None) -> dict:
    """Create a mock AI API response for offline review."""
    if dimensions is None:
        dimensions = [
            {
                "dimension": "个人成长",
                "max_score": 30,
                "score": 25,
                "sub_items": [{"name": "立德树人", "comment": "表现良好"}],
                "suggestions": ["建议加强社会实践"],
            },
            {
                "dimension": "项目创新",
                "max_score": 30,
                "score": 22,
                "sub_items": [{"name": "技术创新", "comment": "有一定创新"}],
                "suggestions": ["建议深化技术方案"],
            },
            {
                "dimension": "产业价值",
                "max_score": 25,
                "score": 18,
                "sub_items": [{"name": "市场前景", "comment": "市场分析不够深入"}],
                "suggestions": ["建议补充市场调研数据"],
            },
            {
                "dimension": "团队协作",
                "max_score": 15,
                "score": 12,
                "sub_items": [{"name": "分工合理", "comment": "分工明确"}],
                "suggestions": ["建议展示更多团队协作成果"],
            },
        ]
    content = json.dumps(
        {"dimensions": dimensions, "overall_suggestions": ["总体建议1", "总体建议2"]},
        ensure_ascii=False,
    )
    return {
        "choices": [{"message": {"content": content}}],
    }


def _setup_review_mocks(
    sb: MagicMock,
    presentation_ppt: dict | None = "DEFAULT",
    presentation_video: dict | None = "DEFAULT",
    project: ProjectResponse | None = None,
    rules: EvaluationRules | None = None,
    ai_response: dict | None = None,
    ai_error: Exception | None = None,
):
    """Set up all mocks needed for a full offline review() call."""
    if presentation_ppt == "DEFAULT":
        presentation_ppt = _make_material("presentation_ppt", version=1)
    if presentation_video == "DEFAULT":
        presentation_video = _make_material(
            "presentation_video", version=1, file_name="demo.mp4"
        )
    if project is None:
        project = _make_project()
    if rules is None:
        rules = _make_rules()
    if ai_response is None:
        ai_response = _make_ai_response()

    # Mock MaterialService.get_latest
    async def mock_get_latest(project_id, material_type):
        if material_type == "presentation_ppt":
            return presentation_ppt
        if material_type == "presentation_video":
            return presentation_video
        return None

    # Mock ProjectService.get_project
    async def mock_get_project(project_id, user_id):
        return project

    # Mock storage.get_public_url
    bucket_mock = MagicMock()
    bucket_mock.get_public_url.return_value = "https://example.com/file"
    sb.storage.from_.return_value = bucket_mock

    # Mock DB insert for reviews / review_details tables
    review_row = {
        "id": "review-1",
        "project_id": "proj-1",
        "review_type": "offline_presentation",
        "total_score": 77.0,
        "created_at": "2025-01-01T00:00:00+00:00",
    }
    detail_row = {"id": "detail-1"}

    def table_side_effect(name):
        chain = MagicMock()
        for m in (
            "insert", "select", "update", "delete",
            "eq", "order", "limit", "maybe_single", "single",
        ):
            getattr(chain, m).return_value = chain
        if name == "reviews":
            chain.execute.return_value = MagicMock(data=[review_row])
        else:
            chain.execute.return_value = MagicMock(data=[detail_row])
        return chain

    sb.table.side_effect = table_side_effect

    patches = []

    p_rule = patch("app.services.offline_review_service.rule_service")
    p_knowledge = patch("app.services.offline_review_service.knowledge_service")
    p_prompt = patch("app.services.offline_review_service.prompt_service")
    p_ai = patch("app.services.offline_review_service.call_ai_api")

    mock_rule = p_rule.start()
    mock_knowledge = p_knowledge.start()
    mock_prompt = p_prompt.start()
    mock_ai = p_ai.start()

    mock_rule.load_rules.return_value = rules
    mock_knowledge.load_knowledge.return_value = "知识库内容"
    mock_prompt.assemble_prompt.return_value = "组装后的prompt"

    if ai_error:
        mock_ai.side_effect = ai_error
    else:
        mock_ai.return_value = ai_response

    patches.extend([p_rule, p_knowledge, p_prompt, p_ai])

    # Create service and manually set internal attributes
    svc = OfflineReviewService.__new__(OfflineReviewService)
    svc._sb = sb
    svc._material_svc = MagicMock()
    svc._material_svc.get_latest = AsyncMock(side_effect=mock_get_latest)
    svc._project_svc = MagicMock()
    svc._project_svc.get_project = AsyncMock(side_effect=mock_get_project)

    return svc, patches


def _cleanup_patches(patches: list):
    for p in patches:
        p.stop()



# ── Unit Tests ────────────────────────────────────────────────


class TestOfflineReviewSuccess:
    """Test successful offline review with both PPT and video."""

    @pytest.mark.asyncio
    async def test_review_with_ppt_and_video(self):
        sb = _mock_supabase()
        svc, patches = _setup_review_mocks(sb)
        try:
            result = await svc.review(
                "proj-1", "user-1", "school_presentation", "strict"
            )
            assert isinstance(result, ReviewResult)
            assert result.review_type == "offline_presentation"
            assert result.status == "completed"
            assert result.id == "review-1"
            assert len(result.dimensions) > 0
            assert result.total_score > 0
        finally:
            _cleanup_patches(patches)


class TestOfflineReviewErrors:
    """Test error handling in offline review."""

    @pytest.mark.asyncio
    async def test_missing_ppt_raises_400(self):
        sb = _mock_supabase()
        svc, patches = _setup_review_mocks(sb, presentation_ppt=None)
        try:
            with pytest.raises(HTTPException) as exc_info:
                await svc.review(
                    "proj-1", "user-1", "school_presentation", "strict"
                )
            assert exc_info.value.status_code == 400
            assert "路演PPT" in str(exc_info.value.detail)
        finally:
            _cleanup_patches(patches)

    @pytest.mark.asyncio
    async def test_missing_video_raises_400(self):
        sb = _mock_supabase()
        svc, patches = _setup_review_mocks(sb, presentation_video=None)
        try:
            with pytest.raises(HTTPException) as exc_info:
                await svc.review(
                    "proj-1", "user-1", "school_presentation", "strict"
                )
            assert exc_info.value.status_code == 400
            assert "路演视频" in str(exc_info.value.detail)
        finally:
            _cleanup_patches(patches)

    @pytest.mark.asyncio
    async def test_ai_api_failure_raises_503(self):
        sb = _mock_supabase()
        svc, patches = _setup_review_mocks(
            sb, ai_error=RuntimeError("AI API 调用失败")
        )
        try:
            with pytest.raises(HTTPException) as exc_info:
                await svc.review(
                    "proj-1", "user-1", "school_presentation", "strict"
                )
            assert exc_info.value.status_code == 503
            assert "AI评审服务" in str(exc_info.value.detail)
        finally:
            _cleanup_patches(patches)



# ── Property-Based Tests ──────────────────────────────────────

from hypothesis import given, settings as h_settings, HealthCheck
import hypothesis.strategies as st


# ── Hypothesis Strategies ─────────────────────────────────────

# Required report sections for offline review
REQUIRED_REPORT_SECTIONS = ["演讲表现评价", "PPT内容评价", "综合评分", "改进建议"]

# Dimension name pool mapping to report sections
OFFLINE_DIMENSION_NAMES = [
    "演讲表现评价",
    "PPT内容评价",
    "综合评分",
    "改进建议",
]


def _non_empty_chinese_text() -> st.SearchStrategy[str]:
    """Generate non-empty text suitable for Chinese content."""
    return st.text(
        min_size=1,
        max_size=50,
        alphabet=st.characters(whitelist_categories=("L", "N", "P")),
    ).filter(lambda s: s.strip())


def _offline_ai_response_strategy() -> st.SearchStrategy[dict]:
    """Generate a mock AI response that always contains the four required
    report sections as dimensions, with non-empty sub_items and suggestions.
    """
    return st.fixed_dictionaries({
        "演讲表现评价_score": st.floats(
            min_value=1.0, max_value=30.0,
            allow_nan=False, allow_infinity=False,
        ).map(lambda x: round(x, 1)),
        "PPT内容评价_score": st.floats(
            min_value=1.0, max_value=30.0,
            allow_nan=False, allow_infinity=False,
        ).map(lambda x: round(x, 1)),
        "综合评分_score": st.floats(
            min_value=1.0, max_value=25.0,
            allow_nan=False, allow_infinity=False,
        ).map(lambda x: round(x, 1)),
        "改进建议_score": st.floats(
            min_value=1.0, max_value=15.0,
            allow_nan=False, allow_infinity=False,
        ).map(lambda x: round(x, 1)),
        "sub_item_text": _non_empty_chinese_text(),
        "suggestion_text": _non_empty_chinese_text(),
        "overall_suggestion": _non_empty_chinese_text(),
    }).map(lambda d: _build_offline_ai_response(d))


def _build_offline_ai_response(params: dict) -> dict:
    """Build a complete AI response dict from strategy parameters."""
    dimensions = []
    section_scores = {
        "演讲表现评价": (30.0, params["演讲表现评价_score"]),
        "PPT内容评价": (30.0, params["PPT内容评价_score"]),
        "综合评分": (25.0, params["综合评分_score"]),
        "改进建议": (15.0, params["改进建议_score"]),
    }
    for name, (max_score, score) in section_scores.items():
        dimensions.append({
            "dimension": name,
            "max_score": max_score,
            "score": score,
            "sub_items": [{"name": f"{name}子项", "comment": params["sub_item_text"]}],
            "suggestions": [params["suggestion_text"]],
        })

    content = json.dumps(
        {
            "dimensions": dimensions,
            "overall_suggestions": [params["overall_suggestion"]],
        },
        ensure_ascii=False,
    )
    return {"choices": [{"message": {"content": content}}]}


def _offline_rules_strategy() -> st.SearchStrategy[EvaluationRules]:
    """Generate evaluation rules matching the four offline review sections."""
    return st.just(
        EvaluationRules(
            competition="guochuangsai",
            track="gaojiao",
            group="benke_chuangyi",
            dimensions=[
                EvaluationDimension(name="演讲表现评价", max_score=30, sub_items=["表达能力", "时间控制"]),
                EvaluationDimension(name="PPT内容评价", max_score=30, sub_items=["内容完整", "视觉设计"]),
                EvaluationDimension(name="综合评分", max_score=25, sub_items=["整体表现"]),
                EvaluationDimension(name="改进建议", max_score=15, sub_items=["改进方向"]),
            ],
            raw_content="# 离线评审规则",
        )
    )


class TestProperty13OfflineReviewReportCompleteness:
    """Property 13: 离线评审报告完整性

    For any completed offline review result, the report should contain
    four required parts: 演讲表现评价 (presentation performance),
    PPT内容评价 (PPT content evaluation), 综合评分 (comprehensive score),
    and 改进建议 (improvement suggestions), and each part should be non-empty.

    Feature: competition-judge-system, Property 13: 离线评审报告完整性
    Validates: Requirements 8.3, 8.4
    """

    @given(
        ai_response=_offline_ai_response_strategy(),
        ppt_version=st.integers(min_value=1, max_value=20),
        video_version=st.integers(min_value=1, max_value=20),
        judge_style=st.sampled_from(["strict", "gentle", "academic"]),
        rules=_offline_rules_strategy(),
    )
    @h_settings(
        max_examples=100,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    @pytest.mark.asyncio
    async def test_offline_review_report_contains_all_required_sections(
        self,
        ai_response: dict,
        ppt_version: int,
        video_version: int,
        judge_style: str,
        rules: EvaluationRules,
    ):
        """Generate random offline review AI responses and verify the parsed
        result always contains the four required report sections, each with
        non-empty content.
        """
        sb = _mock_supabase()
        ppt = _make_material("presentation_ppt", version=ppt_version)
        video = _make_material(
            "presentation_video", version=video_version, file_name="demo.mp4"
        )

        svc, patches = _setup_review_mocks(
            sb,
            presentation_ppt=ppt,
            presentation_video=video,
            rules=rules,
            ai_response=ai_response,
        )
        try:
            result = await svc.review(
                "proj-1", "user-1", "school_presentation", judge_style
            )

            # The result must be a completed ReviewResult
            assert isinstance(result, ReviewResult)
            assert result.status == "completed"

            # Collect dimension names from the result
            result_dimension_names = [d.dimension for d in result.dimensions]

            # Property: all four required sections must be present
            for section in REQUIRED_REPORT_SECTIONS:
                assert section in result_dimension_names, (
                    f"Required section '{section}' missing from offline review report. "
                    f"Got dimensions: {result_dimension_names}"
                )

            # Property: each section must have non-empty content
            for dim in result.dimensions:
                if dim.dimension in REQUIRED_REPORT_SECTIONS:
                    # sub_items must be non-empty
                    assert len(dim.sub_items) > 0, (
                        f"Section '{dim.dimension}' has empty sub_items"
                    )
                    # suggestions must be non-empty
                    assert len(dim.suggestions) > 0, (
                        f"Section '{dim.dimension}' has empty suggestions"
                    )
                    # score should be positive (non-empty score)
                    assert dim.score > 0, (
                        f"Section '{dim.dimension}' has zero or negative score"
                    )

            # Property: overall_suggestions should be non-empty
            assert len(result.overall_suggestions) > 0, (
                "Offline review report should have non-empty overall_suggestions"
            )
        finally:
            _cleanup_patches(patches)
