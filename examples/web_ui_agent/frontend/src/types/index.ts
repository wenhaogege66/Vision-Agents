/**
 * TypeScript 类型定义 — 与后端 Pydantic schemas 对应
 */

// ── 评审规则相关 ──────────────────────────────────────────────

export interface EvaluationDimension {
  name: string;
  max_score: number;
  sub_items: string[];
}

export interface EvaluationRules {
  competition: string;
  track: string;
  group: string;
  dimensions: EvaluationDimension[];
  raw_content: string;
}

// ── 材料管理相关 ──────────────────────────────────────────────

export interface MaterialUploadResponse {
  id: string;
  material_type: string;
  file_name: string;
  version: number;
  created_at: string;
}

export type MaterialType =
  | 'bp'
  | 'text_ppt'
  | 'presentation_ppt'
  | 'presentation_video';

// ── 评审相关 ─────────────────────────────────────────────────

export interface ReviewRequest {
  stage: string;
  judge_style?: string;
}

export interface DimensionScore {
  dimension: string;
  max_score: number;
  score: number;
  sub_items: Array<{ name: string; comment: string }>;
  suggestions: string[];
}

export interface ReviewResult {
  id: string;
  review_type: string;
  total_score: number;
  dimensions: DimensionScore[];
  overall_suggestions: string[];
  status: string;
  created_at: string;
}

// ── 赛事配置相关 ──────────────────────────────────────────────

export interface CompetitionInfo {
  id: string;
  name: string;
}

export interface TrackInfo {
  id: string;
  name: string;
}

export interface GroupInfo {
  id: string;
  name: string;
  has_rules: boolean;
}

// ── 项目管理相关 ──────────────────────────────────────────────

export interface ProjectCreate {
  name: string;
  competition: string;
  track: string;
  group: string;
}

export interface ProjectUpdate {
  name?: string;
  current_stage?: string;
}

export interface ProjectResponse {
  id: string;
  name: string;
  competition: string;
  track: string;
  group: string;
  current_stage: string;
  materials_status: Record<string, boolean>;
  created_at: string;
}

// ── 现场路演相关 ──────────────────────────────────────────────

export interface LiveSessionCreate {
  mode?: string;
  style?: string;
  voice?: string;
  voice_type?: string;
}

export interface ModeSwitch {
  session_id: string;
  mode: string;
}

export interface LiveSessionEnd {
  session_id: string;
}

// ── 评委风格相关 ──────────────────────────────────────────────

export interface JudgeStyleInfo {
  id: string;
  name: string;
  description: string;
}

// ── 音色管理相关 ──────────────────────────────────────────────

export interface PresetVoiceInfo {
  voice: string;
  name: string;
  description: string;
  languages: string[];
}

export interface CustomVoiceInfo {
  id: string;
  voice: string;
  preferred_name: string;
  target_model: string;
  created_at: string;
}

// ── 认证相关 ─────────────────────────────────────────────────

export interface RegisterRequest {
  email: string;
  password: string;
  display_name: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface AuthResponse {
  access_token: string;
  user: UserInfo;
}

export interface UserInfo {
  id: string;
  email: string;
  display_name?: string;
}

// ── 错误响应 ─────────────────────────────────────────────────

export interface ErrorResponse {
  error: string;
  message: string;
  details?: Record<string, unknown>;
}

// ── 比赛阶段 ─────────────────────────────────────────────────

export type CompetitionStage =
  | 'school_text'
  | 'school_presentation'
  | 'province_text'
  | 'province_presentation'
  | 'national_text'
  | 'national_presentation';

export const STAGE_LABELS: Record<CompetitionStage, string> = {
  school_text: '校赛文本评审',
  school_presentation: '校赛路演',
  province_text: '省赛文本评审',
  province_presentation: '省赛路演',
  national_text: '国赛文本评审',
  national_presentation: '国赛路演',
};
