"""音色管理服务单元测试与属性测试。

测试 VoiceService 的预设音色查询、会话音色参数获取、音频文件验证，
以及使用 hypothesis 验证预设音色设置正确性和声音复刻音频验证属性。
"""

import pytest
from fastapi import HTTPException

from app.models.schemas import PresetVoiceInfo
from app.services.voice_service import (
    ALLOWED_AUDIO_EXTENSIONS,
    MAX_AUDIO_DURATION,
    MAX_AUDIO_SIZE,
    MIN_AUDIO_DURATION,
    PRESET_VOICE_NAMES,
    PRESET_VOICES,
    VoiceService,
    validate_audio_duration,
    validate_audio_file,
)

# ── Helpers ───────────────────────────────────────────────────


def _make_service() -> VoiceService:
    """Create a VoiceService without a real Supabase client."""
    return VoiceService(supabase_client=None)


# ── Unit Tests ────────────────────────────────────────────────


class TestListPresetVoices:
    """Unit tests for list_preset_voices."""

    def test_returns_49_voices(self):
        svc = _make_service()
        voices = svc.list_preset_voices()
        assert len(voices) == 49

    def test_returns_preset_voice_info_instances(self):
        svc = _make_service()
        voices = svc.list_preset_voices()
        for v in voices:
            assert isinstance(v, PresetVoiceInfo)
            assert v.voice
            assert v.name
            assert v.description
            assert len(v.languages) > 0


class TestGetVoiceForSession:
    """Unit tests for get_voice_for_session."""

    def test_preset_type_returns_voice_id(self):
        svc = _make_service()
        result = svc.get_voice_for_session("Cherry", "preset")
        assert result == "Cherry"

    def test_custom_type_returns_voice_id(self):
        svc = _make_service()
        result = svc.get_voice_for_session("custom-voice-abc123", "custom")
        assert result == "custom-voice-abc123"

    def test_invalid_type_raises_400(self):
        svc = _make_service()
        with pytest.raises(HTTPException) as exc_info:
            svc.get_voice_for_session("Cherry", "unknown")
        assert exc_info.value.status_code == 400

    def test_invalid_preset_voice_raises_404(self):
        svc = _make_service()
        with pytest.raises(HTTPException) as exc_info:
            svc.get_voice_for_session("NonExistentVoice", "preset")
        assert exc_info.value.status_code == 404


class TestValidateAudioFile:
    """Unit tests for validate_audio_file."""

    def test_valid_wav(self):
        ok, err = validate_audio_file("recording.wav", 1024)
        assert ok is True
        assert err == ""

    def test_valid_mp3(self):
        ok, err = validate_audio_file("recording.mp3", 5 * 1024 * 1024)
        assert ok is True
        assert err == ""

    def test_valid_m4a(self):
        ok, err = validate_audio_file("recording.m4a", 9 * 1024 * 1024)
        assert ok is True
        assert err == ""

    def test_invalid_format_txt(self):
        ok, err = validate_audio_file("notes.txt", 1024)
        assert ok is False
        assert "不支持" in err

    def test_invalid_format_ogg(self):
        ok, err = validate_audio_file("audio.ogg", 1024)
        assert ok is False

    def test_oversized_file(self):
        ok, err = validate_audio_file("big.wav", 11 * 1024 * 1024)
        assert ok is False
        assert "大小" in err

    def test_no_extension(self):
        ok, err = validate_audio_file("noext", 1024)
        assert ok is False


class TestValidateAudioDuration:
    """Unit tests for validate_audio_duration."""

    def test_valid_duration_10s(self):
        ok, err = validate_audio_duration(10.0)
        assert ok is True

    def test_valid_duration_60s(self):
        ok, err = validate_audio_duration(60.0)
        assert ok is True

    def test_valid_duration_30s(self):
        ok, err = validate_audio_duration(30.0)
        assert ok is True

    def test_too_short(self):
        ok, err = validate_audio_duration(5.0)
        assert ok is False
        assert "不足" in err

    def test_too_long(self):
        ok, err = validate_audio_duration(120.0)
        assert ok is False
        assert "过长" in err


# ── Property-Based Tests ──────────────────────────────────────

from hypothesis import given, settings as h_settings, HealthCheck
import hypothesis.strategies as st

# All 49 preset voice names
ALL_PRESET_VOICE_NAMES = [v["voice"] for v in PRESET_VOICES]

# Valid audio extensions
VALID_EXTENSIONS = [".wav", ".mp3", ".m4a"]

# Invalid audio extensions for testing
INVALID_EXTENSIONS = [
    ".txt", ".pdf", ".ogg", ".flac", ".aac", ".wma",
    ".doc", ".py", ".jpg", ".png", ".zip", ".exe",
]


class TestProperty21PresetVoiceSettingCorrectness:
    """Property 21: 预设音色设置正确性

    For any preset voice selected for a live presentation session,
    the voice parameter in session.update should match the user's selection.
    Test get_voice_for_session(voice_id, "preset") returns the same voice_id
    for all valid preset voices. Test that invalid preset voice names raise 404.

    Feature: competition-judge-system, Property 21: 预设音色设置正确性
    Validates: Requirements 14.3, 14.4, 14.9
    """

    @given(voice_name=st.sampled_from(ALL_PRESET_VOICE_NAMES))
    @h_settings(max_examples=100)
    def test_preset_voice_returns_matching_voice_id(self, voice_name: str):
        """For any valid preset voice, get_voice_for_session should return
        the exact same voice_id that was passed in."""
        svc = _make_service()
        result = svc.get_voice_for_session(voice_name, "preset")
        assert result == voice_name, (
            f"Expected voice '{voice_name}' but got '{result}'"
        )

    @given(
        invalid_name=st.text(min_size=1, max_size=30).filter(
            lambda s: s.strip() and s not in PRESET_VOICE_NAMES
        )
    )
    @h_settings(max_examples=100)
    def test_invalid_preset_voice_raises_404(self, invalid_name: str):
        """For any string that is not a valid preset voice name,
        get_voice_for_session with type 'preset' should raise HTTP 404."""
        svc = _make_service()
        with pytest.raises(HTTPException) as exc_info:
            svc.get_voice_for_session(invalid_name, "preset")
        assert exc_info.value.status_code == 404


class TestProperty22VoiceCloningAudioValidation:
    """Property 22: 声音复刻音频验证

    For any voice cloning request, validate audio format (WAV/MP3/M4A),
    file size (<10MB), and duration (10-60s). Invalid formats are rejected,
    oversized files are rejected, and duration outside 10-60s is rejected.

    Feature: competition-judge-system, Property 22: 声音复刻音频验证
    Validates: Requirements 14.4, 14.9
    """

    @given(
        basename=st.text(
            min_size=1, max_size=20,
            alphabet=st.characters(whitelist_categories=("L", "N")),
        ).filter(lambda s: s.strip()),
        ext=st.sampled_from(VALID_EXTENSIONS),
        size=st.integers(min_value=1, max_value=MAX_AUDIO_SIZE),
    )
    @h_settings(max_examples=100)
    def test_valid_format_and_size_accepted(
        self, basename: str, ext: str, size: int
    ):
        """Valid audio files (correct extension, size <= 10MB) should pass."""
        filename = f"{basename}{ext}"
        ok, err = validate_audio_file(filename, size)
        assert ok is True, f"Expected valid for '{filename}' ({size}B): {err}"
        assert err == ""

    @given(
        basename=st.text(
            min_size=1, max_size=20,
            alphabet=st.characters(whitelist_categories=("L", "N")),
        ).filter(lambda s: s.strip()),
        ext=st.sampled_from(INVALID_EXTENSIONS),
        size=st.integers(min_value=1, max_value=MAX_AUDIO_SIZE),
    )
    @h_settings(max_examples=100)
    def test_invalid_format_rejected(
        self, basename: str, ext: str, size: int
    ):
        """Files with unsupported extensions should be rejected."""
        filename = f"{basename}{ext}"
        ok, err = validate_audio_file(filename, size)
        assert ok is False, f"Expected rejection for '{filename}'"
        assert "不支持" in err

    @given(
        basename=st.text(
            min_size=1, max_size=20,
            alphabet=st.characters(whitelist_categories=("L", "N")),
        ).filter(lambda s: s.strip()),
        ext=st.sampled_from(VALID_EXTENSIONS),
        size=st.integers(min_value=MAX_AUDIO_SIZE + 1, max_value=50 * 1024 * 1024),
    )
    @h_settings(max_examples=100)
    def test_oversized_file_rejected(
        self, basename: str, ext: str, size: int
    ):
        """Files exceeding 10MB should be rejected regardless of format."""
        filename = f"{basename}{ext}"
        ok, err = validate_audio_file(filename, size)
        assert ok is False, f"Expected rejection for oversized '{filename}' ({size}B)"
        assert "大小" in err

    @given(
        duration=st.floats(
            min_value=MIN_AUDIO_DURATION,
            max_value=MAX_AUDIO_DURATION,
            allow_nan=False,
            allow_infinity=False,
        )
    )
    @h_settings(max_examples=100)
    def test_valid_duration_accepted(self, duration: float):
        """Durations within 10-60s should pass validation."""
        ok, err = validate_audio_duration(duration)
        assert ok is True, f"Expected valid for {duration}s: {err}"
        assert err == ""

    @given(
        duration=st.floats(
            min_value=0.0,
            max_value=MIN_AUDIO_DURATION,
            allow_nan=False,
            allow_infinity=False,
            exclude_max=True,
        )
    )
    @h_settings(max_examples=100)
    def test_too_short_duration_rejected(self, duration: float):
        """Durations below 10s should be rejected."""
        ok, err = validate_audio_duration(duration)
        assert ok is False, f"Expected rejection for {duration}s"
        assert "不足" in err

    @given(
        duration=st.floats(
            min_value=MAX_AUDIO_DURATION,
            max_value=600.0,
            allow_nan=False,
            allow_infinity=False,
            exclude_min=True,
        )
    )
    @h_settings(max_examples=100)
    def test_too_long_duration_rejected(self, duration: float):
        """Durations above 60s should be rejected."""
        ok, err = validate_audio_duration(duration)
        assert ok is False, f"Expected rejection for {duration}s"
        assert "过长" in err
