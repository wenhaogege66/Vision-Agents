"""RuleService 单元测试。

验证赛事/赛道/组别列表查询、规则文件加载和解析功能。
"""

import textwrap
from pathlib import Path

import pytest

from app.models.schemas import (
    CompetitionInfo,
    EvaluationDimension,
    EvaluationRules,
    GroupInfo,
    TrackInfo,
)
from app.services.rule_service import (
    COMPETITION_NAMES,
    GROUP_NAMES,
    TRACK_NAMES,
    RuleService,
    _extract_sub_items,
    _parse_dimensions,
)


# ── Fixtures ─────────────────────────────────────────────────


@pytest.fixture
def tmp_rules(tmp_path: Path) -> Path:
    """创建临时规则目录结构用于测试"""
    # guochuangsai/gaojiao/benke_chuangyi/rules.md
    group_dir = tmp_path / "guochuangsai" / "gaojiao" / "benke_chuangyi"
    group_dir.mkdir(parents=True)
    rules_md = group_dir / "rules.md"
    rules_md.write_text(
        textwrap.dedent("""\
        # 高教主赛道 - 本科创意组评审规则

        ## 个人成长（30分）

        - 立德树人
        - 调研深入

        ## 项目创新（30分）

        - 技术创新
        - 模式创新

        ## 产业价值（25分）

        - 市场前景
        - 商业可行性

        ## 团队协作（15分）

        - 团队构成
        - 分工协作
        """),
        encoding="utf-8",
    )

    # guochuangsai/gaojiao/benke_chuangye/ (空目录，无规则文件)
    (tmp_path / "guochuangsai" / "gaojiao" / "benke_chuangye").mkdir(parents=True)

    # guochuangsai/honglv/gongyi/rules.md
    gongyi_dir = tmp_path / "guochuangsai" / "honglv" / "gongyi"
    gongyi_dir.mkdir(parents=True)
    (gongyi_dir / "rules.md").write_text(
        textwrap.dedent("""\
        # 红旅赛道 - 公益组评审规则

        ## 个人成长（30分）

        - 立德树人

        ## 公益价值（10分）

        - 社会影响力

        ## 项目创新（20分）

        - 技术创新

        ## 发展前景（20分）

        - 可持续性

        ## 团队协作（20分）

        - 团队构成
        """),
        encoding="utf-8",
    )

    # datiao/ (空赛事目录)
    (tmp_path / "datiao").mkdir()

    return tmp_path


@pytest.fixture
def svc(tmp_rules: Path) -> RuleService:
    """创建使用临时目录的 RuleService 实例"""
    return RuleService(rules_base=tmp_rules)


# ── list_competitions 测试 ────────────────────────────────────


class TestListCompetitions:
    def test_returns_existing_competitions(self, svc: RuleService):
        """应返回 rules/ 下的所有赛事目录"""
        result = svc.list_competitions()
        ids = [c.id for c in result]
        assert "guochuangsai" in ids
        assert "datiao" in ids

    def test_returns_competition_info_type(self, svc: RuleService):
        """返回值应为 CompetitionInfo 列表"""
        result = svc.list_competitions()
        assert all(isinstance(c, CompetitionInfo) for c in result)

    def test_competition_names_mapped(self, svc: RuleService):
        """赛事名称应从映射字典获取"""
        result = svc.list_competitions()
        for c in result:
            if c.id in COMPETITION_NAMES:
                assert c.name == COMPETITION_NAMES[c.id]

    def test_empty_rules_dir(self, tmp_path: Path):
        """空的 rules 目录应返回空列表"""
        svc = RuleService(rules_base=tmp_path)
        assert svc.list_competitions() == []


# ── list_tracks 测试 ──────────────────────────────────────────


class TestListTracks:
    def test_returns_tracks_for_competition(self, svc: RuleService):
        """应返回赛事下的所有赛道"""
        result = svc.list_tracks("guochuangsai")
        ids = [t.id for t in result]
        assert "gaojiao" in ids
        assert "honglv" in ids

    def test_returns_track_info_type(self, svc: RuleService):
        result = svc.list_tracks("guochuangsai")
        assert all(isinstance(t, TrackInfo) for t in result)

    def test_nonexistent_competition_returns_empty(self, svc: RuleService):
        """不存在的赛事应返回空列表"""
        assert svc.list_tracks("nonexistent") == []

    def test_empty_competition_returns_empty(self, svc: RuleService):
        """空赛事目录应返回空列表"""
        assert svc.list_tracks("datiao") == []


# ── list_groups 测试 ──────────────────────────────────────────


class TestListGroups:
    def test_returns_groups_for_track(self, svc: RuleService):
        """应返回赛道下的所有组别"""
        result = svc.list_groups("guochuangsai", "gaojiao")
        ids = [g.id for g in result]
        assert "benke_chuangyi" in ids
        assert "benke_chuangye" in ids

    def test_returns_group_info_type(self, svc: RuleService):
        result = svc.list_groups("guochuangsai", "gaojiao")
        assert all(isinstance(g, GroupInfo) for g in result)

    def test_has_rules_flag(self, svc: RuleService):
        """has_rules 标志应正确反映规则文件是否存在"""
        result = svc.list_groups("guochuangsai", "gaojiao")
        groups = {g.id: g for g in result}
        assert groups["benke_chuangyi"].has_rules is True
        assert groups["benke_chuangye"].has_rules is False

    def test_nonexistent_track_returns_empty(self, svc: RuleService):
        assert svc.list_groups("guochuangsai", "nonexistent") == []


# ── has_rules 测试 ────────────────────────────────────────────


class TestHasRules:
    def test_existing_rules(self, svc: RuleService):
        assert svc.has_rules("guochuangsai", "gaojiao", "benke_chuangyi") is True

    def test_missing_rules(self, svc: RuleService):
        assert svc.has_rules("guochuangsai", "gaojiao", "benke_chuangye") is False

    def test_nonexistent_path(self, svc: RuleService):
        assert svc.has_rules("nonexistent", "x", "y") is False


# ── load_rules 测试 ───────────────────────────────────────────


class TestLoadRules:
    def test_load_existing_rules(self, svc: RuleService):
        """应成功加载并解析规则文件"""
        rules = svc.load_rules("guochuangsai", "gaojiao", "benke_chuangyi")
        assert isinstance(rules, EvaluationRules)
        assert rules.competition == "guochuangsai"
        assert rules.track == "gaojiao"
        assert rules.group == "benke_chuangyi"

    def test_dimensions_parsed(self, svc: RuleService):
        """应正确解析评审维度"""
        rules = svc.load_rules("guochuangsai", "gaojiao", "benke_chuangyi")
        assert len(rules.dimensions) == 4
        dim_names = [d.name for d in rules.dimensions]
        assert "个人成长" in dim_names
        assert "项目创新" in dim_names
        assert "产业价值" in dim_names
        assert "团队协作" in dim_names

    def test_dimension_scores(self, svc: RuleService):
        """维度分值应正确解析"""
        rules = svc.load_rules("guochuangsai", "gaojiao", "benke_chuangyi")
        scores = {d.name: d.max_score for d in rules.dimensions}
        assert scores["个人成长"] == 30.0
        assert scores["项目创新"] == 30.0
        assert scores["产业价值"] == 25.0
        assert scores["团队协作"] == 15.0

    def test_dimension_scores_sum_to_100(self, svc: RuleService):
        """所有维度满分之和应为100"""
        rules = svc.load_rules("guochuangsai", "gaojiao", "benke_chuangyi")
        total = sum(d.max_score for d in rules.dimensions)
        assert total == 100.0

    def test_sub_items_parsed(self, svc: RuleService):
        """子项应被正确解析"""
        rules = svc.load_rules("guochuangsai", "gaojiao", "benke_chuangyi")
        growth = next(d for d in rules.dimensions if d.name == "个人成长")
        assert "立德树人" in growth.sub_items
        assert "调研深入" in growth.sub_items

    def test_raw_content_preserved(self, svc: RuleService):
        """原始内容应被保留"""
        rules = svc.load_rules("guochuangsai", "gaojiao", "benke_chuangyi")
        assert "个人成长" in rules.raw_content
        assert len(rules.raw_content) > 0

    def test_load_missing_rules_raises(self, svc: RuleService):
        """加载不存在的规则应抛出 FileNotFoundError"""
        with pytest.raises(FileNotFoundError):
            svc.load_rules("guochuangsai", "gaojiao", "benke_chuangye")

    def test_load_nonexistent_path_raises(self, svc: RuleService):
        with pytest.raises(FileNotFoundError):
            svc.load_rules("nonexistent", "x", "y")

    def test_honglv_gongyi_rules(self, svc: RuleService):
        """红旅赛道公益组规则应有5个维度，总分100"""
        rules = svc.load_rules("guochuangsai", "honglv", "gongyi")
        assert len(rules.dimensions) == 5
        total = sum(d.max_score for d in rules.dimensions)
        assert total == 100.0


# ── 解析辅助函数测试 ─────────────────────────────────────────


class TestParseDimensions:
    def test_heading_format(self):
        """Markdown 标题格式解析"""
        content = textwrap.dedent("""\
        ## 创新能力（40分）
        - 技术创新
        - 模式创新
        ## 团队协作（60分）
        - 分工合理
        """)
        dims = _parse_dimensions(content)
        assert len(dims) == 2
        assert dims[0].name == "创新能力"
        assert dims[0].max_score == 40.0
        assert dims[1].name == "团队协作"
        assert dims[1].max_score == 60.0

    def test_table_format(self):
        """Markdown 表格格式解析"""
        content = textwrap.dedent("""\
        | 维度名称 | 分值 | 子项 |
        | --- | --- | --- |
        | 创新能力 | 50 | 技术创新、模式创新 |
        | 团队协作 | 50 | 分工合理、执行力 |
        """)
        dims = _parse_dimensions(content)
        assert len(dims) == 2
        assert dims[0].name == "创新能力"
        assert dims[0].max_score == 50.0
        assert "技术创新" in dims[0].sub_items

    def test_empty_content(self):
        """空内容应返回空列表"""
        assert _parse_dimensions("") == []


class TestExtractSubItems:
    def test_dash_items(self):
        items = _extract_sub_items("- 项目A\n- 项目B\n普通文本")
        assert items == ["项目A", "项目B"]

    def test_asterisk_items(self):
        items = _extract_sub_items("* 项目A\n* 项目B")
        assert items == ["项目A", "项目B"]

    def test_empty_section(self):
        assert _extract_sub_items("") == []
