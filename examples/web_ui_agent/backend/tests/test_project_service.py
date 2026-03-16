"""项目管理服务单元测试。"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.models.schemas import ProjectCreate
from app.services.project_service import ProjectService


def _make_project_row(
    project_id: str = "proj-1",
    user_id: str = "user-1",
    name: str = "测试项目",
    competition: str = "guochuangsai",
    track: str = "gaojiao",
    group: str = "benke_chuangyi",
    current_stage: str = "school_text",
) -> dict:
    return {
        "id": project_id,
        "user_id": user_id,
        "name": name,
        "competition": competition,
        "track": track,
        "group": group,
        "current_stage": current_stage,
        "created_at": "2025-01-01T00:00:00+00:00",
        "updated_at": "2025-01-01T00:00:00+00:00",
    }


def _mock_supabase() -> MagicMock:
    """Create a mock Supabase client with chainable table methods."""
    sb = MagicMock()
    return sb


def _setup_table_chain(sb: MagicMock, table_name: str, data: list | dict):
    """Set up a chainable mock for sb.table(name).method().method().execute()."""
    chain = MagicMock()
    chain.execute.return_value = MagicMock(data=data if isinstance(data, list) else data)
    # Make every chained method return the same chain object
    for method in ("insert", "select", "update", "delete", "eq", "order", "maybe_single"):
        getattr(chain, method).return_value = chain
    sb.table.return_value = chain
    return chain


class TestCreate:
    @pytest.mark.asyncio
    async def test_create_project_success(self):
        sb = _mock_supabase()
        row = _make_project_row()
        _setup_table_chain(sb, "projects", [row])
        svc = ProjectService(sb)

        data = ProjectCreate(
            name="测试项目",
            competition="guochuangsai",
            track="gaojiao",
            group="benke_chuangyi",
        )
        result = await svc.create("user-1", data)

        assert result.id == "proj-1"
        assert result.name == "测试项目"
        assert result.competition == "guochuangsai"
        assert result.materials_status == {
            "bp": False,
            "text_ppt": False,
            "presentation_ppt": False,
            "presentation_video": False,
        }

    @pytest.mark.asyncio
    async def test_create_project_empty_name_raises(self):
        sb = _mock_supabase()
        svc = ProjectService(sb)
        data = ProjectCreate(name="", competition="guochuangsai", track="gaojiao", group="benke_chuangyi")
        with pytest.raises(HTTPException) as exc_info:
            await svc.create("user-1", data)
        assert exc_info.value.status_code == 422
        assert "项目名称" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_create_project_whitespace_name_raises(self):
        sb = _mock_supabase()
        svc = ProjectService(sb)
        data = ProjectCreate(name="   ", competition="guochuangsai", track="gaojiao", group="benke_chuangyi")
        with pytest.raises(HTTPException) as exc_info:
            await svc.create("user-1", data)
        assert exc_info.value.status_code == 422

    @pytest.mark.asyncio
    async def test_create_project_empty_competition_raises(self):
        sb = _mock_supabase()
        svc = ProjectService(sb)
        data = ProjectCreate(name="项目", competition="", track="gaojiao", group="benke_chuangyi")
        with pytest.raises(HTTPException) as exc_info:
            await svc.create("user-1", data)
        assert exc_info.value.status_code == 422
        assert "赛事" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_create_project_empty_track_raises(self):
        sb = _mock_supabase()
        svc = ProjectService(sb)
        data = ProjectCreate(name="项目", competition="guochuangsai", track="", group="benke_chuangyi")
        with pytest.raises(HTTPException) as exc_info:
            await svc.create("user-1", data)
        assert exc_info.value.status_code == 422
        assert "赛道" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_create_project_empty_group_raises(self):
        sb = _mock_supabase()
        svc = ProjectService(sb)
        data = ProjectCreate(name="项目", competition="guochuangsai", track="gaojiao", group="")
        with pytest.raises(HTTPException) as exc_info:
            await svc.create("user-1", data)
        assert exc_info.value.status_code == 422
        assert "组别" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_create_project_multiple_empty_fields(self):
        sb = _mock_supabase()
        svc = ProjectService(sb)
        data = ProjectCreate(name="", competition="", track="", group="")
        with pytest.raises(HTTPException) as exc_info:
            await svc.create("user-1", data)
        assert exc_info.value.status_code == 422
        detail = str(exc_info.value.detail)
        assert "项目名称" in detail
        assert "赛事" in detail


class TestListProjects:
    @pytest.mark.asyncio
    async def test_list_returns_projects(self):
        sb = _mock_supabase()
        rows = [_make_project_row("p1"), _make_project_row("p2", name="项目2")]

        # Need to handle two different table calls: projects and project_materials
        call_count = {"n": 0}
        original_table = sb.table

        def table_side_effect(name):
            chain = MagicMock()
            for method in ("insert", "select", "update", "delete", "eq", "order", "maybe_single"):
                getattr(chain, method).return_value = chain
            if name == "projects":
                chain.execute.return_value = MagicMock(data=rows)
            else:  # project_materials
                chain.execute.return_value = MagicMock(data=[])
            return chain

        sb.table.side_effect = table_side_effect
        svc = ProjectService(sb)

        result = await svc.list_projects("user-1")
        assert len(result) == 2
        assert result[0].id == "p1"
        assert result[1].id == "p2"

    @pytest.mark.asyncio
    async def test_list_empty(self):
        sb = _mock_supabase()
        _setup_table_chain(sb, "projects", [])
        svc = ProjectService(sb)
        result = await svc.list_projects("user-1")
        assert result == []

    @pytest.mark.asyncio
    async def test_list_with_materials_status(self):
        sb = _mock_supabase()
        row = _make_project_row()

        def table_side_effect(name):
            chain = MagicMock()
            for method in ("insert", "select", "update", "delete", "eq", "order", "maybe_single"):
                getattr(chain, method).return_value = chain
            if name == "projects":
                chain.execute.return_value = MagicMock(data=[row])
            else:  # project_materials
                chain.execute.return_value = MagicMock(
                    data=[{"material_type": "bp"}, {"material_type": "text_ppt"}]
                )
            return chain

        sb.table.side_effect = table_side_effect
        svc = ProjectService(sb)

        result = await svc.list_projects("user-1")
        assert len(result) == 1
        assert result[0].materials_status["bp"] is True
        assert result[0].materials_status["text_ppt"] is True
        assert result[0].materials_status["presentation_ppt"] is False
        assert result[0].materials_status["presentation_video"] is False


class TestGetProject:
    @pytest.mark.asyncio
    async def test_get_project_success(self):
        sb = _mock_supabase()
        row = _make_project_row()

        def table_side_effect(name):
            chain = MagicMock()
            for method in ("insert", "select", "update", "delete", "eq", "order", "maybe_single"):
                getattr(chain, method).return_value = chain
            if name == "projects":
                chain.execute.return_value = MagicMock(data=row)
            else:
                chain.execute.return_value = MagicMock(data=[])
            return chain

        sb.table.side_effect = table_side_effect
        svc = ProjectService(sb)

        result = await svc.get_project("proj-1", "user-1")
        assert result.id == "proj-1"
        assert result.name == "测试项目"

    @pytest.mark.asyncio
    async def test_get_project_not_found(self):
        sb = _mock_supabase()
        chain = MagicMock()
        for method in ("select", "eq", "maybe_single"):
            getattr(chain, method).return_value = chain
        chain.execute.return_value = MagicMock(data=None)
        sb.table.return_value = chain
        svc = ProjectService(sb)

        with pytest.raises(HTTPException) as exc_info:
            await svc.get_project("nonexistent", "user-1")
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_get_project_wrong_user_403(self):
        sb = _mock_supabase()
        row = _make_project_row(user_id="other-user")

        def table_side_effect(name):
            chain = MagicMock()
            for method in ("insert", "select", "update", "delete", "eq", "order", "maybe_single"):
                getattr(chain, method).return_value = chain
            chain.execute.return_value = MagicMock(data=row)
            return chain

        sb.table.side_effect = table_side_effect
        svc = ProjectService(sb)

        with pytest.raises(HTTPException) as exc_info:
            await svc.get_project("proj-1", "user-1")
        assert exc_info.value.status_code == 403


class TestUpdateProject:
    @pytest.mark.asyncio
    async def test_update_name(self):
        sb = _mock_supabase()
        row = _make_project_row()
        updated_row = {**row, "name": "新名称"}

        call_count = {"n": 0}

        def table_side_effect(name):
            chain = MagicMock()
            for method in ("insert", "select", "update", "delete", "eq", "order", "maybe_single"):
                getattr(chain, method).return_value = chain
            if name == "projects":
                call_count["n"] += 1
                if call_count["n"] == 1:
                    # First call: _fetch_project (select)
                    chain.execute.return_value = MagicMock(data=row)
                else:
                    # Second call: update
                    chain.execute.return_value = MagicMock(data=[updated_row])
            else:
                chain.execute.return_value = MagicMock(data=[])
            return chain

        sb.table.side_effect = table_side_effect
        svc = ProjectService(sb)

        result = await svc.update_project("proj-1", "user-1", {"name": "新名称"})
        assert result.name == "新名称"

    @pytest.mark.asyncio
    async def test_update_wrong_user_403(self):
        sb = _mock_supabase()
        row = _make_project_row(user_id="other-user")

        chain = MagicMock()
        for method in ("insert", "select", "update", "delete", "eq", "order", "maybe_single"):
            getattr(chain, method).return_value = chain
        chain.execute.return_value = MagicMock(data=row)
        sb.table.return_value = chain
        svc = ProjectService(sb)

        with pytest.raises(HTTPException) as exc_info:
            await svc.update_project("proj-1", "user-1", {"name": "新名称"})
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_update_no_fields_raises(self):
        sb = _mock_supabase()
        row = _make_project_row()

        chain = MagicMock()
        for method in ("insert", "select", "update", "delete", "eq", "order", "maybe_single"):
            getattr(chain, method).return_value = chain
        chain.execute.return_value = MagicMock(data=row)
        sb.table.return_value = chain
        svc = ProjectService(sb)

        with pytest.raises(HTTPException) as exc_info:
            await svc.update_project("proj-1", "user-1", {})
        assert exc_info.value.status_code == 422

    @pytest.mark.asyncio
    async def test_update_none_values_filtered(self):
        sb = _mock_supabase()
        row = _make_project_row()

        chain = MagicMock()
        for method in ("insert", "select", "update", "delete", "eq", "order", "maybe_single"):
            getattr(chain, method).return_value = chain
        chain.execute.return_value = MagicMock(data=row)
        sb.table.return_value = chain
        svc = ProjectService(sb)

        with pytest.raises(HTTPException) as exc_info:
            await svc.update_project("proj-1", "user-1", {"name": None, "current_stage": None})
        assert exc_info.value.status_code == 422


# ── 属性测试 (Property-Based Tests) ──────────────────────────
#
# 使用 hypothesis 验证 ProjectService 的通用正确性属性。
# Feature: competition-judge-system

from hypothesis import given, settings, assume
import hypothesis.strategies as st


# ── 策略定义 ──────────────────────────────────────────────────

# 非空非纯空白字符串（有效字段值）
_valid_str = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "P")),
    min_size=1,
    max_size=30,
).filter(lambda s: s.strip() != "")

# 空或纯空白字符串（无效字段值）
_empty_or_whitespace = st.one_of(
    st.just(""),
    st.text(alphabet=" \t", min_size=1, max_size=10),
)

# 四个字段各自可能有效或无效的策略
_field_strategy = st.one_of(_valid_str, _empty_or_whitespace)


class TestProperty14FieldValidation:
    """Property 14: 项目创建字段验证

    对于任意项目创建请求，缺少项目名称、赛事类型、赛道或组别中
    任一必填字段（空或纯空白）时，系统应拒绝创建并返回验证错误(422)。

    # Feature: competition-judge-system, Property 14: 项目创建字段验证
    # Validates: Requirements 9.3
    """

    @given(
        name=_field_strategy,
        competition=_field_strategy,
        track=_field_strategy,
        group=_field_strategy,
    )
    @settings(max_examples=200)
    @pytest.mark.asyncio
    async def test_missing_required_field_rejected(
        self, name: str, competition: str, track: str, group: str
    ):
        """Any combination with at least one empty/whitespace field should raise HTTPException 422."""
        has_invalid = (
            not name.strip()
            or not competition.strip()
            or not track.strip()
            or not group.strip()
        )
        # Only test cases where at least one field is invalid
        assume(has_invalid)

        sb = _mock_supabase()
        svc = ProjectService(sb)
        data = ProjectCreate(
            name=name,
            competition=competition,
            track=track,
            group=group,
        )
        with pytest.raises(HTTPException) as exc_info:
            await svc.create("user-1", data)
        assert exc_info.value.status_code == 422

    @given(
        name=_valid_str,
        competition=_valid_str,
        track=_valid_str,
        group=_valid_str,
    )
    @settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_all_valid_fields_accepted(
        self, name: str, competition: str, track: str, group: str
    ):
        """When all fields are valid (non-empty, non-whitespace), creation should succeed."""
        sb = _mock_supabase()
        row = _make_project_row(
            name=name.strip(),
            competition=competition.strip(),
            track=track.strip(),
            group=group.strip(),
        )
        _setup_table_chain(sb, "projects", [row])
        svc = ProjectService(sb)

        data = ProjectCreate(
            name=name,
            competition=competition,
            track=track,
            group=group,
        )
        result = await svc.create("user-1", data)
        assert result.name == name.strip()


class TestProperty15CRUDConsistency:
    """Property 15: 项目与评审记录的CRUD一致性

    对于任意用户，创建多个项目后应能查询到所有项目。

    # Feature: competition-judge-system, Property 15: 项目与评审记录的CRUD一致性
    # Validates: Requirements 9.2, 9.5, 9.6
    """

    @given(num_projects=st.integers(min_value=1, max_value=10))
    @settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_all_created_projects_queryable(self, num_projects: int):
        """After creating N projects, list_projects should return all N."""
        sb = _mock_supabase()
        user_id = "user-1"

        # Generate N project rows
        rows = [
            _make_project_row(
                project_id=f"proj-{i}",
                user_id=user_id,
                name=f"项目{i}",
            )
            for i in range(num_projects)
        ]

        # Track calls: create calls return individual rows, list returns all
        create_call_idx = {"n": 0}

        def table_side_effect(table_name):
            chain = MagicMock()
            for method in ("insert", "select", "update", "delete", "eq", "order", "maybe_single"):
                getattr(chain, method).return_value = chain

            if table_name == "projects":
                # For insert (create) calls, return the current row
                idx = create_call_idx["n"]
                if idx < num_projects:
                    chain.execute.return_value = MagicMock(data=[rows[idx]])
                    create_call_idx["n"] += 1
                else:
                    # For select (list) call, return all rows
                    chain.execute.return_value = MagicMock(data=rows)
            else:
                # project_materials table
                chain.execute.return_value = MagicMock(data=[])
            return chain

        sb.table.side_effect = table_side_effect
        svc = ProjectService(sb)

        # Create all projects
        for i in range(num_projects):
            data = ProjectCreate(
                name=f"项目{i}",
                competition="guochuangsai",
                track="gaojiao",
                group="benke_chuangyi",
            )
            await svc.create(user_id, data)

        # Now list — reset side_effect to return all rows
        def list_table_side_effect(table_name):
            chain = MagicMock()
            for method in ("insert", "select", "update", "delete", "eq", "order", "maybe_single"):
                getattr(chain, method).return_value = chain
            if table_name == "projects":
                chain.execute.return_value = MagicMock(data=rows)
            else:
                chain.execute.return_value = MagicMock(data=[])
            return chain

        sb.table.side_effect = list_table_side_effect

        result = await svc.list_projects(user_id)
        assert len(result) == num_projects
        returned_ids = {p.id for p in result}
        expected_ids = {f"proj-{i}" for i in range(num_projects)}
        assert returned_ids == expected_ids


class TestProperty16DataRoundTrip:
    """Property 16: 项目数据持久化往返

    对于任意创建的项目，查询返回的赛事类型、赛道、组别和比赛阶段信息
    应与创建时一致。

    # Feature: competition-judge-system, Property 16: 项目数据持久化往返
    # Validates: Requirements 12.3
    """

    @given(
        name=_valid_str,
        competition=_valid_str,
        track=_valid_str,
        group=_valid_str,
    )
    @settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_project_data_round_trip(
        self, name: str, competition: str, track: str, group: str
    ):
        """Created project data should be identical when queried back."""
        sb = _mock_supabase()
        user_id = "user-1"
        project_id = "proj-rt"

        # Simulate Supabase echoing back the inserted data
        row = _make_project_row(
            project_id=project_id,
            user_id=user_id,
            name=name.strip(),
            competition=competition.strip(),
            track=track.strip(),
            group=group.strip(),
        )

        call_count = {"n": 0}

        def table_side_effect(table_name):
            chain = MagicMock()
            for method in ("insert", "select", "update", "delete", "eq", "order", "maybe_single"):
                getattr(chain, method).return_value = chain
            if table_name == "projects":
                call_count["n"] += 1
                if call_count["n"] == 1:
                    # create: insert returns [row]
                    chain.execute.return_value = MagicMock(data=[row])
                else:
                    # get_project: select returns row (maybe_single)
                    chain.execute.return_value = MagicMock(data=row)
            else:
                # project_materials
                chain.execute.return_value = MagicMock(data=[])
            return chain

        sb.table.side_effect = table_side_effect
        svc = ProjectService(sb)

        # Create
        data = ProjectCreate(
            name=name,
            competition=competition,
            track=track,
            group=group,
        )
        created = await svc.create(user_id, data)

        # Query back
        fetched = await svc.get_project(project_id, user_id)

        # Round-trip verification
        assert fetched.competition == competition.strip()
        assert fetched.track == track.strip()
        assert fetched.group == group.strip()
        assert fetched.current_stage == "school_text"
        assert fetched.name == name.strip()
