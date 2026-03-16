"""音色管理路由集成测试。"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import app
from app.models.schemas import CustomVoiceInfo, PresetVoiceInfo, UserInfo
from app.routes.auth import get_current_user
from app.routes.voices import _get_voice_service
from app.services.voice_service import VoiceService


_FAKE_USER = UserInfo(id="user-1", email="test@example.com", display_name="测试用户")

_FAKE_PRESET = PresetVoiceInfo(
    voice="Cherry", name="芊悦", description="温柔甜美的女声", languages=["zh", "en"]
)

_FAKE_CUSTOM = CustomVoiceInfo(
    id="cv-1",
    voice="cloned-voice-abc",
    preferred_name="我的音色",
    target_model="qwen3-tts-vc-realtime-2026-01-15",
    created_at=datetime(2025, 6, 1, tzinfo=timezone.utc),
)


@pytest.fixture
def mock_svc():
    svc = MagicMock(spec=VoiceService)
    svc.list_preset_voices = MagicMock(return_value=[_FAKE_PRESET])
    svc.list_custom_voices = AsyncMock(return_value=[_FAKE_CUSTOM])
    svc.clone_voice = AsyncMock(return_value=_FAKE_CUSTOM)
    svc.delete_custom_voice = AsyncMock(return_value=None)
    return svc


@pytest.fixture
def client(mock_svc):
    app.dependency_overrides[get_current_user] = lambda: _FAKE_USER
    app.dependency_overrides[_get_voice_service] = lambda: mock_svc
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def unauth_client(mock_svc):
    """Client without auth override — only override voice service."""
    app.dependency_overrides[_get_voice_service] = lambda: mock_svc
    yield TestClient(app)
    app.dependency_overrides.clear()


class TestListPresetVoices:
    def test_returns_presets(self, client: TestClient, mock_svc: MagicMock):
        resp = client.get("/api/voices/presets")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["voice"] == "Cherry"
        mock_svc.list_preset_voices.assert_called_once()

    def test_no_auth_required(self, unauth_client: TestClient, mock_svc: MagicMock):
        resp = unauth_client.get("/api/voices/presets")
        assert resp.status_code == 200


class TestListCustomVoices:
    def test_returns_custom_voices(self, client: TestClient, mock_svc: MagicMock):
        resp = client.get("/api/voices/custom")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["id"] == "cv-1"
        assert data[0]["preferred_name"] == "我的音色"
        mock_svc.list_custom_voices.assert_called_once_with("user-1")

    def test_requires_auth(self, unauth_client: TestClient):
        resp = unauth_client.get("/api/voices/custom")
        assert resp.status_code in (401, 403)


class TestCloneVoice:
    def test_clone_success(self, client: TestClient, mock_svc: MagicMock):
        resp = client.post(
            "/api/voices/clone",
            data={"preferred_name": "我的音色"},
            files={"audio": ("test.wav", b"fake-audio-content", "audio/wav")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["voice"] == "cloned-voice-abc"
        assert data["preferred_name"] == "我的音色"
        mock_svc.clone_voice.assert_called_once()

    def test_requires_auth(self, unauth_client: TestClient):
        resp = unauth_client.post(
            "/api/voices/clone",
            data={"preferred_name": "test"},
            files={"audio": ("test.wav", b"fake", "audio/wav")},
        )
        assert resp.status_code in (401, 403)

    def test_missing_audio_422(self, client: TestClient):
        resp = client.post(
            "/api/voices/clone",
            data={"preferred_name": "test"},
        )
        assert resp.status_code == 422

    def test_missing_name_422(self, client: TestClient):
        resp = client.post(
            "/api/voices/clone",
            files={"audio": ("test.wav", b"fake", "audio/wav")},
        )
        assert resp.status_code == 422


class TestDeleteCustomVoice:
    def test_delete_success(self, client: TestClient, mock_svc: MagicMock):
        resp = client.delete("/api/voices/custom/cv-1")
        assert resp.status_code == 204
        mock_svc.delete_custom_voice.assert_called_once_with("user-1", "cv-1")

    def test_not_found(self, client: TestClient, mock_svc: MagicMock):
        mock_svc.delete_custom_voice = AsyncMock(
            side_effect=HTTPException(status_code=404, detail="音色不存在或无权删除")
        )
        resp = client.delete("/api/voices/custom/nonexistent")
        assert resp.status_code == 404

    def test_requires_auth(self, unauth_client: TestClient):
        resp = unauth_client.delete("/api/voices/custom/cv-1")
        assert resp.status_code in (401, 403)
