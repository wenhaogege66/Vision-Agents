"""Pydantic 请求/响应数据模型定义。

定义系统中所有 API 请求和响应使用的数据模型，
涵盖赛事配置、材料管理、评审结果、路演会话、评委风格和音色管理等。
"""

from datetime import datetime

from pydantic import BaseModel


# ── 评审规则相关 ──────────────────────────────────────────────


class EvaluationDimension(BaseModel):
    """评审维度（如"个人成长"、"项目创新"等）"""

    name: str  # 维度名称
    max_score: float  # 满分
    sub_items: list[str]  # 子项列表


class EvaluationRules(BaseModel):
    """评审规则，包含赛事/赛道/组别及其评审维度"""

    competition: str
    track: str
    group: str
    dimensions: list[EvaluationDimension]
    raw_content: str  # 原始规则文本


# ── 材料管理相关 ──────────────────────────────────────────────


class MaterialUploadResponse(BaseModel):
    """材料上传成功后的响应"""

    id: str
    material_type: str
    file_name: str
    version: int
    created_at: datetime


# ── 评审相关 ─────────────────────────────────────────────────


class ReviewRequest(BaseModel):
    """发起评审的请求体"""

    stage: str  # 当前比赛阶段
    judge_style: str = "strict"  # 评委风格: strict, gentle, academic


class DimensionScore(BaseModel):
    """单个维度的评审得分"""

    dimension: str
    max_score: float
    score: float
    sub_items: list[dict]  # [{"name": "...", "comment": "..."}]
    suggestions: list[str]


class ReviewResult(BaseModel):
    """评审结果"""

    id: str
    review_type: str
    total_score: float
    dimensions: list[DimensionScore]
    overall_suggestions: list[str]
    status: str
    created_at: datetime


# ── 赛事配置相关 ──────────────────────────────────────────────


class CompetitionInfo(BaseModel):
    """赛事信息"""

    id: str
    name: str


class TrackInfo(BaseModel):
    """赛道信息"""

    id: str
    name: str


class GroupInfo(BaseModel):
    """组别信息"""

    id: str
    name: str
    has_rules: bool


# ── 项目管理相关 ──────────────────────────────────────────────


class ProjectCreate(BaseModel):
    """创建项目的请求体"""

    name: str
    competition: str
    track: str
    group: str


class ProjectUpdate(BaseModel):
    """更新项目的请求体"""

    name: str | None = None
    current_stage: str | None = None


class ProjectResponse(BaseModel):
    """项目详情响应"""

    id: str
    name: str
    competition: str
    track: str
    group: str
    current_stage: str
    materials_status: dict  # {"bp": bool, "text_ppt": bool, ...}
    created_at: datetime


# ── 现场路演相关 ──────────────────────────────────────────────


class LiveSessionCreate(BaseModel):
    """创建现场路演会话的请求体"""

    mode: str = "question"  # question 或 suggestion
    style: str = "strict"  # 评委风格: strict, gentle, academic
    voice: str = "Cherry"  # 音色: 预设音色名或自定义音色ID
    voice_type: str = "preset"  # preset 或 custom


class ModeSwitch(BaseModel):
    """切换路演交互模式的请求体"""

    session_id: str  # 路演会话ID
    mode: str  # question 或 suggestion


class LiveSessionEnd(BaseModel):
    """结束路演会话的请求体"""

    session_id: str  # 路演会话ID


# ── 评委风格相关 ──────────────────────────────────────────────


class JudgeStyleInfo(BaseModel):
    """评委风格信息"""

    id: str  # 风格标识: strict, gentle, academic
    name: str  # 显示名称: 严厉型, 温和型, 学术型
    description: str  # 风格简介


# ── 音色管理相关 ──────────────────────────────────────────────


class PresetVoiceInfo(BaseModel):
    """预设音色信息"""

    voice: str  # 音色参数值: Cherry, Ethan, Serena 等
    name: str  # 中文名称: 芊悦, 晨煦, 苏瑶 等
    description: str  # 音色描述
    languages: list[str]  # 支持的语种


class CustomVoiceInfo(BaseModel):
    """用户自定义音色信息（通过声音复刻创建）"""

    id: str  # 数据库记录ID
    voice: str  # 声音复刻API返回的voice标识
    preferred_name: str  # 用户指定的音色名称
    target_model: str  # 驱动音色的TTS模型
    created_at: datetime


# ── 认证相关 ─────────────────────────────────────────────────


class RegisterRequest(BaseModel):
    """用户注册请求"""

    email: str
    password: str
    display_name: str


class LoginRequest(BaseModel):
    """用户登录请求"""

    email: str
    password: str


class AuthResponse(BaseModel):
    """认证成功响应（登录/注册）"""

    access_token: str
    user: "UserInfo"


class UserInfo(BaseModel):
    """用户信息"""

    id: str
    email: str
    display_name: str | None = None


# ── 错误响应 ─────────────────────────────────────────────────


class ErrorResponse(BaseModel):
    """统一错误响应格式"""

    error: str  # 错误类型标识
    message: str  # 用户可读的中文错误信息
    details: dict | None = None  # 可选的详细信息
