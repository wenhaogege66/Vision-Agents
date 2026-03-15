"""赛事配置路由集成测试。"""

import textwrap
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.rule_service import RuleService


@pytest.fixture
def tmp_rules(tmp_path: Path) -> Path:
    """创建临时规则目录"""
    group_dir = tmp_path / "guochuangsai" / "gaojiao" / "benke_chuangyi"
    group_dir.mkdir(parents=True)
    (group_dir / "rules.md").write_text(
        textwrap.dedent("""\
        # 本科创意组

        ## 个人成长（30分）
        - 立德树人

        ## 项目创新（30分）
        - 技术创新

        ## 产业价值（25分）
        - 市场前景

        ## 团队协作（15分）
        - 团队构成
        """),
        encoding="utf-8",
    )
    return tmp_path


@pytest.fixture
def client(tmp_rules: Path):
    """创建使用临时规则目录的测试客户端"""
    svc = RuleService(rules_base=tmp_rules)
    with patch("app.routes.competitions.rule_service", svc):
        yield TestClient(app)


class TestListCompetitions:
    def test_returns_competitions(self, client: TestClient):
        resp = client.get("/api/competitions")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        ids = [c["id"] for c in data]
        assert "guochuangsai" in ids


class TestListTracks:
    def test_returns_tracks(self, client: TestClient):
        resp = client.get("/api/competitions/guochuangsai/tracks")
        assert resp.status_code == 200
        data = resp.json()
        ids = [t["id"] for t in data]
        assert "gaojiao" in ids

    def test_nonexistent_competition_404(self, client: TestClient):
        resp = client.get("/api/competitions/nonexistent/tracks")
        assert resp.status_code == 404


class TestListGroups:
    def test_returns_groups(self, client: TestClient):
        resp = client.get("/api/competitions/guochuangsai/tracks/gaojiao/groups")
        assert resp.status_code == 200
        data = resp.json()
        ids = [g["id"] for g in data]
        assert "benke_chuangyi" in ids

    def test_nonexistent_track_404(self, client: TestClient):
        resp = client.get("/api/competitions/guochuangsai/tracks/nonexistent/groups")
        assert resp.status_code == 404


class TestGetRules:
    def test_returns_rules(self, client: TestClient):
        resp = client.get(
            "/api/competitions/guochuangsai/tracks/gaojiao/groups/benke_chuangyi/rules"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["competition"] == "guochuangsai"
        assert len(data["dimensions"]) == 4

    def test_missing_rules_404(self, client: TestClient):
        resp = client.get(
            "/api/competitions/guochuangsai/tracks/gaojiao/groups/nonexistent/rules"
        )
        assert resp.status_code == 404
