"""Preservation 属性测试：验证非 PPTX 上传行为在修复前后保持不变。

这些测试在未修复代码上必须通过——它们编码了需要保持的基线行为。
修复后重新运行这些测试，确认无回归。

**Validates: Requirements 3.1, 3.2, 3.4**
"""

import io
import time
from unittest.mock import MagicMock, patch

import pytest
from hypothesis import given, settings as h_settings, assume
import hypothesis.strategies as st

from fastapi.testclient import TestClient

from app.main import app
from app.models.database import get_supabase
from app.models.schemas import UserInfo
from app.routes.auth import get_current_user
from app.routes.materials import _PPT_TYPES
from app.services.material_service import MaterialService
from app.services.ppt_convert_service import PPTConvertService


# ── Helpers ──────────────────────────────────────────────────


def _mock_supabase() -> MagicMock:
    return MagicMock()


def _make_material_row(
    material_type: str = "bp",
    file_name: str = "plan.pdf",
    version: int = 1,
) -> dict:
    return {
        "id": f"mat-{version}",
        "project_id": "proj-1",
        "material_type": material_type,
        "file_path": f"proj-1/{material_type}/v{version}_{file_name}",
        "file_name": file_name,
        "file_size": 1024,
        "version": version,
        "is_latest": True,
        "image_paths": None,
        "created_at": "2025-01-01T00:00:00+00:00",
    }


# Non-PPT material types and their valid file configs
_NON_PPT_UPLOADS = [
    ("bp", "plan.pdf", "application/pdf"),
    ("bp", "plan.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
    ("presentation_video", "demo.mp4", "video/mp4"),
    ("presentation_video", "demo.webm", "video/webm"),
    # text_ppt and presentation_ppt with .pdf (non-pptx extension) also don't trigger conversion
    ("text_ppt", "slides.pdf", "application/pdf"),
    ("presentation_ppt", "slides.pdf", "application/pdf"),
]


def _setup_mocks_for_upload(mock_sb: MagicMock, material_type: str, file_name: str, version: int = 1):
    """Set up supabase mock chain for a successful upload flow."""
    row = _make_material_row(material_type=material_type, file_name=file_name, version=version)
    mock_upload_response = MaterialService._to_upload_response(row)

    async def mock_svc_upload(project_id, material_type, file):
        return mock_upload_response, f"proj-1/{material_type}/v{version}_{file_name}"

    return mock_svc_upload, mock_upload_response



# ── Property 2: Non-PPTX uploads do NOT call PPT conversion ─


class TestPreservation_NonPPTXUploadNoPPTConversion:
    """Property 2: Preservation - 非 PPTX 上传行为不变

    For any non-PPTX file upload (PDF, DOCX, MP4, WEBM), the upload_material
    route SHALL NOT call ppt_svc.convert_to_images() and SHALL return a
    correct MaterialUploadResponse.

    This test must PASS on unfixed code (baseline behavior to preserve).

    **Validates: Requirements 3.1, 3.2, 3.4**
    """

    @given(
        upload_idx=st.integers(min_value=0, max_value=len(_NON_PPT_UPLOADS) - 1),
    )
    @h_settings(max_examples=30, deadline=None)
    def test_non_pptx_upload_does_not_call_ppt_convert(self, upload_idx: int):
        """For any non-PPTX upload, ppt_svc.convert_to_images is never called."""
        material_type, file_name, content_type = _NON_PPT_UPLOADS[upload_idx]

        mock_sb = _mock_supabase()
        mock_svc_upload, expected_response = _setup_mocks_for_upload(
            mock_sb, material_type, file_name
        )

        fake_user = UserInfo(id="user-1", email="test@test.com", display_name="Test")
        app.dependency_overrides[get_current_user] = lambda: fake_user
        app.dependency_overrides[get_supabase] = lambda: mock_sb

        try:
            with (
                patch.object(
                    MaterialService, "upload", side_effect=mock_svc_upload
                ),
                patch.object(
                    PPTConvertService,
                    "convert_to_images",
                    side_effect=AssertionError("convert_to_images should NOT be called for non-PPTX"),
                ) as mock_convert,
                patch.object(
                    PPTConvertService,
                    "update_material_image_paths",
                    side_effect=AssertionError("update_material_image_paths should NOT be called for non-PPTX"),
                ) as mock_update,
            ):
                client = TestClient(app)
                fake_content = b"fake-file-content-" + file_name.encode()

                response = client.post(
                    "/api/projects/proj-1/materials",
                    data={"material_type": material_type},
                    files={"file": (file_name, io.BytesIO(fake_content), content_type)},
                )

                assert response.status_code == 200, (
                    f"Expected 200 for {material_type}/{file_name}, got {response.status_code}: {response.text}"
                )

                data = response.json()
                assert data["material_type"] == material_type
                assert data["file_name"] == file_name
                assert data["version"] == 1

                # PPT conversion must NOT have been called
                mock_convert.assert_not_called()
                mock_update.assert_not_called()
        finally:
            app.dependency_overrides.clear()


# ── Property 2: material_type not in _PPT_TYPES → no PPT conversion ─


# Strategy: generate material_types that are NOT in _PPT_TYPES
_ALL_MATERIAL_TYPES = ["bp", "text_ppt", "presentation_ppt", "presentation_video"]
_NON_PPT_MATERIAL_TYPES = [mt for mt in _ALL_MATERIAL_TYPES if mt not in _PPT_TYPES]

# Valid file extensions per material type (for non-PPT types)
_NON_PPT_TYPE_FILES = {
    "bp": [("plan.pdf", "application/pdf"), ("plan.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")],
    "presentation_video": [("demo.mp4", "video/mp4"), ("demo.webm", "video/webm")],
}


class TestPreservation_NonPPTMaterialTypeNoPPTConversion:
    """Property 2: Preservation - material_type not in _PPT_TYPES → no PPT conversion

    For any material_type that is NOT in _PPT_TYPES (i.e., not text_ppt or
    presentation_ppt), the PPT conversion service is never invoked regardless
    of file extension.

    **Validates: Requirements 3.1, 3.2, 3.4**
    """

    @given(
        mt_idx=st.integers(min_value=0, max_value=len(_NON_PPT_MATERIAL_TYPES) - 1),
        data=st.data(),
    )
    @h_settings(max_examples=30, deadline=None)
    def test_non_ppt_material_type_never_triggers_conversion(self, mt_idx: int, data):
        """For material_type not in _PPT_TYPES, PPT conversion is never called."""
        material_type = _NON_PPT_MATERIAL_TYPES[mt_idx]
        file_options = _NON_PPT_TYPE_FILES[material_type]
        file_idx = data.draw(st.integers(min_value=0, max_value=len(file_options) - 1))
        file_name, content_type = file_options[file_idx]

        mock_sb = _mock_supabase()
        mock_svc_upload, _ = _setup_mocks_for_upload(mock_sb, material_type, file_name)

        fake_user = UserInfo(id="user-1", email="test@test.com", display_name="Test")
        app.dependency_overrides[get_current_user] = lambda: fake_user
        app.dependency_overrides[get_supabase] = lambda: mock_sb

        try:
            with (
                patch.object(MaterialService, "upload", side_effect=mock_svc_upload),
                patch.object(
                    PPTConvertService, "convert_to_images",
                ) as mock_convert,
                patch.object(
                    PPTConvertService, "update_material_image_paths",
                ) as mock_update,
            ):
                client = TestClient(app)
                response = client.post(
                    "/api/projects/proj-1/materials",
                    data={"material_type": material_type},
                    files={"file": (file_name, io.BytesIO(b"content"), content_type)},
                )

                assert response.status_code == 200
                mock_convert.assert_not_called()
                mock_update.assert_not_called()
        finally:
            app.dependency_overrides.clear()


# ── Property 2: Version management (is_latest flag switching) ─


class TestPreservation_VersionManagement:
    """Property 2: Preservation - 材料版本管理 is_latest 标记切换行为一致

    For any sequence of uploads for the same project and material_type,
    the version management logic (is_latest flag switching) must work
    consistently: only the latest version has is_latest=True.

    This tests the MaterialService directly (not the route) to verify
    the core version management logic is preserved.

    **Validates: Requirements 3.2, 3.4**
    """

    @given(
        num_uploads=st.integers(min_value=1, max_value=5),
        material_type=st.sampled_from(["bp", "presentation_video"]),
    )
    @h_settings(max_examples=30, deadline=None)
    @pytest.mark.asyncio
    async def test_version_management_is_latest_consistency(
        self, num_uploads: int, material_type: str
    ):
        """After N uploads, exactly one record has is_latest=True (the latest)."""
        project_id = "proj-preservation"
        db_records: list[dict] = []

        ext = ".pdf" if material_type == "bp" else ".mp4"

        sb = _mock_supabase()
        # Setup storage mock
        bucket = MagicMock()
        sb.storage.from_.return_value = bucket

        call_counter = {"n": 0}

        def table_side_effect(name):
            chain = MagicMock()
            for m in ("insert", "select", "update", "delete",
                       "eq", "order", "limit", "maybe_single"):
                getattr(chain, m).return_value = chain

            call_counter["n"] += 1
            phase = (call_counter["n"] - 1) % 3

            if phase == 0:
                # _next_version: return current max version
                sorted_recs = sorted(db_records, key=lambda r: r["version"], reverse=True)
                chain.execute.return_value = MagicMock(data=sorted_recs[:1])
            elif phase == 1:
                # update old is_latest → False
                for r in db_records:
                    if r["is_latest"]:
                        r["is_latest"] = False
                chain.execute.return_value = MagicMock(data=[])
            else:
                # insert new record
                next_ver = len(db_records) + 1
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

        from fastapi import UploadFile
        for i in range(num_uploads):
            file = UploadFile(
                filename=f"file_v{i+1}{ext}",
                file=io.BytesIO(b"x" * 100),
                headers={"content-type": "application/octet-stream"},
            )
            result, storage_path = await svc.upload(project_id, material_type, file)
            assert result.version == i + 1

        # Verify: exactly N records
        assert len(db_records) == num_uploads

        # Verify: exactly one is_latest=True (the latest version)
        latest_records = [r for r in db_records if r["is_latest"]]
        assert len(latest_records) == 1, (
            f"Expected exactly 1 is_latest=True record, got {len(latest_records)}"
        )
        assert latest_records[0]["version"] == num_uploads

        # Verify: all other records have is_latest=False
        old_records = [r for r in db_records if not r["is_latest"]]
        assert len(old_records) == num_uploads - 1
