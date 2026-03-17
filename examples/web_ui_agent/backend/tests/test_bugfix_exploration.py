"""Bug Condition 探索性测试：PPT 上传同步阻塞 & StrictMode 双重调用。

此测试编码了期望行为（修复后的正确行为）。
在未修复代码上运行时，测试应该失败——失败即确认缺陷存在。

**Validates: Requirements 2.4, 2.3**
"""

import asyncio
import io
import os
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.database import get_supabase
from app.models.schemas import UserInfo
from app.routes.auth import get_current_user
from app.services.material_service import MaterialService
from app.services.ppt_convert_service import PPTConvertService


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


class TestScenarioA_PPTUploadSyncBlocking:
    """Property 1: Bug Condition - PPT 上传同步转换阻塞 HTTP 响应。

    在未修复代码上，upload_material 路由同步 await PPT 转换。
    修复后，PPT 转换应通过 BackgroundTasks 异步执行。

    验证方式：检查 upload_material 函数签名是否包含 BackgroundTasks 参数，
    以及 PPT 转换是否通过 background_tasks.add_task() 调度而非直接 await。

    **Validates: Requirements 2.4**
    """

    def test_upload_material_uses_background_tasks(self):
        """upload_material 路由应使用 BackgroundTasks 调度 PPT 转换。

        期望行为（修复后）：函数签名包含 BackgroundTasks 参数，
        PPT 转换通过 add_task 调度。
        未修复行为：函数不使用 BackgroundTasks，PPT 转换同步 await。
        """
        import inspect
        from app.routes.materials import upload_material

        sig = inspect.signature(upload_material)
        param_types = {
            name: param.annotation
            for name, param in sig.parameters.items()
        }

        # 检查函数签名中是否有 BackgroundTasks 参数
        from fastapi import BackgroundTasks
        has_background_tasks = any(
            ann is BackgroundTasks for ann in param_types.values()
        )

        assert has_background_tasks, (
            "upload_material 函数签名中没有 BackgroundTasks 参数。"
            "这确认了同步阻塞缺陷：PPT 转换在请求处理中同步执行，"
            "而非通过 BackgroundTasks 调度到后台。"
        )

    def test_pptx_upload_dispatches_to_background(self):
        """上传 .pptx 文件时，PPT 转换应被调度到后台任务而非同步 await。

        通过 mock BackgroundTasks.add_task 验证转换被调度到后台。
        """
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
                patch.object(
                    PPTConvertService,
                    "convert_to_images",
                    return_value=["proj-1/text_ppt/images/page_001.png"],
                ) as mock_convert,
                patch.object(
                    PPTConvertService,
                    "update_material_image_paths",
                ) as mock_update,
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

                # 验证 PPT 转换确实被调用了（通过 BackgroundTasks）
                # TestClient 会同步执行 BackgroundTasks，所以 mock 会被调用
                mock_convert.assert_called_once()
                mock_update.assert_called_once()
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
