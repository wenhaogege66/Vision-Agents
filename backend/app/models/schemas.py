"""Pydantic 请求/响应数据模型定义。

定义系统中所有 API 请求和响应使用的数据模型，
涵盖赛事配置、材料管理、评审结果、路演会话、评委风格和音色管理等。
"""

from datetime import datetime

from pydantic import BaseModel, Field


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
    material_types: list[str] | None = None  # 文本评审时指定使用的材料类型列表
    auto_triggered: bool = False  # 是否由系统自动触发


class DimensionScore(BaseModel):
    """单个维度的评审得分"""

    dimension: str
    max_score: float
    score: float
    sub_items: list[dict]  # [{"name": "...", "comment": "..."}]
    suggestions: list[str]


class PPTVisualDimension(BaseModel):
    """PPT 视觉评审单维度"""

    name: str  # 信息结构/信息密度/视觉设计/图示表达/说服力/完整性
    rating: str  # 优秀/良好/一般/较差
    comment: str  # 具体评价
    suggestions: list[str]  # 改进建议（优秀时可为空）


class PPTVisualReviewResult(BaseModel):
    """PPT 视觉评审结果"""

    dimensions: list[PPTVisualDimension]
    overall_comment: str


class PresenterEvaluation(BaseModel):
    """路演者表现评价"""

    language_expression: str  # 语言表达评价
    rhythm_control: str  # 节奏控制评价
    logic_clarity: str  # 逻辑清晰度评价
    engagement: str  # 互动感评价
    overall_comment: str  # 总体评价
    suggestions: list[str]  # 改进建议


class ReviewResult(BaseModel):
    """评审结果"""

    id: str
    review_type: str
    total_score: float
    dimensions: list[DimensionScore]
    overall_suggestions: list[str]
    status: str
    created_at: datetime
    selected_materials: list[str] | None = None  # 评审所选材料类型列表
    ppt_visual_review: dict | None = None  # PPT 视觉评审结果
    presenter_evaluation: dict | None = None  # 路演者表现评价


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


# ── 材料就绪状态相关 ──────────────────────────────────────────


class MaterialStatusItem(BaseModel):
    """单种材料的状态"""

    uploaded: bool
    ready: bool


class MaterialStatusResponse(BaseModel):
    """材料就绪状态总览响应"""

    bp: MaterialStatusItem
    text_ppt: MaterialStatusItem
    presentation_ppt: MaterialStatusItem
    presentation_video: MaterialStatusItem
    presentation_audio: MaterialStatusItem  # 路演音频
    any_text_material_ready: bool
    offline_review_ready: bool
    offline_review_reasons: list[str]


# ── 名称映射相关 ──────────────────────────────────────────────


class NameMappingsResponse(BaseModel):
    """赛事/赛道/组别名称映射批量响应"""

    competitions: dict[str, str]
    tracks: dict[str, str]
    groups: dict[str, str]


# ── 项目简介相关 ──────────────────────────────────────────────


class ProjectProfile(BaseModel):
    """AI 提取的项目简介"""

    id: str
    project_id: str
    team_intro: str | None = None
    domain: str | None = None
    startup_status: str | None = None
    achievements: str | None = None
    product_links: str | None = None
    next_goals: str | None = None
    is_ai_generated: bool = True
    created_at: datetime
    updated_at: datetime


class ProjectProfileUpdate(BaseModel):
    """用户编辑项目简介的请求体"""

    team_intro: str | None = None
    domain: str | None = None
    startup_status: str | None = None
    achievements: str | None = None
    product_links: str | None = None
    next_goals: str | None = None


# ── 自定义标签相关 ────────────────────────────────────────────


class TagCreate(BaseModel):
    """创建标签的请求体"""

    name: str
    color: str


class TagResponse(BaseModel):
    """标签详情响应"""

    id: str
    name: str
    color: str
    created_at: datetime


# ── 材料下载相关 ──────────────────────────────────────────────


class DownloadUrlResponse(BaseModel):
    """材料版本下载签名 URL 响应"""

    download_url: str
    file_name: str
    expires_in: int


# ── 会议分享相关 ──────────────────────────────────────────────


class ShareLinkResponse(BaseModel):
    """会议分享链接响应"""

    share_url: str
    expires_in: int


# ── 阶段配置相关 ──────────────────────────────────────────────


class StageConfigResponse(BaseModel):
    """赛事阶段日期配置响应"""

    stage: str
    stage_date: str | None  # "YYYY-MM-DD" 或 None


# ── 数字人问辩相关 ────────────────────────────────────────────


class DefenseQuestionCreate(BaseModel):
    """创建/更新预定义问题的请求体"""

    content: str = Field(..., min_length=1, max_length=40)  # 最长 40 字


class DefenseQuestionResponse(BaseModel):
    """预定义问题响应"""

    id: str
    project_id: str
    content: str
    sort_order: int
    created_at: datetime
    updated_at: datetime


class DefenseRecordResponse(BaseModel):
    """问辩记录响应"""

    id: str
    project_id: str
    questions_snapshot: list[dict]
    user_answer_text: str | None
    ai_feedback_text: str | None
    answer_duration: int
    status: str
    feedback_type: str = "text"
    question_video_task_id: str | None = None
    feedback_video_task_id: str | None = None
    created_at: datetime


class VideoTaskResponse(BaseModel):
    """视频生成任务响应"""

    id: str
    project_id: str
    video_type: str  # "question" | "feedback"
    status: str  # "pending" | "processing" | "completed" | "failed" | "outdated"
    persistent_url: str | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime


class GenerateQuestionVideoRequest(BaseModel):
    """生成提问视频请求（使用项目已有问题，无需额外参数）"""

    pass


class GenerateFeedbackVideoRequest(BaseModel):
    """生成反馈视频请求"""

    defense_record_id: str
    feedback_text: str
