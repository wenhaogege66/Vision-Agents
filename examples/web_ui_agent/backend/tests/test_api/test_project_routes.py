"""项目管理路由集成测试。"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timezone

from app.main import app
from app.models.database import get_supabase
from app.models.schemas import ProjectResponse, UserInfo
from app.routes.auth import get_current_user
from app.routes.projects import _get_project_service
from app.services.project_service import ProjectService


_FAKE_USER = UserInfo(id="user-1", email="test@example.com", display_name="测试用户")

_FAKE_PROJECT = ProjectResponse(
    id="proj-1",
    name="测试项目",
    competition="guochuangsai",
    track="gaojiao",
    group="benke_chuangyi",
    current_stage="school_text",
    materials_status={
        "bp": False,
        "text_ppt": False,
        "presentation_ppt": False,
        "presentation_video": False,
    },
    created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
)


@pytest.fixture
def mock_svc():
    """Create a mock ProjectService."""
    svc = MagicMock(spec=ProjectService)
    svc.create = AsyncMock(return_value=_FAKE_PROJECT)
    svc.list_projects = AsyncMock(return_value=[_FAKE_PROJECT])
    svc.get_project = AsyncMock(return_value=_FAKE_PROJECT)
    svc.update_project = AsyncMock(return_value=_FAKE_PROJECT)
    return svc


@pytest.fixture
def client(mock_svc):
    """Create test client with dependency overrides for auth and project service."""
    app.dependency_overrides[get_current_user] = lambda: _FAKE_USER
    app.dependency_overrides[_get_project_service] = lambda: mock_svc
    yield TestClient(app)
    app.dependency_overrides.clear()


class TestCreateProject:
    def test_create_success(self, client: TestClient, mock_svc: MagicMock):
        resp = client.post(
            "/api/projects",
            json={
                "name": "测试项目",
                "competition": "guochuangsai",
                "track": "gaojiao",
                "group": "benke_chuangyi",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "proj-1"
        assert data["name"] == "测试项目"
        assert data["materials_status"]["bp"] is False
        mock_svc.create.assert_called_once()

    def test_create_missing_field_422(self, client: TestClient):
        resp = client.post(
            "/api/projects",
            json={"name": "测试项目"},
        )
        assert resp.status_code == 422


class TestListProjects:
    def test_list_success(self, client: TestClient, mock_svc: MagicMock):
        resp = client.get("/api/projects")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["id"] == "proj-1"
        mock_svc.list_projects.assert_called_once_with("user-1")


class TestGetProject:
    def test_get_success(self, client: TestClient, mock_svc: MagicMock):
        resp = client.get("/api/projects/proj-1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "proj-1"
        mock_svc.get_project.assert_called_once_with("proj-1", "user-1")


class TestUpdateProject:
    def test_update_success(self, client: TestClient, mock_svc: MagicMock):
        resp = client.put(
            "/api/projects/proj-1",
            json={"name": "新名称"},
        )
        assert resp.status_code == 200
        mock_svc.update_project.assert_called_once()

    def test_update_empty_body(self, client: TestClient, mock_svc: MagicMock):
        resp = client.put("/api/projects/proj-1", json={})
        assert resp.status_code == 200
