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


# ── 属性测试 (Property-Based Tests) ──────────────────────────
#
# 使用 hypothesis 验证 RuleService 的通用正确性属性。
# Feature: competition-judge-system

from hypothesis import given, settings, assume
import hypothesis.strategies as st


def _dir_name_strategy() -> st.SearchStrategy[str]:
    """生成合法的目录名（小写字母+下划线，非空）"""
    return st.from_regex(r"[a-z][a-z_]{0,19}", fullmatch=True)


def _build_rules_tree(
    tmp_path: Path,
    competitions: list[tuple[str, list[tuple[str, list[str]]]]],
) -> Path:
    """辅助函数：根据结构描述创建规则目录树。

    每个有规则的组别会生成一个维度总分为100的 rules.md。
    """
    for comp, tracks in competitions:
        for track, groups in tracks:
            for group in groups:
                group_dir = tmp_path / comp / track / group
                group_dir.mkdir(parents=True, exist_ok=True)
                # 生成总分100的规则文件
                (group_dir / "rules.md").write_text(
                    textwrap.dedent(f"""\
                    # {comp}/{track}/{group} 评审规则

                    ## 维度A（40分）

                    - 子项1
                    - 子项2

                    ## 维度B（35分）

                    - 子项3

                    ## 维度C（25分）

                    - 子项4
                    """),
                    encoding="utf-8",
                )
    return tmp_path


class TestProperty1CascadeConsistency:
    """Property 1: 赛事级联选择一致性

    对于任意有效的赛事类型，查询其赛道列表应返回非空结果；
    对于任意有效的赛事+赛道组合，查询其组别列表应返回非空结果；
    对于任意有效的赛事+赛道+组别组合且存在规则文件时，加载规则应返回包含评审维度的规则对象。

    Feature: competition-judge-system, Property 1: 赛事级联选择一致性
    Validates: Requirements 1.2, 1.3, 1.4
    """

    @given(
        comp=_dir_name_strategy(),
        track=_dir_name_strategy(),
        group=_dir_name_strategy(),
    )
    @settings(max_examples=100)
    def test_cascade_selection_consistency(
        self, tmp_path_factory, comp: str, track: str, group: str
    ):
        # 确保三级名称互不相同，避免路径冲突
        assume(comp != track and track != group and comp != group)

        base = tmp_path_factory.mktemp("rules")
        _build_rules_tree(base, [(comp, [(track, [group])])])
        svc = RuleService(rules_base=base)

        # 赛事列表非空
        competitions = svc.list_competitions()
        assert len(competitions) > 0
        assert any(c.id == comp for c in competitions)

        # 赛道列表非空
        tracks = svc.list_tracks(comp)
        assert len(tracks) > 0
        assert any(t.id == track for t in tracks)

        # 组别列表非空
        groups = svc.list_groups(comp, track)
        assert len(groups) > 0
        assert any(g.id == group for g in groups)

        # 有规则的组别能成功加载，且包含评审维度
        rules = svc.load_rules(comp, track, group)
        assert len(rules.dimensions) > 0


class TestProperty2NoRulesErrorHandling:
    """Property 2: 无规则组合的错误处理

    对于任意不存在对应规则文件的赛事/赛道/组别组合，
    调用规则加载服务应返回明确的错误信息而非空结果或异常崩溃。

    Feature: competition-judge-system, Property 2: 无规则组合的错误处理
    Validates: Requirements 1.5
    """

    @given(
        comp=_dir_name_strategy(),
        track=_dir_name_strategy(),
        group=_dir_name_strategy(),
    )
    @settings(max_examples=100)
    def test_missing_rules_raises_file_not_found(
        self, tmp_path_factory, comp: str, track: str, group: str
    ):
        assume(comp != track and track != group and comp != group)

        base = tmp_path_factory.mktemp("rules")
        # 创建目录结构但不放规则文件
        (base / comp / track / group).mkdir(parents=True, exist_ok=True)
        svc = RuleService(rules_base=base)

        # has_rules 应返回 False
        assert svc.has_rules(comp, track, group) is False

        # load_rules 应抛出 FileNotFoundError，而非返回空或崩溃
        with pytest.raises(FileNotFoundError) as exc_info:
            svc.load_rules(comp, track, group)

        # 错误信息应包含路径信息，便于定位
        assert comp in str(exc_info.value)
        assert track in str(exc_info.value)
        assert group in str(exc_info.value)

    @given(
        comp=_dir_name_strategy(),
        track=_dir_name_strategy(),
        group=_dir_name_strategy(),
    )
    @settings(max_examples=100)
    def test_completely_nonexistent_path(
        self, tmp_path_factory, comp: str, track: str, group: str
    ):
        """完全不存在的路径也应抛出 FileNotFoundError"""
        base = tmp_path_factory.mktemp("empty")
        svc = RuleService(rules_base=base)

        assert svc.has_rules(comp, track, group) is False

        with pytest.raises(FileNotFoundError):
            svc.load_rules(comp, track, group)


class TestProperty3PathConstruction:
    """Property 3: 评审规则路径构造正确性

    对于任意赛事类型、赛道和组别的组合，规则服务构造的文件路径
    应严格遵循 rules/{赛事}/{赛道}/{组别}/ 的格式。

    Feature: competition-judge-system, Property 3: 评审规则路径构造正确性
    Validates: Requirements 2.3
    """

    @given(
        comp=_dir_name_strategy(),
        track=_dir_name_strategy(),
        group=_dir_name_strategy(),
    )
    @settings(max_examples=100)
    def test_path_follows_convention(
        self, tmp_path_factory, comp: str, track: str, group: str
    ):
        assume(comp != track and track != group and comp != group)

        base = tmp_path_factory.mktemp("rules")
        _build_rules_tree(base, [(comp, [(track, [group])])])
        svc = RuleService(rules_base=base)

        rules = svc.load_rules(comp, track, group)

        # 验证返回的规则对象正确记录了三级路径信息
        assert rules.competition == comp
        assert rules.track == track
        assert rules.group == group

        # 验证实际的文件系统路径遵循 {base}/{comp}/{track}/{group}/ 结构
        expected_dir = base / comp / track / group
        assert expected_dir.is_dir()
        # 规则文件应存在于该目录下
        assert any(
            (expected_dir / f).is_file()
            for f in ["rules.md", "rules.pdf", "rules.docx", "rules.xlsx"]
        )


class TestProperty4DimensionCompleteness:
    """Property 4: 评审规则维度完整性

    对于任意成功加载的评审规则，其所有维度的满分之和应等于100分，
    且每个维度的满分值大于0。

    Feature: competition-judge-system, Property 4: 评审规则维度完整性
    Validates: Requirements 2.4
    """

    @given(
        num_dims=st.integers(min_value=2, max_value=8),
        data=st.data(),
    )
    @settings(max_examples=100)
    def test_dimensions_sum_to_100_and_positive(
        self, tmp_path_factory, num_dims: int, data: st.DataObject
    ):
        """动态生成N个维度（总分100），验证解析后满分之和为100且每项>0"""
        # 生成 num_dims 个正整数，总和为100
        raw_scores = data.draw(
            st.lists(
                st.integers(min_value=1, max_value=97),
                min_size=num_dims,
                max_size=num_dims,
            )
        )
        total_raw = sum(raw_scores)
        assume(total_raw > 0)
        # 归一化到总分100（整数分配）
        scores = [int(s * 100 / total_raw) for s in raw_scores]
        # 把余数加到最后一个维度
        remainder = 100 - sum(scores)
        scores[-1] += remainder
        # 确保所有分值 > 0
        assume(all(s > 0 for s in scores))

        # 构建规则文件
        lines = ["# 测试评审规则\n"]
        for i, score in enumerate(scores):
            lines.append(f"## 维度{i+1}（{score}分）\n")
            lines.append(f"- 子项{i+1}a\n")

        base = tmp_path_factory.mktemp("rules")
        group_dir = base / "test_comp" / "test_track" / "test_group"
        group_dir.mkdir(parents=True)
        (group_dir / "rules.md").write_text("".join(lines), encoding="utf-8")

        svc = RuleService(rules_base=base)
        rules = svc.load_rules("test_comp", "test_track", "test_group")

        # 属性验证：维度数量匹配
        assert len(rules.dimensions) == num_dims

        # 属性验证：每个维度满分 > 0
        for dim in rules.dimensions:
            assert dim.max_score > 0, f"维度 {dim.name} 满分应大于0"

        # 属性验证：满分之和 == 100
        total = sum(d.max_score for d in rules.dimensions)
        assert total == 100.0, f"维度满分之和应为100，实际为{total}"

    def test_real_rules_dimensions_sum_to_100(self):
        """验证实际 rules/ 目录下所有规则文件的维度满分之和为100"""
        svc = RuleService()  # 使用默认的 rules/ 目录
        if not svc.rules_base.is_dir():
            pytest.skip("rules/ 目录不存在")

        for comp_info in svc.list_competitions():
            for track_info in svc.list_tracks(comp_info.id):
                for group_info in svc.list_groups(comp_info.id, track_info.id):
                    if not group_info.has_rules:
                        continue
                    rules = svc.load_rules(
                        comp_info.id, track_info.id, group_info.id
                    )
                    total = sum(d.max_score for d in rules.dimensions)
                    assert total == 100.0, (
                        f"{comp_info.id}/{track_info.id}/{group_info.id} "
                        f"维度满分之和为{total}，应为100"
                    )
                    for dim in rules.dimensions:
                        assert dim.max_score > 0, (
                            f"{comp_info.id}/{track_info.id}/{group_info.id} "
                            f"维度 {dim.name} 满分应大于0"
                        )
