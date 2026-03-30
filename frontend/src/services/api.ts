/**
 * API 服务层 — axios 实例封装与接口调用函数
 */

import axios from 'axios';
import type { AxiosRequestConfig, InternalAxiosRequestConfig } from 'axios';
import { msg } from '@/utils/messageHolder';

// ── 扩展 AxiosRequestConfig 以支持 timing metadata ──────────
declare module 'axios' {
  interface InternalAxiosRequestConfig {
    metadata?: { startTime: number };
  }
}
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

// 请求拦截器：自动附加 Authorization header + 记录请求开始时间
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  config.metadata = { startTime: performance.now() };
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

// 响应拦截器：统一错误通知 + 401 处理 + 重试支持 + 耗时日志
api.interceptors.response.use(
  (res) => {
    // 成功响应 → 重置重试计数
    _retryCount = 0;
    // 记录 API 调用耗时
    const startTime = res.config.metadata?.startTime;
    if (startTime) {
      const elapsed = performance.now() - startTime;
      console.log(`[API Timing] ${res.config.method?.toUpperCase()} ${res.config.url} - ${elapsed.toFixed(0)}ms`);
    }
    return res;
  },
  (error) => {
    const status = error.response?.status as number | undefined;

    // 记录失败请求的耗时
    const cfg = error.config as InternalAxiosRequestConfig | undefined;
    const startTime = cfg?.metadata?.startTime;
    if (startTime) {
      const elapsed = performance.now() - startTime;
      console.log(`[API Timing] ${cfg?.method?.toUpperCase()} ${cfg?.url} - ${elapsed.toFixed(0)}ms (error${status ? ` ${status}` : ''})`);
    }

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

  pending: (projectId: string) =>
    api.get<Array<{ id: string; review_type: string; status: string; auto_triggered: boolean; created_at: string }>>(
      `/projects/${projectId}/reviews/pending`,
    ).then(r => r.data),

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

// ── 数字人问辩 ───────────────────────────────────────────────

import type { DefenseQuestion, DefenseRecord, VideoTask, AvatarInfo, VideoGenerationOptions, PhotoAvatarCreateParams, AvatarCacheItem, VoiceCacheItem, PaginatedResponse, CacheQueryParams, SyncStatusResponse } from '@/types';

export const defenseApi = {
  // ── LiveAvatar 实时流式会话 ──
  createLiveAvatarSession: (projectId: string, avatarId?: string) =>
    api.post<{ provider: string; mode: string; session_token: string; session_id: string }>(
      `/projects/${projectId}/defense/avatar/liveavatar/session`,
      avatarId ? { avatar_id: avatarId } : {},
    ).then(r => r.data),

  // ── HeyGen 视频生成 ──
  generateHeyGenVideo: (projectId: string, text: string) =>
    api.post<{ provider: string; mode: string; video_id: string; status: string }>(
      `/projects/${projectId}/defense/avatar/heygen/generate`,
      { text },
    ).then(r => r.data),

  checkHeyGenVideoStatus: (projectId: string, videoId: string) =>
    api.get<{ video_id: string; status: string; video_url: string | null }>(
      `/projects/${projectId}/defense/avatar/heygen/status/${videoId}`,
    ).then(r => r.data),

  // ── 问题 CRUD ──
  listQuestions: (projectId: string) =>
    api.get<DefenseQuestion[]>(`/projects/${projectId}/defense/questions`).then(r => r.data),

  createQuestion: (projectId: string, content: string) =>
    api.post<DefenseQuestion>(`/projects/${projectId}/defense/questions`, { content }).then(r => r.data),

  updateQuestion: (projectId: string, questionId: string, content: string) =>
    api.put<DefenseQuestion>(`/projects/${projectId}/defense/questions/${questionId}`, { content }).then(r => r.data),

  deleteQuestion: (projectId: string, questionId: string) =>
    api.delete(`/projects/${projectId}/defense/questions/${questionId}`),

  submitAnswer: (projectId: string, audio: Blob, answerDuration: number, questionVideoTaskId?: string | null) => {
    const form = new FormData();
    form.append('audio', audio, 'answer.webm');
    form.append('answer_duration', String(answerDuration));
    if (questionVideoTaskId) {
      form.append('question_video_task_id', questionVideoTaskId);
    }
    return api.post<DefenseRecord>(`/projects/${projectId}/defense/submit-answer`, form, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 120_000,
    }).then(r => r.data);
  },

  listRecords: (projectId: string) =>
    api.get<DefenseRecord[]>(`/projects/${projectId}/defense/records`).then(r => r.data),

  deleteRecord: (projectId: string, recordId: string) =>
    api.delete(`/projects/${projectId}/defense/records/${recordId}`),

  // ── 资源列表 ──
  listHeygenVoices: (projectId: string) =>
    api.get<Array<{ voice_id: string; name: string; language: string; gender: string; preview_audio: string; is_custom: boolean }>>(
      `/projects/${projectId}/defense/avatar/heygen/voices`,
    ).then(r => r.data),

  listHeygenTalkingPhotos: (projectId: string) =>
    api.get<Array<{ id: string; name: string; preview_image_url: string; type: string }>>(
      `/projects/${projectId}/defense/avatar/heygen/talking-photos`,
    ).then(r => r.data),

  listHeygenAvatars: (projectId: string) =>
    api.get<AvatarInfo[]>(
      `/projects/${projectId}/defense/avatar/heygen/avatars`,
    ).then(r => r.data),

  listLiveAvatarAvatars: (projectId: string) =>
    api.get<Array<{ id: string; name: string; preview_image_url: string }>>(
      `/projects/${projectId}/defense/avatar/liveavatar/avatars`,
    ).then(r => r.data),

  getAvatarDefaults: (projectId: string) =>
    api.get<{ heygen_video_avatar_id: string; heygen_video_voice_id: string }>(
      `/projects/${projectId}/defense/avatar/defaults`,
    ).then(r => r.data),

  // ── 视频任务 ──
  generateQuestionVideo: (projectId: string, opts?: VideoGenerationOptions) =>
    api.post<VideoTask>(`/projects/${projectId}/defense/video-tasks/generate-question`, opts || {}).then(r => r.data),

  generateFeedbackVideo: (projectId: string, defenseRecordId: string, feedbackText: string) =>
    api.post<VideoTask>(`/projects/${projectId}/defense/video-tasks/generate-feedback`, {
      defense_record_id: defenseRecordId,
      feedback_text: feedbackText,
    }).then(r => r.data),

  getVideoTask: (projectId: string, taskId: string) =>
    api.get<VideoTask>(`/projects/${projectId}/defense/video-tasks/${taskId}`).then(r => r.data),

  getLatestQuestionTask: (projectId: string) =>
    api.get<VideoTask | null>(`/projects/${projectId}/defense/video-tasks/latest-question`).then(r => r.data),

  // ── Photo Avatar ──
  createPhotoAvatar: (projectId: string, params: PhotoAvatarCreateParams) =>
    api.post<{ generation_id: string }>(
      `/projects/${projectId}/defense/avatar/heygen/photo-avatar`,
      params,
    ).then(r => r.data),

  checkPhotoAvatarStatus: (projectId: string, generationId: string) =>
    api.get<{ generation_id: string; status: string }>(
      `/projects/${projectId}/defense/avatar/heygen/photo-avatar/${generationId}`,
    ).then(r => r.data),

  // ── 缓存 API ──
  listCachedAvatars: (projectId: string, params?: CacheQueryParams) => {
    const searchParams = new URLSearchParams();
    if (params?.page) searchParams.set('page', String(params.page));
    if (params?.page_size) searchParams.set('page_size', String(params.page_size));
    if (params?.search) searchParams.set('search', params.search);
    if (params?.is_custom !== undefined) searchParams.set('is_custom', String(params.is_custom));
    const qs = searchParams.toString();
    return api.get<PaginatedResponse<AvatarCacheItem>>(
      `/projects/${projectId}/defense/avatar/cache/avatars${qs ? `?${qs}` : ''}`,
    ).then(r => r.data);
  },

  listCachedVoices: (projectId: string, params?: CacheQueryParams) => {
    const searchParams = new URLSearchParams();
    if (params?.page) searchParams.set('page', String(params.page));
    if (params?.page_size) searchParams.set('page_size', String(params.page_size));
    if (params?.search) searchParams.set('search', params.search);
    const qs = searchParams.toString();
    return api.get<PaginatedResponse<VoiceCacheItem>>(
      `/projects/${projectId}/defense/avatar/cache/voices${qs ? `?${qs}` : ''}`,
    ).then(r => r.data);
  },

  triggerCacheSync: (projectId: string) =>
    api.post<{ message: string }>(
      `/projects/${projectId}/defense/avatar/cache/sync`,
    ).then(r => r.data),

  getCacheSyncStatus: (projectId: string) =>
    api.get<SyncStatusResponse>(
      `/projects/${projectId}/defense/avatar/cache/sync-status`,
    ).then(r => r.data),
};
