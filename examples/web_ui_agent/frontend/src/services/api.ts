/**
 * API 服务层 — axios 实例封装与接口调用函数
 */

import axios from 'axios';
import type {
  AuthResponse,
  CompetitionInfo,
  CustomVoiceInfo,
  EvaluationRules,
  GroupInfo,
  JudgeStyleInfo,
  LiveSessionCreate,
  LoginRequest,
  MaterialUploadResponse,
  ModeSwitch,
  PresetVoiceInfo,
  ProjectCreate,
  ProjectResponse,
  ProjectUpdate,
  RegisterRequest,
  ReviewResult,
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

// 响应拦截器：401 时清除 token 并跳转登录
api.interceptors.response.use(
  (res) => res,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('access_token');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  },
);

export default api;

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
};

// ── 评审 ─────────────────────────────────────────────────────

export const reviewApi = {
  textReview: (projectId: string, stage: string, judgeStyle = 'strict') =>
    api.post<ReviewResult>(`/projects/${projectId}/reviews/text`, {
      stage,
      judge_style: judgeStyle,
    }),

  offlineReview: (projectId: string, stage: string, judgeStyle = 'strict') =>
    api.post<ReviewResult>(`/projects/${projectId}/reviews/offline`, {
      stage,
      judge_style: judgeStyle,
    }),

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
