"""PromptService 单元测试。

测试评委风格列表、风格加载、模板加载和prompt组装功能。
"""

import textwrap
from pathlib import Path

import pytest

from app.models.schemas import JudgeStyleInfo
from app.services.prompt_service import PromptService, _parse_front_matter


# ── Fixtures ──────────────────────────────────────────────────


@pytest.fixture()
def prompt_dir(tmp_path: Path) -> Path:
    """创建临时prompt目录结构并填充测试文件。"""
    styles_dir = tmp_path / "styles"
    styles_dir.mkdir()
    templates_dir = tmp_path / "templates"
    templates_dir.mkdir()

    # 创建风格文件
    (styles_dir / "strict.md").write_text(
        "---\nname: 严厉型\ndescription: 言辞犀利\n---\n你是严厉评委。",
        encoding="utf-8",
    )
    (styles_dir / "gentle.md").write_text(
        "---\nname: 温和型\ndescription: 鼓励为主\n---\n你是温和评委。",
        encoding="utf-8",
    )
    (styles_dir / "academic.md").write_text(
        "---\nname: 学术型\ndescription: 注重逻辑\n---\n你是学术评委。",
        encoding="utf-8",
    )

    # 创建模板文件
    (templates_dir / "text_review.md").write_text(
        "# 文本评审\n\n评审流程说明\n\n<!-- OUTPUT_FORMAT -->\n\n## 输出格式要求\n\n请输出JSON。",
        encoding="utf-8",
    )
    (templates_dir / "live_presentation.md").write_text(
        "# 现场路演\n\n路演流程说明\n\n<!-- OUTPUT_FORMAT -->\n\n## 输出格式要求\n\n请按格式输出。",
        encoding="utf-8",
    )
    (templates_dir / "offline_review.md").write_text(
        "# 离线评审\n\n离线流程说明\n\n<!-- OUTPUT_FORMAT -->\n\n## 输出格式要求\n\n请输出报告。",
        encoding="utf-8",
    )

    return tmp_path


@pytest.fixture()
def svc(prompt_dir: Path) -> PromptService:
    return PromptService(prompts_base=prompt_dir)


# ── _parse_front_matter 测试 ─────────────────────────────────


class TestParseFrontMatter:
    def test_with_front_matter(self):
        content = "---\nname: 严厉型\ndescription: 犀利\n---\n正文内容"
        meta, body = _parse_front_matter(content)
        assert meta["name"] == "严厉型"
        assert meta["description"] == "犀利"
        assert body == "正文内容"

    def test_without_front_matter(self):
        content = "# 标题\n\n正文"
        meta, body = _parse_front_matter(content)
        assert meta == {}
        assert body == content

    def test_empty_content(self):
        meta, body = _parse_front_matter("")
        assert meta == {}
        assert body == ""


# ── list_styles 测试 ─────────────────────────────────────────


class TestListStyles:
    def test_returns_all_styles(self, svc: PromptService):
        styles = svc.list_styles()
        assert len(styles) == 3
        ids = {s.id for s in styles}
        assert ids == {"strict", "gentle", "academic"}

    def test_style_metadata(self, svc: PromptService):
        styles = svc.list_styles()
        strict = next(s for s in styles if s.id == "strict")
        assert strict.name == "严厉型"
        assert strict.description == "言辞犀利"

    def test_returns_judge_style_info(self, svc: PromptService):
        styles = svc.list_styles()
        for s in styles:
            assert isinstance(s, JudgeStyleInfo)

    def test_empty_dir(self, tmp_path: Path):
        (tmp_path / "styles").mkdir()
        svc = PromptService(prompts_base=tmp_path)
        assert svc.list_styles() == []

    def test_missing_dir(self, tmp_path: Path):
        svc = PromptService(prompts_base=tmp_path)
        assert svc.list_styles() == []

    def test_ignores_non_md_files(self, prompt_dir: Path):
        (prompt_dir / "styles" / "notes.txt").write_text("not a style")
        svc = PromptService(prompts_base=prompt_dir)
        styles = svc.list_styles()
        ids = {s.id for s in styles}
        assert "notes" not in ids


# ── load_style 测试 ──────────────────────────────────────────


class TestLoadStyle:
    def test_load_existing_style(self, svc: PromptService):
        content = svc.load_style("strict")
        assert "严厉评委" in content
        # Should not contain front-matter
        assert "---" not in content

    def test_load_missing_style_raises(self, svc: PromptService):
        with pytest.raises(FileNotFoundError, match="评委风格文件不存在"):
            svc.load_style("nonexistent")


# ── load_template 测试 ───────────────────────────────────────


class TestLoadTemplate:
    def test_load_existing_template(self, svc: PromptService):
        content = svc.load_template("text_review")
        assert "文本评审" in content
        assert "OUTPUT_FORMAT" in content

    def test_load_missing_template_raises(self, svc: PromptService):
        with pytest.raises(FileNotFoundError, match="Prompt模板文件不存在"):
            svc.load_template("nonexistent")


# ── assemble_prompt 测试 ─────────────────────────────────────


class TestAssemblePrompt:
    def test_basic_assembly_order(self, svc: PromptService):
        """验证组装顺序：角色描述 → 评审规则 → 知识库 → 材料 → 输出格式"""
        prompt = svc.assemble_prompt(
            template_name="text_review",
            style_id="strict",
            rules_content="这是评审规则",
            knowledge_content="这是知识库",
            material_content="这是材料内容",
        )

        # All sections present
        assert "严厉评委" in prompt
        assert "评审规则" in prompt
        assert "知识库" in prompt
        assert "材料内容" in prompt
        assert "输出格式要求" in prompt

        # Verify order
        idx_style = prompt.index("严厉评委")
        idx_rules = prompt.index("这是评审规则")
        idx_knowledge = prompt.index("这是知识库")
        idx_material = prompt.index("这是材料内容")
        idx_output = prompt.index("输出格式要求")

        assert idx_style < idx_rules < idx_knowledge < idx_material < idx_output

    def test_with_interaction_mode_question(self, svc: PromptService):
        """验证提问模式指令插入"""
        prompt = svc.assemble_prompt(
            template_name="live_presentation",
            style_id="gentle",
            rules_content="规则",
            knowledge_content="知识",
            material_content="材料",
            interaction_mode="question",
        )
        assert "提问模式" in prompt
        assert "建议模式" not in prompt

    def test_with_interaction_mode_suggestion(self, svc: PromptService):
        """验证建议模式指令插入"""
        prompt = svc.assemble_prompt(
            template_name="live_presentation",
            style_id="gentle",
            rules_content="规则",
            knowledge_content="知识",
            material_content="材料",
            interaction_mode="suggestion",
        )
        assert "建议模式" in prompt

    def test_interaction_mode_between_material_and_output(self, svc: PromptService):
        """验证交互模式指令在材料和输出格式之间"""
        prompt = svc.assemble_prompt(
            template_name="live_presentation",
            style_id="strict",
            rules_content="规则",
            knowledge_content="知识",
            material_content="材料",
            interaction_mode="question",
        )
        idx_material = prompt.index("材料")
        idx_mode = prompt.index("提问模式")
        idx_output = prompt.index("输出格式要求")
        assert idx_material < idx_mode < idx_output

    def test_no_interaction_mode_for_text_review(self, svc: PromptService):
        """文本评审不应包含交互模式指令"""
        prompt = svc.assemble_prompt(
            template_name="text_review",
            style_id="strict",
            rules_content="规则",
            knowledge_content="知识",
            material_content="材料",
        )
        assert "提问模式" not in prompt
        assert "建议模式" not in prompt

    def test_different_styles_produce_different_prompts(self, svc: PromptService):
        """不同风格应产生不同的角色描述"""
        prompt_strict = svc.assemble_prompt(
            template_name="text_review",
            style_id="strict",
            rules_content="规则",
            knowledge_content="知识",
            material_content="材料",
        )
        prompt_gentle = svc.assemble_prompt(
            template_name="text_review",
            style_id="gentle",
            rules_content="规则",
            knowledge_content="知识",
            material_content="材料",
        )
        assert prompt_strict != prompt_gentle
        assert "严厉评委" in prompt_strict
        assert "温和评委" in prompt_gentle

    def test_empty_optional_sections(self, svc: PromptService):
        """空的可选内容不应产生多余的段落"""
        prompt = svc.assemble_prompt(
            template_name="text_review",
            style_id="strict",
            rules_content="",
            knowledge_content="",
            material_content="",
        )
        assert "严厉评委" in prompt
        assert "输出格式要求" in prompt
        # Empty sections should not add headers
        assert "## 评审规则" not in prompt
        assert "## 知识库参考" not in prompt
        assert "## 评审材料" not in prompt

    def test_missing_style_raises(self, svc: PromptService):
        with pytest.raises(FileNotFoundError):
            svc.assemble_prompt(
                template_name="text_review",
                style_id="nonexistent",
                rules_content="规则",
                knowledge_content="知识",
                material_content="材料",
            )

    def test_missing_template_raises(self, svc: PromptService):
        with pytest.raises(FileNotFoundError):
            svc.assemble_prompt(
                template_name="nonexistent",
                style_id="strict",
                rules_content="规则",
                knowledge_content="知识",
                material_content="材料",
            )


# ── 使用真实文件的集成测试 ───────────────────────────────────


class TestWithRealFiles:
    """使用项目中实际的prompt文件进行测试。"""

    def test_real_styles_exist(self):
        svc = PromptService()
        styles = svc.list_styles()
        assert len(styles) >= 3
        ids = {s.id for s in styles}
        assert {"strict", "gentle", "academic"} <= ids

    def test_real_templates_exist(self):
        svc = PromptService()
        for name in ("text_review", "live_presentation", "offline_review"):
            content = svc.load_template(name)
            assert len(content) > 0
            assert "OUTPUT_FORMAT" in content

    def test_real_assemble_prompt(self):
        svc = PromptService()
        prompt = svc.assemble_prompt(
            template_name="text_review",
            style_id="strict",
            rules_content="测试规则",
            knowledge_content="测试知识",
            material_content="测试材料",
        )
        assert "测试规则" in prompt
        assert "测试知识" in prompt
        assert "测试材料" in prompt


# ── 属性测试 (Property-Based Tests) ──────────────────────────
#
# 使用 hypothesis 验证 PromptService 的通用正确性属性。
# Feature: competition-judge-system

from hypothesis import given, settings, assume, HealthCheck
import hypothesis.strategies as st


def _nonempty_text() -> st.SearchStrategy[str]:
    """生成非空且 strip 后仍非空的文本字符串。"""
    return st.text(min_size=1, max_size=200).filter(lambda s: s.strip())


@pytest.fixture()
def pbt_prompt_dir(tmp_path: Path) -> Path:
    """为属性测试创建临时prompt目录，包含多种风格和模板。"""
    styles_dir = tmp_path / "styles"
    styles_dir.mkdir()
    templates_dir = tmp_path / "templates"
    templates_dir.mkdir()

    # 创建三种风格文件（内容不同）
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


class TestProperty5PromptAssemblyCompleteness:
    """Property 5: 评审Prompt组装完整性

    对于任意评审请求（文本评审或路演评审），构造的AI Prompt应同时包含
    评审规则内容和对应材料类型的知识库内容。

    Feature: competition-judge-system, Property 5: 评审Prompt组装完整性
    Validates: Requirements 2.8, 2.6
    """

    @given(
        rules_content=_nonempty_text(),
        knowledge_content=_nonempty_text(),
        template_name=st.sampled_from(["text_review", "live_presentation", "offline_review"]),
        style_id=st.sampled_from(["strict", "gentle", "academic"]),
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_prompt_contains_rules_and_knowledge(
        self,
        pbt_prompt_dir: Path,
        rules_content: str,
        knowledge_content: str,
        template_name: str,
        style_id: str,
    ):
        svc = PromptService(prompts_base=pbt_prompt_dir)
        prompt = svc.assemble_prompt(
            template_name=template_name,
            style_id=style_id,
            rules_content=rules_content,
            knowledge_content=knowledge_content,
            material_content="测试材料",
        )

        # 评审规则内容必须出现在最终prompt中
        assert rules_content in prompt, "组装后的prompt应包含评审规则内容"
        # 知识库内容必须出现在最终prompt中
        assert knowledge_content in prompt, "组装后的prompt应包含知识库内容"


class TestProperty18PromptAssemblyOrder:
    """Property 18: Prompt模板组装顺序正确性

    对于任意评审请求或现场路演会话，组装后的最终prompt中各片段的出现顺序
    应严格遵循：角色描述（含风格）→ 评审规则 → 知识库内容 → 材料内容 → 输出格式要求。

    Feature: competition-judge-system, Property 18: Prompt模板组装顺序正确性
    Validates: Requirements 13.6
    """

    @given(
        rules_content=_nonempty_text(),
        knowledge_content=_nonempty_text(),
        material_content=_nonempty_text(),
        template_name=st.sampled_from(["text_review", "live_presentation", "offline_review"]),
        style_id=st.sampled_from(["strict", "gentle", "academic"]),
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_section_order_is_correct(
        self,
        pbt_prompt_dir: Path,
        rules_content: str,
        knowledge_content: str,
        material_content: str,
        template_name: str,
        style_id: str,
    ):
        # Ensure no content string is a substring of another so index checks are unambiguous
        r, k, m = rules_content.strip(), knowledge_content.strip(), material_content.strip()
        assume(r != k and r != m and k != m)
        assume(r not in k and k not in r)
        assume(r not in m and m not in r)
        assume(k not in m and m not in k)

        svc = PromptService(prompts_base=pbt_prompt_dir)
        prompt = svc.assemble_prompt(
            template_name=template_name,
            style_id=style_id,
            rules_content=rules_content,
            knowledge_content=knowledge_content,
            material_content=material_content,
        )

        # Locate each section by its unique content
        # Role description is the style body loaded from file — use the section header
        idx_role = prompt.index("评委")  # all styles contain "评委"
        idx_rules = prompt.index(rules_content)
        idx_knowledge = prompt.index(knowledge_content)
        idx_material = prompt.index(material_content)
        idx_output = prompt.index("输出格式要求")

        assert idx_role < idx_rules, "角色描述应在评审规则之前"
        assert idx_rules < idx_knowledge, "评审规则应在知识库内容之前"
        assert idx_knowledge < idx_material, "知识库内容应在材料内容之前"
        assert idx_material < idx_output, "材料内容应在输出格式要求之前"


class TestProperty19StyleSwitchEffectiveness:
    """Property 19: 评委风格切换有效性

    对于任意两种不同的评委风格，使用相同的评审规则、知识库和材料内容组装prompt时，
    最终prompt中的角色描述部分应不同。

    Feature: competition-judge-system, Property 19: 评委风格切换有效性
    Validates: Requirements 13.3, 13.5
    """

    @given(
        rules_content=_nonempty_text(),
        knowledge_content=_nonempty_text(),
        material_content=_nonempty_text(),
        template_name=st.sampled_from(["text_review", "live_presentation", "offline_review"]),
        styles=st.permutations(["strict", "gentle", "academic"]).map(lambda xs: (xs[0], xs[1])),
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_different_styles_produce_different_role_descriptions(
        self,
        pbt_prompt_dir: Path,
        rules_content: str,
        knowledge_content: str,
        material_content: str,
        template_name: str,
        styles: tuple[str, str],
    ):
        style_a, style_b = styles
        svc = PromptService(prompts_base=pbt_prompt_dir)

        prompt_a = svc.assemble_prompt(
            template_name=template_name,
            style_id=style_a,
            rules_content=rules_content,
            knowledge_content=knowledge_content,
            material_content=material_content,
        )
        prompt_b = svc.assemble_prompt(
            template_name=template_name,
            style_id=style_b,
            rules_content=rules_content,
            knowledge_content=knowledge_content,
            material_content=material_content,
        )

        # Extract the role description part (everything before "## 评审规则")
        role_a = prompt_a.split("## 评审规则")[0]
        role_b = prompt_b.split("## 评审规则")[0]

        assert role_a != role_b, (
            f"风格 {style_a} 和 {style_b} 的角色描述部分应不同"
        )


class TestProperty20InteractionModeIndependence:
    """Property 20: 交互模式与评委风格独立性

    对于任意现场路演会话中的交互模式切换（提问↔建议），切换前后的prompt中
    角色描述部分和评审规则部分应保持完全一致，仅交互模式指令部分发生变化。

    Feature: competition-judge-system, Property 20: 交互模式与评委风格独立性
    Validates: Requirements 13.7
    """

    @given(
        rules_content=_nonempty_text(),
        knowledge_content=_nonempty_text(),
        material_content=_nonempty_text(),
        style_id=st.sampled_from(["strict", "gentle", "academic"]),
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_mode_switch_preserves_role_and_rules(
        self,
        pbt_prompt_dir: Path,
        rules_content: str,
        knowledge_content: str,
        material_content: str,
        style_id: str,
    ):
        svc = PromptService(prompts_base=pbt_prompt_dir)

        prompt_question = svc.assemble_prompt(
            template_name="live_presentation",
            style_id=style_id,
            rules_content=rules_content,
            knowledge_content=knowledge_content,
            material_content=material_content,
            interaction_mode="question",
        )
        prompt_suggestion = svc.assemble_prompt(
            template_name="live_presentation",
            style_id=style_id,
            rules_content=rules_content,
            knowledge_content=knowledge_content,
            material_content=material_content,
            interaction_mode="suggestion",
        )

        # Extract role description: everything before "## 评审规则"
        role_q = prompt_question.split("## 评审规则")[0]
        role_s = prompt_suggestion.split("## 评审规则")[0]
        assert role_q == role_s, "切换交互模式后角色描述部分应保持一致"

        # Extract rules section: between "## 评审规则" and "## 知识库参考"
        rules_q = prompt_question.split("## 评审规则")[1].split("## 知识库参考")[0]
        rules_s = prompt_suggestion.split("## 评审规则")[1].split("## 知识库参考")[0]
        assert rules_q == rules_s, "切换交互模式后评审规则部分应保持一致"

        # The interaction mode section should differ
        assert "提问模式" in prompt_question, "question模式的prompt应包含提问模式指令"
        assert "建议模式" in prompt_suggestion, "suggestion模式的prompt应包含建议模式指令"
        assert "建议模式" not in prompt_question, "question模式不应包含建议模式指令"
        assert "提问模式" not in prompt_suggestion, "suggestion模式不应包含提问模式指令"

        # The two prompts should be different overall
        assert prompt_question != prompt_suggestion, "两种交互模式的完整prompt应不同"
