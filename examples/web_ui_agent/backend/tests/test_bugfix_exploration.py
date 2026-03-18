"""Bug Condition 探索性测试：PPT 上传同步阻塞 & StrictMode 双重调用。

此测试编码了期望行为（修复后的正确行为）。
在未修复代码上运行时，测试应该失败——失败即确认缺陷存在。

**Validates: Requirements 2.4, 2.3**
"""

import io
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.database import get_supabase
from app.models.schemas import UserInfo
from app.routes.auth import get_current_user
from app.services.material_service import MaterialService


# ── Helpers ──────────────────────────────────────────────────


def _mock_supabase() -> MagicMock:
    sb = MagicMock()
    return sb


def _make_material_row() -> dict:
    return {
        "id": "mat-test-1",
        "project_id": "proj-1",
        "material_type": "text_ppt",
        "file_path": "proj-1/text_ppt/v1_abc12345.pptx",
        "file_name": "slides.pptx",
        "file_size": 1024,
        "version": 1,
        "is_latest": True,
        "image_paths": None,
        "created_at": "2025-01-01T00:00:00+00:00",
    }


# ── Scenario A: PPT 上传同步阻塞测试 ────────────────────────


class TestScenarioA_PPTUploadSimple:
    """Property 1: PPT 上传不再触发转换。

    PPT 转换已被移除，文件直接以 base64 发送给 DashScope API。
    上传应直接返回成功，无需 BackgroundTasks。

    **Validates: Requirements 2.4**
    """

    def test_upload_material_no_background_tasks_needed(self):
        """upload_material 路由不再需要 BackgroundTasks（PPT 转换已移除）。"""
        import inspect
        from app.routes.materials import upload_material

        sig = inspect.signature(upload_material)
        param_types = {
            name: param.annotation
            for name, param in sig.parameters.items()
        }

        from fastapi import BackgroundTasks
        has_background_tasks = any(
            ann is BackgroundTasks for ann in param_types.values()
        )

        # PPT conversion removed — BackgroundTasks no longer needed
        assert not has_background_tasks, (
            "upload_material 不应再包含 BackgroundTasks 参数，"
            "PPT 转换已被移除。"
        )

    def test_pptx_upload_returns_success(self):
        """上传 .pptx 文件时应直接返回成功。"""
        mock_sb = _mock_supabase()
        row = _make_material_row()

        mock_upload_response = MaterialService._to_upload_response(row)

        async def mock_svc_upload(project_id, material_type, file):
            return mock_upload_response, "proj-1/text_ppt/v1_abc12345.pptx"

        fake_user = UserInfo(id="user-1", email="test@test.com", display_name="Test")

        app.dependency_overrides[get_current_user] = lambda: fake_user
        app.dependency_overrides[get_supabase] = lambda: mock_sb

        try:
            with (
                patch.object(
                    MaterialService, "upload", side_effect=mock_svc_upload
                ),
            ):
                client = TestClient(app)

                fake_pptx_content = b"PK\x03\x04" + b"\x00" * 100

                response = client.post(
                    "/api/projects/proj-1/materials",
                    data={"material_type": "text_ppt"},
                    files={"file": ("slides.pptx", io.BytesIO(fake_pptx_content), "application/vnd.openxmlformats-officedocument.presentationml.presentation")},
                )

                assert response.status_code == 200, (
                    f"Expected 200, got {response.status_code}: {response.text}"
                )
        finally:
            app.dependency_overrides.clear()


# ── Scenario B: StrictMode 双重调用测试 ──────────────────────


class TestScenarioB_StrictModePresence:
    """Property 1: Bug Condition - StrictMode 导致 API 双重调用。

    验证 main.tsx 中 StrictMode 已被移除。
    在未修复代码上，StrictMode 仍然存在，此测试将失败。

    **Validates: Requirements 2.3**
    """

    def test_main_tsx_should_not_contain_strict_mode(self):
        """main.tsx 不应包含 <StrictMode>。

        期望行为（修复后）：StrictMode 已被移除，useEffect 不再双重执行。
        未修复行为：StrictMode 仍然存在，开发模式下 useEffect 双重执行。
        """
        # Locate main.tsx relative to the backend directory
        main_tsx_path = Path(__file__).resolve().parent.parent.parent / "frontend" / "src" / "main.tsx"

        assert main_tsx_path.exists(), (
            f"main.tsx not found at {main_tsx_path}"
        )

        content = main_tsx_path.read_text(encoding="utf-8")

        # EXPECTED BEHAVIOR (after fix): StrictMode is removed
        # ON UNFIXED CODE: This assertion FAILS because <StrictMode> is present
        assert "<StrictMode>" not in content, (
            "main.tsx still contains <StrictMode>. "
            "This confirms the StrictMode bug: React development mode will "
            "double-execute useEffect hooks, causing duplicate API calls."
        )
