"""赛事配置路由：赛事/赛道/组别查询和评审规则加载。"""

from fastapi import APIRouter, HTTPException

from app.models.schemas import (
    CompetitionInfo,
    EvaluationRules,
    GroupInfo,
    NameMappingsResponse,
    TrackInfo,
)
from app.services.rule_service import (
    COMPETITION_NAMES,
    GROUP_NAMES,
    TRACK_NAMES,
    rule_service,
)

router = APIRouter(prefix="/api/competitions", tags=["competitions"])

# 独立路由：名称映射 API（不使用 /api/competitions 前缀）
name_mappings_router = APIRouter(prefix="/api", tags=["name-mappings"])


@router.get("", response_model=list[CompetitionInfo])
async def list_competitions():
    """获取赛事类型列表"""
    return rule_service.list_competitions()


@router.get("/{competition}/tracks", response_model=list[TrackInfo])
async def list_tracks(competition: str):
    """获取赛道列表"""
    tracks = rule_service.list_tracks(competition)
    if not tracks:
        raise HTTPException(status_code=404, detail=f"未找到赛事 '{competition}' 或该赛事下无赛道")
    return tracks


@router.get("/{competition}/tracks/{track}/groups", response_model=list[GroupInfo])
async def list_groups(competition: str, track: str):
    """获取组别列表"""
    groups = rule_service.list_groups(competition, track)
    if not groups:
        raise HTTPException(
            status_code=404,
            detail=f"未找到赛事 '{competition}' 赛道 '{track}' 或该赛道下无组别",
        )
    return groups


@router.get(
    "/{competition}/tracks/{track}/groups/{group}/rules",
    response_model=EvaluationRules,
)
async def get_rules(competition: str, track: str, group: str):
    """获取评审规则"""
    try:
        return rule_service.load_rules(competition, track, group)
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=404,
            detail=str(e),
        ) from e


# ── 名称映射 API ──────────────────────────────────────────────


@name_mappings_router.get("/name-mappings", response_model=NameMappingsResponse)
async def get_name_mappings():
    """获取赛事/赛道/组别名称映射（批量）"""
    return NameMappingsResponse(
        competitions=COMPETITION_NAMES,
        tracks=TRACK_NAMES,
        groups=GROUP_NAMES,
    )
