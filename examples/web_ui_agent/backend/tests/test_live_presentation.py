"""现场路演服务属性测试。

测试路演交互模式指令差异性等属性。
Feature: competition-judge-system
"""

from pathlib import Path

import pytest
from hypothesis import given, settings, assume, HealthCheck
import hypothesis.strategies as st

from app.services.prompt_service import PromptService


# ── Strategies ────────────────────────────────────────────────


def _unique_prefixed_text(prefix: str) -> st.SearchStrategy[str]:
    """生成带唯一前缀的非空文本，避免与模板标记冲突。"""
    return (
        st.text(
            min_size=1,
            max_size=50,
            alphabet=st.characters(whitelist_categories=("L", "N")),
        )
        .filter(lambda s: s.strip())
        .map(lambda s: f"{prefix}_{s}")
    )


# ── Fixtures ──────────────────────────────────────────────────


@pytest.fixture()
def pbt_prompt_dir(tmp_path: Path) -> Path:
    """为属性测试创建临时prompt目录，包含多种风格和模板。"""
    styles_dir = tmp_path / "styles"
    styles_dir.mkdir()
    templates_dir = tmp_path / "templates"
    templates_dir.mkdir()

    # 创建三种风格文件
    (styles_dir / "strict.md").write_text(
        "---\nname: 严厉型\ndescription: 言辞犀利\n---\n你是严厉评委，直言不讳。",
        encoding="utf-8",
    )
    (styles_dir / "gentle.md").write_text(
        "---\nname: 温和型\ndescription: 鼓励为主\n---\n你是温和评委，循循善诱。",
        encoding="utf-8",
    )
    (styles_dir / "academic.md").write_text(
        "---\nname: 学术型\ndescription: 注重逻辑\n---\n你是学术评委，数据导向。",
        encoding="utf-8",
    )

    # 创建模板文件（含 OUTPUT_FORMAT 标记）
    for tpl_name in ("text_review", "live_presentation", "offline_review"):
        (templates_dir / f"{tpl_name}.md").write_text(
            f"# {tpl_name}\n\n流程说明\n\n<!-- OUTPUT_FORMAT -->\n\n## 输出格式要求\n\n请按格式输出。",
            encoding="utf-8",
        )

    return tmp_path


# ── Property 12: 路演交互模式指令差异性 ──────────────────────


class TestProperty12InteractionModeInstructionDifferentiation:
    """Property 12: 路演交互模式指令差异性

    对于任意交互模式切换，提问模式下的AI指令应包含"提问"相关指示词，
    建议模式下的AI指令应包含"建议"相关指示词，且两种模式的指令内容不同。

    Feature: competition-judge-system, Property 12: 路演交互模式指令差异性
    Validates: Requirements 7.2, 7.3
    """

    @given(
        rules_suffix=_unique_prefixed_text("RULES"),
        knowledge_suffix=_unique_prefixed_text("KNOWLEDGE"),
        material_suffix=_unique_prefixed_text("MATERIAL"),
        style_id=st.sampled_from(["strict", "gentle", "academic"]),
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_different_modes_produce_different_instructions(
        self,
        pbt_prompt_dir: Path,
        rules_suffix: str,
        knowledge_suffix: str,
        material_suffix: str,
        style_id: str,
    ):
        """**Validates: Requirements 7.2, 7.3**

        提问模式和建议模式应产生包含不同交互指令的prompt。
        """
        # Ensure content strings don't collide
        assume(rules_suffix != knowledge_suffix)
        assume(rules_suffix != material_suffix)
        assume(knowledge_suffix != material_suffix)

        svc = PromptService(prompts_base=pbt_prompt_dir)

        prompt_question = svc.assemble_prompt(
            template_name="live_presentation",
            style_id=style_id,
            rules_content=rules_suffix,
            knowledge_content=knowledge_suffix,
            material_content=material_suffix,
            interaction_mode="question",
        )

        prompt_suggestion = svc.assemble_prompt(
            template_name="live_presentation",
            style_id=style_id,
            rules_content=rules_suffix,
            knowledge_content=knowledge_suffix,
            material_content=material_suffix,
            interaction_mode="suggestion",
        )

        # Requirement 7.2: 提问模式应包含"提问"相关指示词
        assert "提问模式" in prompt_question, (
            "question模式的prompt应包含'提问模式'指示词"
        )

        # Requirement 7.3: 建议模式应包含"建议"相关指示词
        assert "建议模式" in prompt_suggestion, (
            "suggestion模式的prompt应包含'建议模式'指示词"
        )

        # 两种模式的指令不应交叉出现
        assert "建议模式" not in prompt_question, (
            "question模式不应包含'建议模式'指示词"
        )
        assert "提问模式" not in prompt_suggestion, (
            "suggestion模式不应包含'提问模式'指示词"
        )

        # 两种模式的完整prompt应不同
        assert prompt_question != prompt_suggestion, (
            "提问模式和建议模式的完整prompt应不同"
        )
