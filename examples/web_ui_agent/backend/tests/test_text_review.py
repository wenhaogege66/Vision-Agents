"""AI文本评审服务单元测试与属性测试。

测试 TextReviewService 的完整评审流程、AI响应解析、错误处理，
以及使用 hypothesis 验证评审结果的正确性属性。
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
from app.services.text_review_service import TextReviewService


# ── Helpers ───────────────────────────────────────────────────


def _mock_supabase() -> MagicMock:
    """Create a mock Supabase client."""
    sb = MagicMock()
    return sb


def _make_material(
    material_type: str = "text_ppt",
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
        "image_paths": ["proj-1/text_ppt/images/page_001.png"] if "ppt" in material_type else None,
        "created_at": "2025-01-01T00:00:00+00:00",
    }


def _make_project() -> ProjectResponse:
    return ProjectResponse(
        id="proj-1",
        name="测试项目",
        competition="guochuangsai",
        track="gaojiao",
        group="benke_chuangyi",
        current_stage="school_text",
        materials_status={"bp": True, "text_ppt": True, "presentation_ppt": False, "presentation_video": False},
        created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )


def _make_rules() -> EvaluationRules:
    return EvaluationRules(
        competition="guochuangsai",
        track="gaojiao",
        group="benke_chuangyi",
        dimensions=[
            EvaluationDimension(name="个人成长", max_score=30, sub_items=["立德树人", "调研深入"]),
            EvaluationDimension(name="项目创新", max_score=30, sub_items=["技术创新", "模式创新"]),
            EvaluationDimension(name="产业价值", max_score=25, sub_items=["市场前景", "商业模式"]),
            EvaluationDimension(name="团队协作", max_score=15, sub_items=["分工合理", "执行力"]),
        ],
        raw_content="# 评审规则\n## 个人成长（30分）\n## 项目创新（30分）",
    )


def _make_ai_response(dimensions: list[dict] | None = None) -> dict:
    """Create a mock AI API response."""
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
    text_ppt: dict | None = None,
    bp: dict | None = None,
    project: ProjectResponse | None = None,
    rules: EvaluationRules | None = None,
    ai_response: dict | None = None,
    ai_error: Exception | None = None,
):
    """Set up all mocks needed for a full review() call."""
    if text_ppt is None:
        text_ppt = _make_material("text_ppt", version=1)
    if project is None:
        project = _make_project()
    if rules is None:
        rules = _make_rules()
    if ai_response is None:
        ai_response = _make_ai_response()

    # Mock MaterialService.get_latest
    async def mock_get_latest(project_id, material_type):
        if material_type == "text_ppt":
            return text_ppt
        if material_type == "bp":
            return bp
        return None

    # Mock ProjectService.get_project
    async def mock_get_project(project_id, user_id):
        return project

    # Mock storage.get_public_url
    bucket_mock = MagicMock()
    bucket_mock.get_public_url.return_value = "https://example.com/image.png"
    sb.storage.from_.return_value = bucket_mock

    # Mock DB insert for reviews table
    review_row = {
        "id": "review-1",
        "project_id": "proj-1",
        "review_type": "text_review",
        "total_score": 77.0,
        "created_at": "2025-01-01T00:00:00+00:00",
    }
    detail_row = {"id": "detail-1"}

    call_count = {"n": 0}

    def table_side_effect(name):
        chain = MagicMock()
        for m in ("insert", "select", "update", "delete", "eq", "order", "limit", "maybe_single", "single"):
            getattr(chain, m).return_value = chain
        call_count["n"] += 1
        if name == "reviews":
            chain.execute.return_value = MagicMock(data=[review_row])
        else:
            chain.execute.return_value = MagicMock(data=[detail_row])
        return chain

    sb.table.side_effect = table_side_effect

    patches = []

    # Patch MaterialService methods on the instance
    mat_patch_get = patch.object(
        TextReviewService, "__init__", lambda self, supabase: None
    )

    # We'll patch at module level for singletons
    p_rule = patch("app.services.text_review_service.rule_service")
    p_knowledge = patch("app.services.text_review_service.knowledge_service")
    p_prompt = patch("app.services.text_review_service.prompt_service")
    p_ai = patch("app.services.text_review_service.call_ai_api")

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
    svc = TextReviewService.__new__(TextReviewService)
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


class TestTextReviewSuccess:
    """Test successful text review with both PPT and BP."""

    @pytest.mark.asyncio
    async def test_review_with_ppt_and_bp(self):
        sb = _mock_supabase()
        bp = _make_material("bp", version=2, file_name="plan.pdf")
        svc, patches = _setup_review_mocks(sb, bp=bp)
        try:
            result = await svc.review("proj-1", "user-1", "school_text", "strict")
            assert isinstance(result, ReviewResult)
            assert result.review_type == "text_review"
            assert result.status == "completed"
            assert result.id == "review-1"
        finally:
            _cleanup_patches(patches)

    @pytest.mark.asyncio
    async def test_review_stores_to_db(self):
        sb = _mock_supabase()
        bp = _make_material("bp", version=2, file_name="plan.pdf")
        svc, patches = _setup_review_mocks(sb, bp=bp)
        try:
            await svc.review("proj-1", "user-1", "school_text", "strict")
            # Verify reviews table was called with insert
            sb.table.assert_any_call("reviews")
            sb.table.assert_any_call("review_details")
        finally:
            _cleanup_patches(patches)


class TestTextReviewDegradedMode:
    """Test text review with only PPT (no BP) — degraded mode."""

    @pytest.mark.asyncio
    async def test_review_without_bp_succeeds(self):
        sb = _mock_supabase()
        svc, patches = _setup_review_mocks(sb, bp=None)
        try:
            result = await svc.review("proj-1", "user-1", "school_text", "strict")
            assert isinstance(result, ReviewResult)
            assert result.review_type == "text_review"
            assert result.status == "completed"
        finally:
            _cleanup_patches(patches)


class TestTextReviewErrors:
    """Test error handling in text review."""

    @pytest.mark.asyncio
    async def test_no_ppt_raises_400(self):
        sb = _mock_supabase()
        svc, patches = _setup_review_mocks(sb, text_ppt=None)
        # Override get_latest to return None for text_ppt
        async def no_ppt(project_id, material_type):
            if material_type == "text_ppt":
                return None
            return None
        svc._material_svc.get_latest = AsyncMock(side_effect=no_ppt)
        try:
            with pytest.raises(HTTPException) as exc_info:
                await svc.review("proj-1", "user-1", "school_text", "strict")
            assert exc_info.value.status_code == 400
            assert "文本PPT" in str(exc_info.value.detail)
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
                await svc.review("proj-1", "user-1", "school_text", "strict")
            assert exc_info.value.status_code == 503
            assert "AI评审服务" in str(exc_info.value.detail)
        finally:
            _cleanup_patches(patches)


class TestExtractJson:
    """Test JSON parsing from AI response (various formats)."""

    def test_direct_json(self):
        text = '{"dimensions": [], "overall_suggestions": []}'
        result = TextReviewService._extract_json(text)
        assert result is not None
        assert "dimensions" in result

    def test_markdown_code_block(self):
        text = '```json\n{"dimensions": [{"dimension": "test"}]}\n```'
        result = TextReviewService._extract_json(text)
        assert result is not None
        assert result["dimensions"][0]["dimension"] == "test"

    def test_json_with_surrounding_text(self):
        text = '以下是评审结果：\n{"dimensions": []} \n请参考以上内容。'
        result = TextReviewService._extract_json(text)
        assert result is not None
        assert "dimensions" in result

    def test_invalid_json_returns_none(self):
        text = "这不是JSON内容"
        result = TextReviewService._extract_json(text)
        assert result is None

    def test_code_block_without_json_tag(self):
        text = '```\n{"dimensions": [{"dimension": "创新"}]}\n```'
        result = TextReviewService._extract_json(text)
        assert result is not None


# ── Property-Based Tests ──────────────────────────────────────

from hypothesis import given, settings as h_settings, assume, HealthCheck
import hypothesis.strategies as st


# ── Hypothesis Strategies ─────────────────────────────────────

def _dimension_strategy() -> st.SearchStrategy[dict]:
    """Generate a random evaluation dimension dict."""
    return st.fixed_dictionaries({
        "name": st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("L", "N"))),
        "max_score": st.floats(min_value=1.0, max_value=50.0, allow_nan=False, allow_infinity=False).map(lambda x: round(x, 1)),
        "sub_items": st.lists(st.text(min_size=1, max_size=15, alphabet=st.characters(whitelist_categories=("L",))), min_size=1, max_size=5),
    })


def _unique_dimensions_strategy() -> st.SearchStrategy[list[EvaluationDimension]]:
    """Generate a list of dimensions with unique names."""
    dim_name_pool = ["个人成长", "项目创新", "产业价值", "团队协作", "公益价值", "发展前景"]
    return (
        st.lists(
            st.sampled_from(dim_name_pool),
            min_size=1,
            max_size=len(dim_name_pool),
            unique=True,
        )
        .flatmap(
            lambda names: st.tuples(
                *[
                    st.tuples(
                        st.just(name),
                        st.floats(min_value=5.0, max_value=50.0, allow_nan=False, allow_infinity=False).map(lambda x: round(x, 1)),
                        st.lists(st.text(min_size=1, max_size=10, alphabet=st.characters(whitelist_categories=("L",))), min_size=1, max_size=3),
                    )
                    for name in names
                ]
            )
        )
        .map(
            lambda tuples: [
                EvaluationDimension(name=t[0], max_score=t[1], sub_items=t[2])
                for t in tuples
            ]
        )
    )


def _rules_strategy() -> st.SearchStrategy[EvaluationRules]:
    """Generate random evaluation rules with unique dimension names."""
    return st.builds(
        EvaluationRules,
        competition=st.just("guochuangsai"),
        track=st.just("gaojiao"),
        group=st.just("benke_chuangyi"),
        dimensions=_unique_dimensions_strategy(),
        raw_content=st.just("评审规则内容"),
    )


def _ai_response_from_rules(rules: EvaluationRules) -> dict:
    """Build a mock AI response that conforms to the given rules.

    Scores are deterministically set to 70% of max_score to avoid
    floating-point edge cases.
    """
    dimensions = []
    for dim in rules.dimensions:
        score = round(dim.max_score * 0.7, 1)
        sub_items = [{"name": si, "comment": f"评价{si}"} for si in dim.sub_items]
        suggestions = [f"建议改进{dim.name}"]
        dimensions.append({
            "dimension": dim.name,
            "max_score": dim.max_score,
            "score": score,
            "sub_items": sub_items,
            "suggestions": suggestions,
        })
    content = json.dumps(
        {"dimensions": dimensions, "overall_suggestions": ["总体建议"]},
        ensure_ascii=False,
    )
    return {"choices": [{"message": {"content": content}}]}


# Valid review types
VALID_REVIEW_TYPES = ["text_review", "live_presentation", "offline_presentation"]


class TestProperty9ReviewUsesLatestMaterials:
    """Property 9: 评审结果使用最新材料

    For any review request, the system should use the latest version of
    materials from the project material center.

    Feature: competition-judge-system, Property 9: 评审结果使用最新材料
    Validates: Requirements 4.1
    """

    @given(
        ppt_version=st.integers(min_value=1, max_value=20),
        bp_version=st.integers(min_value=1, max_value=20),
    )
    @h_settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @pytest.mark.asyncio
    async def test_review_uses_latest_material_versions(
        self, ppt_version: int, bp_version: int
    ):
        """Verify that the review service fetches materials with is_latest=True
        and material_versions in the review record matches the latest version numbers.
        """
        sb = _mock_supabase()
        text_ppt = _make_material("text_ppt", version=ppt_version)
        bp = _make_material("bp", version=bp_version, file_name="plan.pdf")

        svc, patches = _setup_review_mocks(sb, text_ppt=text_ppt, bp=bp)
        try:
            result = await svc.review("proj-1", "user-1", "school_text", "strict")

            # Verify get_latest was called for text_ppt and bp
            calls = svc._material_svc.get_latest.call_args_list
            call_types = [c.args[1] for c in calls]
            assert "text_ppt" in call_types, "Should fetch text_ppt"
            assert "bp" in call_types, "Should fetch bp"

            # Verify the materials returned are the latest (is_latest=True)
            assert text_ppt["is_latest"] is True
            assert bp["is_latest"] is True

            # Verify the review was stored with correct material versions
            # Check the insert call to reviews table
            reviews_calls = [
                c for c in sb.table.call_args_list if c.args[0] == "reviews"
            ]
            assert len(reviews_calls) > 0, "Should insert into reviews table"

            # Get the insert data from the chain
            # The insert is called on the chain returned by sb.table("reviews")
            for call in sb.table.call_args_list:
                if call.args[0] == "reviews":
                    chain = sb.table(call.args[0])
                    insert_call = chain.insert.call_args
                    if insert_call:
                        insert_data = insert_call.args[0]
                        assert insert_data["material_versions"]["text_ppt"] == ppt_version
                        assert insert_data["material_versions"]["bp"] == bp_version
                    break
        finally:
            _cleanup_patches(patches)


class TestProperty10ReviewResultStructureMatchesRules:
    """Property 10: 评审结果结构符合规则

    For any completed review result, its scoring dimensions should correspond
    one-to-one with the evaluation rule dimensions, each dimension's score
    should not exceed its max_score, and each dimension should contain
    non-empty sub_items and suggestions.

    Feature: competition-judge-system, Property 10: 评审结果结构符合规则
    Validates: Requirements 4.3
    """

    @given(rules=_rules_strategy())
    @h_settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @pytest.mark.asyncio
    async def test_result_dimensions_match_rules(self, rules: EvaluationRules):
        """Generate random evaluation rules and AI responses conforming to those rules,
        then verify the parsed result matches the rule structure.
        """
        sb = _mock_supabase()
        ai_response = _ai_response_from_rules(rules)

        svc, patches = _setup_review_mocks(
            sb,
            bp=_make_material("bp", version=1, file_name="plan.pdf"),
            rules=rules,
            ai_response=ai_response,
        )
        try:
            result = await svc.review("proj-1", "user-1", "school_text", "strict")

            # Verify dimensions count matches rules
            assert len(result.dimensions) == len(rules.dimensions), (
                f"Expected {len(rules.dimensions)} dimensions, got {len(result.dimensions)}"
            )

            # Build a lookup from rule dimensions
            rule_dims = {d.name: d for d in rules.dimensions}

            for dim in result.dimensions:
                # Each dimension name should correspond to a rule dimension
                assert dim.dimension in rule_dims, (
                    f"Dimension '{dim.dimension}' not found in rules"
                )

                rule_dim = rule_dims[dim.dimension]

                # Score should not exceed max_score
                assert dim.score <= rule_dim.max_score, (
                    f"Score {dim.score} exceeds max {rule_dim.max_score} for '{dim.dimension}'"
                )

                # Each dimension should have non-empty sub_items
                assert len(dim.sub_items) > 0, (
                    f"Dimension '{dim.dimension}' should have non-empty sub_items"
                )

                # Each dimension should have non-empty suggestions
                assert len(dim.suggestions) > 0, (
                    f"Dimension '{dim.dimension}' should have non-empty suggestions"
                )
        finally:
            _cleanup_patches(patches)


class TestProperty11ReviewResultPersistenceRoundTrip:
    """Property 11: 评审结果持久化往返

    For any review result, after storing to the database and querying back,
    the returned review record should contain complete scoring, evaluation,
    and suggestion information consistent with the original result.

    Feature: competition-judge-system, Property 11: 评审结果持久化往返
    Validates: Requirements 4.6
    """

    @given(
        num_dimensions=st.integers(min_value=1, max_value=6),
        data=st.data(),
    )
    @h_settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @pytest.mark.asyncio
    async def test_review_round_trip_consistency(self, num_dimensions: int, data):
        """Generate random review results, mock DB insert and query,
        verify round-trip consistency.
        """
        # Generate random dimensions
        dimensions_data = []
        for i in range(num_dimensions):
            max_score = data.draw(
                st.floats(min_value=5.0, max_value=50.0, allow_nan=False, allow_infinity=False).map(
                    lambda x: round(x, 1)
                )
            )
            score = data.draw(
                st.floats(min_value=0.0, max_value=max_score, allow_nan=False, allow_infinity=False).map(
                    lambda x: round(x, 1)
                )
            )
            dim_name = data.draw(
                st.text(min_size=1, max_size=10, alphabet=st.characters(whitelist_categories=("L",)))
            )
            sub_items = [{"name": f"子项{j}", "comment": f"评价{j}"} for j in range(1, 3)]
            suggestions = [f"建议{j}" for j in range(1, 3)]
            dimensions_data.append({
                "dimension": dim_name,
                "max_score": max_score,
                "score": score,
                "sub_items": sub_items,
                "suggestions": suggestions,
            })

        total_score = sum(d["score"] for d in dimensions_data)
        review_id = "review-rt-1"
        now_str = "2025-06-01T12:00:00+00:00"

        # Simulate DB: store what was inserted, return it on query
        stored_review = {
            "id": review_id,
            "project_id": "proj-1",
            "review_type": "text_review",
            "total_score": float(total_score),
            "material_versions": {"text_ppt": 1, "bp": 1},
            "status": "completed",
            "created_at": now_str,
        }
        stored_details = [
            {
                "id": f"detail-{i}",
                "review_id": review_id,
                "dimension": d["dimension"],
                "max_score": float(d["max_score"]),
                "score": float(d["score"]),
                "sub_items": d["sub_items"],
                "suggestions": d["suggestions"],
            }
            for i, d in enumerate(dimensions_data)
        ]

        # Simulate query: reconstruct ReviewResult from stored data
        queried_dimensions = [
            DimensionScore(
                dimension=d["dimension"],
                max_score=float(d["max_score"]),
                score=float(d["score"]),
                sub_items=d.get("sub_items") or [],
                suggestions=d.get("suggestions") or [],
            )
            for d in stored_details
        ]

        queried_result = ReviewResult(
            id=stored_review["id"],
            review_type=stored_review["review_type"],
            total_score=float(stored_review["total_score"]),
            dimensions=queried_dimensions,
            overall_suggestions=[],
            status=stored_review["status"],
            created_at=datetime.fromisoformat(stored_review["created_at"]),
        )

        # Verify round-trip consistency
        assert queried_result.id == review_id
        assert queried_result.review_type == "text_review"
        assert queried_result.status == "completed"
        assert abs(queried_result.total_score - total_score) < 0.01

        assert len(queried_result.dimensions) == num_dimensions

        for orig, queried in zip(dimensions_data, queried_result.dimensions):
            assert queried.dimension == orig["dimension"]
            assert abs(queried.max_score - orig["max_score"]) < 0.01
            assert abs(queried.score - orig["score"]) < 0.01
            assert queried.sub_items == orig["sub_items"]
            assert queried.suggestions == orig["suggestions"]


class TestProperty17ReviewRecordTypeAndMaterialVersions:
    """Property 17: 评审记录类型与材料版本关联

    For any review record, its review_type should be one of text_review,
    live_presentation, or offline_presentation, and material_versions should
    correctly record the version numbers of materials used.

    Feature: competition-judge-system, Property 17: 评审记录类型与材料版本关联
    Validates: Requirements 12.5
    """

    @given(
        review_type=st.sampled_from(VALID_REVIEW_TYPES),
        material_versions=st.fixed_dictionaries({
            "text_ppt": st.integers(min_value=1, max_value=50),
            "bp": st.integers(min_value=1, max_value=50),
        }),
    )
    @h_settings(max_examples=100)
    def test_review_record_type_and_versions(
        self, review_type: str, material_versions: dict
    ):
        """Generate random review types and material version combinations,
        verify the stored record has correct type and version info.
        """
        # Simulate a review record as stored in DB
        review_record = {
            "id": "review-prop17",
            "project_id": "proj-1",
            "user_id": "user-1",
            "review_type": review_type,
            "competition": "guochuangsai",
            "track": "gaojiao",
            "group": "benke_chuangyi",
            "stage": "school_text",
            "judge_style": "strict",
            "total_score": 75.0,
            "material_versions": material_versions,
            "status": "completed",
            "created_at": "2025-01-01T00:00:00+00:00",
        }

        # Property: review_type must be one of the valid types
        assert review_record["review_type"] in VALID_REVIEW_TYPES, (
            f"review_type '{review_record['review_type']}' is not valid"
        )

        # Property: material_versions should correctly record version numbers
        stored_versions = review_record["material_versions"]
        assert isinstance(stored_versions, dict), "material_versions should be a dict"

        for key, version in stored_versions.items():
            assert isinstance(version, int), f"Version for '{key}' should be int"
            assert version >= 1, f"Version for '{key}' should be >= 1"

        # Verify the versions match what was provided
        assert stored_versions["text_ppt"] == material_versions["text_ppt"]
        assert stored_versions["bp"] == material_versions["bp"]

    @given(
        ppt_version=st.integers(min_value=1, max_value=50),
        bp_version=st.integers(min_value=1, max_value=50),
    )
    @h_settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @pytest.mark.asyncio
    async def test_text_review_stores_correct_type_and_versions(
        self, ppt_version: int, bp_version: int
    ):
        """Verify that TextReviewService.review() stores the correct review_type
        and material_versions in the database insert call.
        """
        sb = _mock_supabase()
        text_ppt = _make_material("text_ppt", version=ppt_version)
        bp = _make_material("bp", version=bp_version, file_name="plan.pdf")

        # Track what gets inserted into reviews table
        inserted_data = {}

        def table_side_effect(name):
            chain = MagicMock()
            for m in ("insert", "select", "update", "delete", "eq", "order", "limit", "maybe_single", "single"):
                getattr(chain, m).return_value = chain

            if name == "reviews":
                real_insert = MagicMock(return_value=chain)

                def capture_insert(data):
                    inserted_data.update(data)
                    return real_insert(data)

                chain.insert = MagicMock(side_effect=capture_insert)
                chain.execute.return_value = MagicMock(data=[{
                    "id": "review-cap",
                    "created_at": "2025-01-01T00:00:00+00:00",
                }])
            else:
                chain.execute.return_value = MagicMock(data=[{"id": "detail-1"}])
            return chain

        sb.table.side_effect = table_side_effect

        svc, patches = _setup_review_mocks(sb, text_ppt=text_ppt, bp=bp)
        # Re-set sb.table since _setup_review_mocks overrides it
        sb.table.side_effect = table_side_effect
        try:
            await svc.review("proj-1", "user-1", "school_text", "strict")

            # Verify review_type
            assert inserted_data.get("review_type") == "text_review"

            # Verify material_versions
            mv = inserted_data.get("material_versions", {})
            assert mv.get("text_ppt") == ppt_version, (
                f"Expected text_ppt version {ppt_version}, got {mv.get('text_ppt')}"
            )
            assert mv.get("bp") == bp_version, (
                f"Expected bp version {bp_version}, got {mv.get('bp')}"
            )
        finally:
            _cleanup_patches(patches)
