"""KnowledgeService 单元测试。

验证知识库文件加载功能。
"""

from pathlib import Path

import pytest

from app.services.knowledge_service import KnowledgeService


@pytest.fixture
def tmp_knowledge(tmp_path: Path) -> Path:
    """创建临时知识库目录结构"""
    # bp/
    bp_dir = tmp_path / "bp"
    bp_dir.mkdir()
    (bp_dir / "tips.md").write_text("# BP评审技巧\n\n- 关注商业模式", encoding="utf-8")
    (bp_dir / "examples.md").write_text("# BP案例\n\n- 优秀案例分析", encoding="utf-8")

    # text_ppt/
    text_ppt_dir = tmp_path / "text_ppt"
    text_ppt_dir.mkdir()
    (text_ppt_dir / "guide.md").write_text("# 文本PPT评审指南", encoding="utf-8")

    # presentation_ppt/ (空目录)
    (tmp_path / "presentation_ppt").mkdir()

    # presentation/
    pres_dir = tmp_path / "presentation"
    pres_dir.mkdir()
    (pres_dir / "questions.md").write_text("# 提问模板\n\n- 核心技术是什么？", encoding="utf-8")

    return tmp_path


@pytest.fixture
def svc(tmp_knowledge: Path) -> KnowledgeService:
    return KnowledgeService(knowledge_base=tmp_knowledge)


class TestLoadKnowledge:
    def test_load_bp_knowledge(self, svc: KnowledgeService):
        """应加载bp目录下所有md文件内容"""
        content = svc.load_knowledge("bp")
        assert "BP评审技巧" in content
        assert "BP案例" in content

    def test_load_text_ppt_knowledge(self, svc: KnowledgeService):
        content = svc.load_knowledge("text_ppt")
        assert "文本PPT评审指南" in content

    def test_load_presentation_knowledge(self, svc: KnowledgeService):
        content = svc.load_knowledge("presentation")
        assert "提问模板" in content

    def test_empty_directory_returns_empty(self, svc: KnowledgeService):
        """空目录应返回空字符串"""
        content = svc.load_knowledge("presentation_ppt")
        assert content == ""

    def test_nonexistent_directory_returns_empty(self, tmp_path: Path):
        """不存在的目录应返回空字符串"""
        svc = KnowledgeService(knowledge_base=tmp_path / "nonexistent")
        content = svc.load_knowledge("bp")
        assert content == ""

    def test_invalid_material_type_raises(self, svc: KnowledgeService):
        """无效的材料类型应抛出 ValueError"""
        with pytest.raises(ValueError, match="无效的材料类型"):
            svc.load_knowledge("invalid_type")

    def test_multiple_files_concatenated(self, svc: KnowledgeService):
        """多个文件内容应被拼接"""
        content = svc.load_knowledge("bp")
        # 两个文件的内容都应存在
        assert "BP评审技巧" in content
        assert "BP案例" in content
        # 文件之间应有分隔
        assert "\n\n" in content

    def test_ignores_unsupported_formats(self, tmp_path: Path):
        """应忽略不支持的文件格式"""
        bp_dir = tmp_path / "bp"
        bp_dir.mkdir()
        (bp_dir / "notes.txt").write_text("should be ignored", encoding="utf-8")
        (bp_dir / "guide.md").write_text("# Guide", encoding="utf-8")

        svc = KnowledgeService(knowledge_base=tmp_path)
        content = svc.load_knowledge("bp")
        assert "should be ignored" not in content
        assert "Guide" in content
