/**
 * API 服务层 — axios 实例封装与接口调用函数
 */

import axios from 'axios';
import type { AxiosRequestConfig, InternalAxiosRequestConfig } from 'axios';
import { msg } from '@/utils/messageHolder';
import type {
  AuthResponse,
  CompetitionInfo,
  CustomVoiceInfo,
  EvaluationRules,
  GroupInfo,
  JudgeStyleInfo,
  LiveSessionCreate,
  LoginRequest,
  MaterialStatusResponse,
  MaterialUploadResponse,
  ModeSwitch,
  NameMappings,
  PresetVoiceInfo,
  ProjectCreate,
  ProjectProfile,
  ProjectResponse,
  ProjectUpdate,
  RegisterRequest,
  ReviewResult,
  StageConfig,
  TagInfo,
  TrackInfo,
} from '@/types';

// ── axios 实例 ───────────────────────────────────────────────

const api = axios.create({
  baseURL: '/api',
  timeout: 30_000,
  headers: { 'Content-Type': 'application/json' },
});

// 请求拦截器：自动附加 Authorization header
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// ── 重试机制 ──────────────────────────────────────────────────

let _lastFailedConfig: AxiosRequestConfig | null = null;
let _retryCount = 0;
const MAX_RETRIES = 3;
const FALLBACK_MESSAGE = '请检查网络连接或联系管理员';

/** 获取上次失败请求的配置 */
export function getLastFailedConfig(): AxiosRequestConfig | null {
  return _lastFailedConfig;
}

/** 重试上次失败的请求。超过 3 次连续失败后返回 null 并提示兜底信息。 */
export async function retryLastRequest() {
  if (!_lastFailedConfig) return null;
  if (_retryCount >= MAX_RETRIES) {
    msg.error(FALLBACK_MESSAGE);
    return null;
  }
  _retryCount++;
  try {
    const res = await api.request(_lastFailedConfig);
    // 成功 → 重置状态
    _lastFailedConfig = null;
    _retryCount = 0;
    return res;
  } catch {
    if (_retryCount >= MAX_RETRIES) {
      msg.error(FALLBACK_MESSAGE);
    }
    return null;
  }
}

// 响应拦截器：统一错误通知 + 401 处理 + 重试支持
api.interceptors.response.use(
  (res) => {
    // 成功响应 → 重置重试计数
    _retryCount = 0;
    return res;
  },
  (error) => {
    const status = error.response?.status as number | undefined;

    // 401 → 清除 token 并跳转登录（保留原有行为）
    if (status === 401) {
      localStorage.removeItem('access_token');
      window.location.href = '/login';
      return Promise.reject(error);
    }

    // 提取可读错误信息
    const errorMsg: string =
      error.response?.data?.message ??
      (status ? `请求失败 (${status})` : '网络请求失败，请检查网络连接');

    // 统一展示错误通知
    msg.error(errorMsg);

    // 存储失败请求配置以便重试（去掉 adapter 等内部字段，只保留可重发的配置）
    const cfg = error.config as InternalAxiosRequestConfig | undefined;
    if (cfg) {
      const { url, method, data, params, headers, timeout } = cfg;
      _lastFailedConfig = { url, method, data, params, headers, timeout };
    }

    return Promise.reject(error);
  },
);

export default api;

/** 仅用于测试：重置内部重试状态 */
export function _resetRetryState() {
  _lastFailedConfig = null;
  _retryCount = 0;
}

// ── 认证 ─────────────────────────────────────────────────────

export const authApi = {
  register: (data: RegisterRequest) =>
    api.post<AuthResponse>('/auth/register', data),

  login: (data: LoginRequest) =>
    api.post<AuthResponse>('/auth/login', data),

  me: () => api.get<AuthResponse['user']>('/auth/me'),
};

// ── 赛事配置 ─────────────────────────────────────────────────

export const competitionApi = {
  list: () =>
    api.get<CompetitionInfo[]>('/competitions'),

  tracks: (competition: string) =>
    api.get<TrackInfo[]>(`/competitions/${competition}/tracks`),

  groups: (competition: string, track: string) =>
    api.get<GroupInfo[]>(
      `/competitions/${competition}/tracks/${track}/groups`,
    ),

  rules: (competition: string, track: string, group: string) =>
    api.get<EvaluationRules>(
      `/competitions/${competition}/tracks/${track}/groups/${group}/rules`,
    ),

  nameMappings: () =>
    api.get<NameMappings>('/name-mappings').then(res => res.data),
};

// ── 项目管理 ─────────────────────────────────────────────────

export const projectApi = {
  create: (data: ProjectCreate) =>
    api.post<ProjectResponse>('/projects', data),

  list: () =>
    api.get<ProjectResponse[]>('/projects'),

  get: (id: string) =>
    api.get<ProjectResponse>(`/projects/${id}`),

  update: (id: string, data: ProjectUpdate) =>
    api.put<ProjectResponse>(`/projects/${id}`, data),

  delete: (id: string) =>
    api.delete(`/projects/${id}`),

  stageDates: (projectId: string) =>
    api.get<StageConfig[]>(`/projects/${projectId}/stage-dates`).then(res => res.data),
};

// ── 材料管理 ─────────────────────────────────────────────────

export const materialApi = {
  upload: (projectId: string, materialType: string, file: File) => {
    const form = new FormData();
    form.append('file', file);
    form.append('material_type', materialType);
    return api.post<MaterialUploadResponse>(
      `/projects/${projectId}/materials`,
      form,
      { headers: { 'Content-Type': 'multipart/form-data' }, timeout: 120_000 },
    );
  },

  list: (projectId: string) =>
    api.get<MaterialUploadResponse[]>(`/projects/${projectId}/materials`),

  getByType: (projectId: string, type: string) =>
    api.get<MaterialUploadResponse>(`/projects/${projectId}/materials/${type}`),

  versions: (projectId: string, type: string) =>
    api.get<MaterialUploadResponse[]>(
      `/projects/${projectId}/materials/${type}/versions`,
    ),

  status: (projectId: string) =>
    api.get<MaterialStatusResponse>(`/projects/${projectId}/materials/status`).then(res => res.data),

  download: (projectId: string, materialId: string) =>
    api.get<{ download_url: string; file_name: string; expires_in: number }>(`/projects/${projectId}/materials/${materialId}/download`).then(res => res.data),
};

// ── 评审 ─────────────────────────────────────────────────────

export const reviewApi = {
  textReview: (projectId: string, stage: string, judgeStyle = 'strict', materialTypes?: string[]) =>
    api.post<ReviewResult>(`/projects/${projectId}/reviews/text`, {
      stage,
      judge_style: judgeStyle,
      ...(materialTypes ? { material_types: materialTypes } : {}),
    }, { timeout: 180_000 }),

  offlineReview: (projectId: string, stage: string, judgeStyle = 'strict') =>
    api.post<ReviewResult>(`/projects/${projectId}/reviews/offline`, {
      stage,
      judge_style: judgeStyle,
    }, { timeout: 360_000 }),

  list: (projectId: string) =>
    api.get<ReviewResult[]>(`/projects/${projectId}/reviews`),

  get: (projectId: string, reviewId: string) =>
    api.get<ReviewResult>(`/projects/${projectId}/reviews/${reviewId}`),

  exportPdf: (projectId: string, reviewId: string) =>
    api.get(`/projects/${projectId}/reviews/${reviewId}/export`, {
      responseType: 'blob',
    }),
};

// ── 现场路演 ─────────────────────────────────────────────────

export const liveApi = {
  start: (projectId: string, data: LiveSessionCreate) =>
    api.post(`/projects/${projectId}/live/start`, data),

  switchMode: (projectId: string, data: ModeSwitch) =>
    api.post(`/projects/${projectId}/live/mode`, data),

  end: (projectId: string, sessionId: string) =>
    api.post(`/projects/${projectId}/live/end`, { session_id: sessionId }),

  share: (projectId: string, sessionId: string) =>
    api.post<{ share_url: string; expires_in: number }>(`/projects/${projectId}/live/${sessionId}/share`),
};

// ── 评委风格 ─────────────────────────────────────────────────

export const judgeStyleApi = {
  list: () => api.get<JudgeStyleInfo[]>('/judge-styles'),
};

// ── 音色管理 ─────────────────────────────────────────────────

export const voiceApi = {
  presets: () =>
    api.get<PresetVoiceInfo[]>('/voices/presets'),

  customList: () =>
    api.get<CustomVoiceInfo[]>('/voices/custom'),

  clone: (audioFile: File, preferredName: string) => {
    const form = new FormData();
    form.append('audio_file', audioFile);
    form.append('preferred_name', preferredName);
    return api.post<CustomVoiceInfo>('/voices/clone', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 60_000,
    });
  },

  deleteCustom: (voiceId: string) =>
    api.delete(`/voices/custom/${voiceId}`),
};

// ── 项目简介 ─────────────────────────────────────────────────

export const profileApi = {
  extract: (projectId: string) =>
    api.post<ProjectProfile>(`/projects/${projectId}/profile/extract`, null, { timeout: 180_000 }).then(res => res.data),

  get: (projectId: string) =>
    api.get<ProjectProfile | null>(`/projects/${projectId}/profile`).then(res => res.data),

  update: (projectId: string, data: Partial<ProjectProfile>) =>
    api.put<ProjectProfile>(`/projects/${projectId}/profile`, data).then(res => res.data),
};

// ── 自定义标签 ───────────────────────────────────────────────

export const tagApi = {
  create: (data: { name: string; color: string }) =>
    api.post<TagInfo>('/tags', data).then(res => res.data),

  list: () =>
    api.get<TagInfo[]>('/tags').then(res => res.data),

  update: (tagId: string, data: { name: string; color: string }) =>
    api.put<TagInfo>(`/tags/${tagId}`, data).then(res => res.data),

  delete: (tagId: string) =>
    api.delete(`/tags/${tagId}`),

  addToProject: (projectId: string, tagId: string) =>
    api.post<TagInfo>(`/projects/${projectId}/tags`, { tag_id: tagId }).then(res => res.data),

  removeFromProject: (projectId: string, tagId: string) =>
    api.delete(`/projects/${projectId}/tags/${tagId}`),

  getProjectTags: (projectId: string) =>
    api.get<TagInfo[]>(`/projects/${projectId}/tags`).then(res => res.data),
};
