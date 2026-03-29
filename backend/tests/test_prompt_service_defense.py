"""Unit tests for PromptService.load_defense_template."""

import logging
from pathlib import Path

import pytest

from app.services.prompt_service import PromptService


@pytest.fixture()
def tmp_prompts(tmp_path: Path) -> Path:
    """Create a temporary prompts directory structure."""
    templates_dir = tmp_path / "templates" / "defense"
    templates_dir.mkdir(parents=True)
    return tmp_path


@pytest.fixture()
def svc(tmp_prompts: Path) -> PromptService:
    return PromptService(prompts_base=tmp_prompts)


class TestLoadDefenseTemplate:
    """Tests for load_defense_template method."""

    def test_loads_existing_file(self, svc: PromptService, tmp_prompts: Path) -> None:
        defense_dir = tmp_prompts / "templates" / "defense"
        defense_dir.joinpath("question_gen.md").write_text("custom prompt", encoding="utf-8")

        result = svc.load_defense_template("question_gen")
        assert result == "custom prompt"

    def test_fallback_question_gen(self, svc: PromptService) -> None:
        result = svc.load_defense_template("question_gen")
        assert "创业大赛评委" in result
        assert "JSON" in result

    def test_fallback_feedback_gen(self, svc: PromptService) -> None:
        result = svc.load_defense_template("feedback_gen")
        assert "创业大赛评委" in result
        assert "20-60" in result

    def test_fallback_question_speech(self, svc: PromptService) -> None:
        result = svc.load_defense_template("question_speech")
        assert "{{project_name}}" in result
        assert "{{question_count}}" in result
        assert "{{questions_text}}" in result

    def test_unknown_name_returns_empty(self, svc: PromptService) -> None:
        result = svc.load_defense_template("nonexistent_template")
        assert result == ""

    def test_logs_warning_on_fallback(
        self, svc: PromptService, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level(logging.WARNING):
            svc.load_defense_template("question_gen")
        assert any("硬编码默认值" in r.message for r in caplog.records)

    def test_no_warning_when_file_exists(
        self, svc: PromptService, tmp_prompts: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        defense_dir = tmp_prompts / "templates" / "defense"
        defense_dir.joinpath("question_gen.md").write_text("content", encoding="utf-8")

        with caplog.at_level(logging.WARNING):
            svc.load_defense_template("question_gen")
        assert not any("硬编码默认值" in r.message for r in caplog.records)

    def test_runtime_reload(self, svc: PromptService, tmp_prompts: Path) -> None:
        """File edits are picked up on next call (no caching)."""
        defense_dir = tmp_prompts / "templates" / "defense"
        f = defense_dir / "feedback_gen.md"
        f.write_text("version1", encoding="utf-8")
        assert svc.load_defense_template("feedback_gen") == "version1"

        f.write_text("version2", encoding="utf-8")
        assert svc.load_defense_template("feedback_gen") == "version2"
