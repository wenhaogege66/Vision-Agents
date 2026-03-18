"""材料管理服务单元测试。"""

import io
from unittest.mock import MagicMock, AsyncMock

import pytest
from fastapi import HTTPException, UploadFile

from app.services.material_service import MaterialService


def _mock_supabase() -> MagicMock:
    """Create a mock Supabase client with chainable table and storage methods."""
    sb = MagicMock()
    return sb


def _setup_table_chain(sb: MagicMock, data: list | dict | None):
    """Set up a chainable mock for sb.table(name).method()...execute()."""
    chain = MagicMock()
    chain.execute.return_value = MagicMock(data=data if data is not None else [])
    for method in (
        "insert", "select", "update", "delete",
        "eq", "order", "limit", "maybe_single",
    ):
        getattr(chain, method).return_value = chain
    sb.table.return_value = chain
    return chain


def _setup_storage(sb: MagicMock):
    """Set up a mock for sb.storage.from_(bucket).upload(...)."""
    bucket = MagicMock()
    sb.storage.from_.return_value = bucket
    return bucket


def _make_upload_file(
    filename: str = "plan.pdf",
    content: bytes = b"fake-content",
    content_type: str = "application/pdf",
) -> UploadFile:
    """Create a mock UploadFile."""
    return UploadFile(
        filename=filename,
        file=io.BytesIO(content),
        headers={"content-type": content_type},
    )


def _make_material_row(
    material_id: str = "mat-1",
    project_id: str = "proj-1",
    material_type: str = "bp",
    file_name: str = "plan.pdf",
    version: int = 1,
    is_latest: bool = True,
) -> dict:
    return {
        "id": material_id,
        "project_id": project_id,
        "material_type": material_type,
        "file_path": f"{project_id}/{material_type}/v{version}_{file_name}",
        "file_name": file_name,
        "file_size": 1024,
        "version": version,
        "is_latest": is_latest,
        "image_paths": None,
        "created_at": "2025-01-01T00:00:00+00:00",
    }


# ── Upload Tests ─────────────────────────────────────────────


class TestUpload:
    @pytest.mark.asyncio
    async def test_upload_bp_pdf_success(self):
        sb = _mock_supabase()
        bucket = _setup_storage(sb)
        row = _make_material_row()

        call_count = {"n": 0}

        def table_side_effect(name):
            chain = MagicMock()
            for m in ("insert", "select", "update", "delete", "eq", "order", "limit", "maybe_single"):
                getattr(chain, m).return_value = chain
            call_count["n"] += 1
            if call_count["n"] == 1:
                # _next_version: no existing versions
                chain.execute.return_value = MagicMock(data=[])
            elif call_count["n"] == 2:
                # update old is_latest
                chain.execute.return_value = MagicMock(data=[])
            else:
                # insert new record
                chain.execute.return_value = MagicMock(data=[row])
            return chain

        sb.table.side_effect = table_side_effect
        svc = MaterialService(sb)

        file = _make_upload_file("plan.pdf", b"x" * 100)
        result = await svc.upload("proj-1", "bp", file)

        assert result.id == "mat-1"
        assert result.material_type == "bp"
        assert result.version == 1
        assert result.file_name == "plan.pdf"
        bucket.upload.assert_called_once()

    @pytest.mark.asyncio
    async def test_upload_invalid_format_raises_400(self):
        sb = _mock_supabase()
        svc = MaterialService(sb)

        file = _make_upload_file("plan.txt", b"content")
        with pytest.raises(HTTPException) as exc_info:
            await svc.upload("proj-1", "bp", file)
        assert exc_info.value.status_code == 400
        assert "不支持的文件格式" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_upload_invalid_material_type_raises_400(self):
        sb = _mock_supabase()
        svc = MaterialService(sb)

        file = _make_upload_file("plan.pdf", b"content")
        with pytest.raises(HTTPException) as exc_info:
            await svc.upload("proj-1", "invalid_type", file)
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_upload_ppt_too_large_raises_413(self):
        sb = _mock_supabase()
        svc = MaterialService(sb)

        # 50MB + 1 byte
        large_content = b"x" * (52428800 + 1)
        file = _make_upload_file("slides.pptx", large_content, "application/vnd.openxmlformats")
        with pytest.raises(HTTPException) as exc_info:
            await svc.upload("proj-1", "text_ppt", file)
        assert exc_info.value.status_code == 413

    @pytest.mark.asyncio
    async def test_upload_ppt_exactly_50mb_accepted(self):
        sb = _mock_supabase()
        bucket = _setup_storage(sb)
        row = _make_material_row(material_type="text_ppt", file_name="slides.pptx")

        call_count = {"n": 0}

        def table_side_effect(name):
            chain = MagicMock()
            for m in ("insert", "select", "update", "delete", "eq", "order", "limit", "maybe_single"):
                getattr(chain, m).return_value = chain
            call_count["n"] += 1
            if call_count["n"] == 1:
                chain.execute.return_value = MagicMock(data=[])
            elif call_count["n"] == 2:
                chain.execute.return_value = MagicMock(data=[])
            else:
                chain.execute.return_value = MagicMock(data=[row])
            return chain

        sb.table.side_effect = table_side_effect
        svc = MaterialService(sb)

        content = b"x" * 52428800  # exactly 50MB
        file = _make_upload_file("slides.pptx", content)
        result = await svc.upload("proj-1", "text_ppt", file)
        assert result.material_type == "text_ppt"

    @pytest.mark.asyncio
    async def test_upload_video_too_large_raises_413(self):
        sb = _mock_supabase()
        svc = MaterialService(sb)

        # 500MB + 1 byte — we can't allocate that much memory in tests,
        # so we mock file.read() to return a size indicator
        file = MagicMock(spec=UploadFile)
        file.filename = "demo.mp4"
        file.content_type = "video/mp4"
        file.read = AsyncMock(return_value=b"x" * (524288000 + 1))

        with pytest.raises(HTTPException) as exc_info:
            await svc.upload("proj-1", "presentation_video", file)
        assert exc_info.value.status_code == 413

    @pytest.mark.asyncio
    async def test_upload_increments_version(self):
        sb = _mock_supabase()
        bucket = _setup_storage(sb)
        row_v2 = _make_material_row(version=2)

        call_count = {"n": 0}

        def table_side_effect(name):
            chain = MagicMock()
            for m in ("insert", "select", "update", "delete", "eq", "order", "limit", "maybe_single"):
                getattr(chain, m).return_value = chain
            call_count["n"] += 1
            if call_count["n"] == 1:
                # _next_version: existing version 1
                chain.execute.return_value = MagicMock(data=[{"version": 1}])
            elif call_count["n"] == 2:
                # update old is_latest
                chain.execute.return_value = MagicMock(data=[])
            else:
                # insert new record
                chain.execute.return_value = MagicMock(data=[row_v2])
            return chain

        sb.table.side_effect = table_side_effect
        svc = MaterialService(sb)

        file = _make_upload_file("plan.pdf", b"new-content")
        result = await svc.upload("proj-1", "bp", file)
        assert result.version == 2

    @pytest.mark.asyncio
    async def test_upload_video_mp4_accepted(self):
        sb = _mock_supabase()
        bucket = _setup_storage(sb)
        row = _make_material_row(material_type="presentation_video", file_name="demo.mp4")

        call_count = {"n": 0}

        def table_side_effect(name):
            chain = MagicMock()
            for m in ("insert", "select", "update", "delete", "eq", "order", "limit", "maybe_single"):
                getattr(chain, m).return_value = chain
            call_count["n"] += 1
            if call_count["n"] == 1:
                chain.execute.return_value = MagicMock(data=[])
            elif call_count["n"] == 2:
                chain.execute.return_value = MagicMock(data=[])
            else:
                chain.execute.return_value = MagicMock(data=[row])
            return chain

        sb.table.side_effect = table_side_effect
        svc = MaterialService(sb)

        file = _make_upload_file("demo.mp4", b"video-data", "video/mp4")
        result = await svc.upload("proj-1", "presentation_video", file)
        assert result.material_type == "presentation_video"

    @pytest.mark.asyncio
    async def test_upload_storage_path_format(self):
        """Verify the storage path follows {project_id}/{material_type}/v{version}_{filename}."""
        sb = _mock_supabase()
        bucket = _setup_storage(sb)
        row = _make_material_row()

        call_count = {"n": 0}

        def table_side_effect(name):
            chain = MagicMock()
            for m in ("insert", "select", "update", "delete", "eq", "order", "limit", "maybe_single"):
                getattr(chain, m).return_value = chain
            call_count["n"] += 1
            if call_count["n"] == 1:
                chain.execute.return_value = MagicMock(data=[])
            elif call_count["n"] == 2:
                chain.execute.return_value = MagicMock(data=[])
            else:
                chain.execute.return_value = MagicMock(data=[row])
            return chain

        sb.table.side_effect = table_side_effect
        svc = MaterialService(sb)

        file = _make_upload_file("plan.pdf", b"data")
        await svc.upload("proj-1", "bp", file)

        # Check the path passed to storage.upload
        call_args = bucket.upload.call_args
        path = call_args.kwargs.get("path") or call_args[0][0] if call_args[0] else call_args.kwargs["path"]
        assert path == "proj-1/bp/v1_plan.pdf"


# ── GetLatest Tests ──────────────────────────────────────────


class TestGetLatest:
    @pytest.mark.asyncio
    async def test_get_latest_returns_material(self):
        sb = _mock_supabase()
        row = _make_material_row()
        chain = MagicMock()
        for m in ("select", "eq", "maybe_single"):
            getattr(chain, m).return_value = chain
        chain.execute.return_value = MagicMock(data=row)
        sb.table.return_value = chain
        svc = MaterialService(sb)

        result = await svc.get_latest("proj-1", "bp")
        assert result is not None
        assert result["id"] == "mat-1"
        assert result["is_latest"] is True

    @pytest.mark.asyncio
    async def test_get_latest_returns_none_when_empty(self):
        sb = _mock_supabase()
        chain = MagicMock()
        for m in ("select", "eq", "maybe_single"):
            getattr(chain, m).return_value = chain
        chain.execute.return_value = MagicMock(data=None)
        sb.table.return_value = chain
        svc = MaterialService(sb)

        result = await svc.get_latest("proj-1", "bp")
        assert result is None


# ── GetVersions Tests ────────────────────────────────────────


class TestGetVersions:
    @pytest.mark.asyncio
    async def test_get_versions_returns_all(self):
        sb = _mock_supabase()
        rows = [
            _make_material_row(material_id="m2", version=2, is_latest=True),
            _make_material_row(material_id="m1", version=1, is_latest=False),
        ]
        _setup_table_chain(sb, rows)
        svc = MaterialService(sb)

        result = await svc.get_versions("proj-1", "bp")
        assert len(result) == 2
        assert result[0]["version"] == 2
        assert result[1]["version"] == 1

    @pytest.mark.asyncio
    async def test_get_versions_empty(self):
        sb = _mock_supabase()
        _setup_table_chain(sb, [])
        svc = MaterialService(sb)

        result = await svc.get_versions("proj-1", "bp")
        assert result == []


# ── File Format Validation Tests ─────────────────────────────


class TestFileFormatValidation:
    """Test that each material type only accepts its allowed formats."""

    @pytest.mark.asyncio
    async def test_bp_accepts_docx(self):
        sb = _mock_supabase()
        bucket = _setup_storage(sb)
        row = _make_material_row(file_name="plan.docx")

        call_count = {"n": 0}

        def table_side_effect(name):
            chain = MagicMock()
            for m in ("insert", "select", "update", "delete", "eq", "order", "limit", "maybe_single"):
                getattr(chain, m).return_value = chain
            call_count["n"] += 1
            if call_count["n"] == 1:
                chain.execute.return_value = MagicMock(data=[])
            elif call_count["n"] == 2:
                chain.execute.return_value = MagicMock(data=[])
            else:
                chain.execute.return_value = MagicMock(data=[row])
            return chain

        sb.table.side_effect = table_side_effect
        svc = MaterialService(sb)

        file = _make_upload_file("plan.docx", b"data")
        result = await svc.upload("proj-1", "bp", file)
        assert result.file_name == "plan.docx"

    @pytest.mark.asyncio
    async def test_bp_rejects_pptx(self):
        sb = _mock_supabase()
        svc = MaterialService(sb)
        file = _make_upload_file("plan.pptx", b"data")
        with pytest.raises(HTTPException) as exc_info:
            await svc.upload("proj-1", "bp", file)
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_ppt_accepts_pptx(self):
        sb = _mock_supabase()
        bucket = _setup_storage(sb)
        row = _make_material_row(material_type="presentation_ppt", file_name="slides.pptx")

        call_count = {"n": 0}

        def table_side_effect(name):
            chain = MagicMock()
            for m in ("insert", "select", "update", "delete", "eq", "order", "limit", "maybe_single"):
                getattr(chain, m).return_value = chain
            call_count["n"] += 1
            if call_count["n"] == 1:
                chain.execute.return_value = MagicMock(data=[])
            elif call_count["n"] == 2:
                chain.execute.return_value = MagicMock(data=[])
            else:
                chain.execute.return_value = MagicMock(data=[row])
            return chain

        sb.table.side_effect = table_side_effect
        svc = MaterialService(sb)

        file = _make_upload_file("slides.pptx", b"data")
        result = await svc.upload("proj-1", "presentation_ppt", file)
        assert result.file_name == "slides.pptx"

    @pytest.mark.asyncio
    async def test_video_rejects_avi(self):
        sb = _mock_supabase()
        svc = MaterialService(sb)
        file = _make_upload_file("demo.avi", b"data")
        with pytest.raises(HTTPException) as exc_info:
            await svc.upload("proj-1", "presentation_video", file)
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_video_accepts_webm(self):
        sb = _mock_supabase()
        bucket = _setup_storage(sb)
        row = _make_material_row(material_type="presentation_video", file_name="demo.webm")

        call_count = {"n": 0}

        def table_side_effect(name):
            chain = MagicMock()
            for m in ("insert", "select", "update", "delete", "eq", "order", "limit", "maybe_single"):
                getattr(chain, m).return_value = chain
            call_count["n"] += 1
            if call_count["n"] == 1:
                chain.execute.return_value = MagicMock(data=[])
            elif call_count["n"] == 2:
                chain.execute.return_value = MagicMock(data=[])
            else:
                chain.execute.return_value = MagicMock(data=[row])
            return chain

        sb.table.side_effect = table_side_effect
        svc = MaterialService(sb)

        file = _make_upload_file("demo.webm", b"data", "video/webm")
        result = await svc.upload("proj-1", "presentation_video", file)
        assert result.file_name == "demo.webm"


# ── 属性测试 (Property-Based Tests) ──────────────────────────
#
# 使用 hypothesis 验证材料管理服务的通用正确性属性。
# Feature: competition-judge-system

from hypothesis import given, settings as h_settings, assume
import hypothesis.strategies as st

from app.utils.file_utils import (
    validate_file_format,
    validate_file_size,
    ALLOWED_EXTENSIONS,
)


# ── Hypothesis 策略 ──────────────────────────────────────────

# 所有材料类型
ALL_MATERIAL_TYPES = list(ALLOWED_EXTENSIONS.keys())

# 材料类型 → 允许的扩展名列表
_EXT_MAP = {mt: sorted(exts) for mt, exts in ALLOWED_EXTENSIONS.items()}

# 不在任何允许列表中的扩展名
_REJECTED_EXTENSIONS = [".txt", ".avi", ".jpg", ".exe", ".zip", ".html", ".csv"]


def _material_type_strategy() -> st.SearchStrategy[str]:
    """随机选取一个有效的材料类型。"""
    return st.sampled_from(ALL_MATERIAL_TYPES)


def _valid_ext_for_type(material_type: str) -> st.SearchStrategy[str]:
    """为给定材料类型随机选取一个允许的扩展名。"""
    return st.sampled_from(_EXT_MAP[material_type])


def _rejected_ext_strategy() -> st.SearchStrategy[str]:
    """随机选取一个不被任何材料类型接受的扩展名。"""
    return st.sampled_from(_REJECTED_EXTENSIONS)


def _filename_base_strategy() -> st.SearchStrategy[str]:
    """生成合法的文件名基础部分（不含扩展名）。"""
    return st.from_regex(r"[a-z][a-z0-9_]{0,15}", fullmatch=True)


class TestProperty6FileFormatAndSizeValidation:
    """Property 6: 文件格式与大小验证

    对于任意上传请求，系统应根据材料类型验证文件扩展名
    （BP接受.docx/.pdf，PPT接受.pptx/.pdf，视频接受.mp4/.webm），
    且PPT/BP文件超过50MB或视频文件超过500MB时应拒绝上传。

    Feature: competition-judge-system, Property 6: 文件格式与大小验证
    Validates: Requirements 3.2, 3.7, 3.8
    """

    @given(
        material_type=_material_type_strategy(),
        base_name=_filename_base_strategy(),
        data=st.data(),
    )
    @h_settings(max_examples=100)
    def test_valid_extension_accepted(self, material_type: str, base_name: str, data):
        """任意材料类型 + 其允许的扩展名 → 格式验证通过。"""
        ext = data.draw(_valid_ext_for_type(material_type))
        filename = f"{base_name}{ext}"

        ok, err = validate_file_format(filename, material_type)
        assert ok is True, f"{filename} 应被 {material_type} 接受，但被拒绝: {err}"
        assert err == ""

    @given(
        material_type=_material_type_strategy(),
        base_name=_filename_base_strategy(),
        bad_ext=_rejected_ext_strategy(),
    )
    @h_settings(max_examples=100)
    def test_invalid_extension_rejected(
        self, material_type: str, base_name: str, bad_ext: str
    ):
        """任意材料类型 + 不允许的扩展名 → 格式验证失败。"""
        # 确保 bad_ext 确实不在该类型的允许列表中
        assume(bad_ext not in ALLOWED_EXTENSIONS[material_type])
        filename = f"{base_name}{bad_ext}"

        ok, err = validate_file_format(filename, material_type)
        assert ok is False, f"{filename} 应被 {material_type} 拒绝"
        assert "不支持的文件格式" in err

    @given(
        material_type=st.sampled_from(["bp", "text_ppt", "presentation_ppt"]),
        size_over=st.integers(min_value=1, max_value=1024 * 1024),
    )
    @h_settings(max_examples=100)
    def test_ppt_bp_over_50mb_rejected(self, material_type: str, size_over: int):
        """PPT/BP 文件超过 50MB 时应拒绝。"""
        size = 52428800 + size_over  # 50MB + extra

        ok, err = validate_file_size(size, material_type)
        assert ok is False, f"{material_type} {size}B 应被拒绝"
        assert "超过限制" in err

    @given(
        material_type=st.sampled_from(["bp", "text_ppt", "presentation_ppt"]),
        size=st.integers(min_value=0, max_value=52428800),
    )
    @h_settings(max_examples=100)
    def test_ppt_bp_within_50mb_accepted(self, material_type: str, size: int):
        """PPT/BP 文件 ≤ 50MB 时应接受。"""
        ok, err = validate_file_size(size, material_type)
        assert ok is True, f"{material_type} {size}B 应被接受，但被拒绝: {err}"

    @given(size_over=st.integers(min_value=1, max_value=10 * 1024 * 1024))
    @h_settings(max_examples=100)
    def test_video_over_500mb_rejected(self, size_over: int):
        """视频文件超过 500MB 时应拒绝。"""
        size = 524288000 + size_over  # 500MB + extra

        ok, err = validate_file_size(size, "presentation_video")
        assert ok is False, f"presentation_video {size}B 应被拒绝"
        assert "超过限制" in err

    @given(size=st.integers(min_value=0, max_value=524288000))
    @h_settings(max_examples=100)
    def test_video_within_500mb_accepted(self, size: int):
        """视频文件 ≤ 500MB 时应接受。"""
        ok, err = validate_file_size(size, "presentation_video")
        assert ok is True, f"presentation_video {size}B 应被接受，但被拒绝: {err}"


class TestProperty7VersionManagementConsistency:
    """Property 7: 材料版本管理一致性

    对于任意项目和材料类型，连续上传N个版本后，系统应保留所有N个版本记录，
    且仅最新版本的 is_latest 标记为 true，其余为 false。

    Feature: competition-judge-system, Property 7: 材料版本管理一致性
    Validates: Requirements 3.3, 3.4
    """

    @given(
        num_uploads=st.integers(min_value=1, max_value=10),
        material_type=st.sampled_from(["bp", "text_ppt", "presentation_ppt"]),
    )
    @h_settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_n_uploads_produce_n_versions_with_single_latest(
        self, num_uploads: int, material_type: str
    ):
        """连续上传 N 次后，应有 N 条版本记录，且仅最新版本 is_latest=True。"""
        project_id = "proj-test"
        # 模拟数据库中的材料记录
        db_records: list[dict] = []

        # 根据材料类型选择合法的文件扩展名
        ext = ".pdf" if material_type == "bp" else ".pptx"

        sb = _mock_supabase()
        _setup_storage(sb)

        # 每次 upload 调用会触发 3 次 sb.table():
        #   1) _next_version (select)
        #   2) update old is_latest
        #   3) insert new record
        # 用全局计数器追踪每轮的第几次调用
        call_counter = {"n": 0}

        def table_side_effect(name):
            chain = MagicMock()
            for m in ("insert", "select", "update", "delete",
                       "eq", "order", "limit", "maybe_single"):
                getattr(chain, m).return_value = chain

            call_counter["n"] += 1
            phase = (call_counter["n"] - 1) % 3  # 0=select, 1=update, 2=insert

            if phase == 0:
                # _next_version: 返回当前最大版本
                sorted_recs = sorted(db_records, key=lambda r: r["version"], reverse=True)
                chain.execute.return_value = MagicMock(data=sorted_recs[:1])
            elif phase == 1:
                # update old is_latest → False
                for r in db_records:
                    if r["is_latest"]:
                        r["is_latest"] = False
                chain.execute.return_value = MagicMock(data=[])
            else:
                # insert: 计算新版本号并记录
                next_ver = (len(db_records) + 1)
                new_row = {
                    "id": f"mat-{next_ver}",
                    "project_id": project_id,
                    "material_type": material_type,
                    "file_path": f"{project_id}/{material_type}/v{next_ver}_file{ext}",
                    "file_name": f"file_v{next_ver}{ext}",
                    "file_size": 100,
                    "version": next_ver,
                    "is_latest": True,
                    "created_at": "2025-01-01T00:00:00+00:00",
                }
                db_records.append(new_row)
                chain.execute.return_value = MagicMock(data=[new_row])

            return chain

        sb.table.side_effect = table_side_effect
        svc = MaterialService(sb)

        # 连续上传 N 次
        for i in range(num_uploads):
            file = _make_upload_file(f"file_v{i+1}{ext}", b"x" * 100)
            result = await svc.upload(project_id, material_type, file)
            assert result.version == i + 1

        # 验证：共有 N 条记录
        assert len(db_records) == num_uploads

        # 验证：仅最新版本 is_latest=True
        latest_records = [r for r in db_records if r["is_latest"]]
        assert len(latest_records) == 1, (
            f"应有且仅有1条 is_latest=True 的记录，实际有 {len(latest_records)}"
        )
        assert latest_records[0]["version"] == num_uploads

        # 验证：其余版本 is_latest=False
        old_records = [r for r in db_records if not r["is_latest"]]
        assert len(old_records) == num_uploads - 1



