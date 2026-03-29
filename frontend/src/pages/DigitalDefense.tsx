import { useEffect, useRef, useState, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Card,
  Button,
  InputNumber,
  Typography,
  Tag,
  Spin,
  Empty,
  Result,
  Radio,
  Alert,
  Progress,
  Flex,
  Popconfirm,
  Select,
  Image,
  Modal,
  Switch,
  Form,
  Input,
} from 'antd';
import {
  SoundOutlined,
  AudioOutlined,
  RobotOutlined,
  ClockCircleOutlined,
  VideoCameraOutlined,
  ThunderboltOutlined,
  PlayCircleOutlined,
  StopOutlined,
  DeleteOutlined,
  UserOutlined,
  PlusOutlined,
} from '@ant-design/icons';
import { LiveAvatarSession, SessionEvent, SessionState, AgentEventsEnum } from '@heygen/liveavatar-web-sdk';
import BackButton from '@/components/BackButton';
import AudioWaveform from '@/components/AudioWaveform';
import QuestionPanel from '@/components/QuestionPanel';
import FeedbackTypeModal from '@/components/FeedbackTypeModal';
import VideoTaskStatus from '@/components/VideoTaskStatus';
import { defenseApi, projectApi } from '@/services/api';
import { msg } from '@/utils/messageHolder';
import type { DefenseRecord, VideoTask, DefenseQuestion, AvatarInfo, VideoGenerationOptions, PhotoAvatarCreateParams } from '@/types';

const { Title, Text, Paragraph } = Typography;

type AvatarProvider = 'liveavatar' | 'heygen';
type Phase = 'idle' | 'loading' | 'generating' | 'ready' | 'speaking' | 'recording' | 'processing' | 'feedback_modal' | 'feedback_text' | 'feedback_video' | 'done';

const ORDINALS = ['第一', '第二', '第三', '第四', '第五', '第六', '第七', '第八', '第九', '第十'];

function formatTime(dateStr: string): string {
  return new Date(dateStr).toLocaleString('zh-CN', {
    year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit',
  });
}

function buildSpeechText(projectName: string, questions: Array<{ content: string; sort_order: number }>): string {
  const sorted = [...questions].sort((a, b) => a.sort_order - b.sort_order);
  const parts = sorted.map((q, i) => `${ORDINALS[i] ?? `第${i + 1}`}，${q.content}`);
  return `你好，我是数字人评委，对于你们的${projectName}项目，我有以下${sorted.length}个问题：${parts.join('；')}`;
}

export default function DigitalDefense() {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();

  // ── Core state ────────────────────────────────────────────
  const [provider, setProvider] = useState<AvatarProvider>('liveavatar');
  const [phase, setPhase] = useState<Phase>('idle');
  const [countdown, setCountdown] = useState(0);
  const [answerDuration, setAnswerDuration] = useState(30);
  const [records, setRecords] = useState<DefenseRecord[]>([]);
  const [projectName, setProjectName] = useState('');
  const [loadingRecords, setLoadingRecords] = useState(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [questions, setQuestions] = useState<DefenseQuestion[]>([]);

  // ── Video task state (pre-generate flow) ──────────────────
  const [questionTask, setQuestionTask] = useState<VideoTask | null>(null);
  const [taskPolling, setTaskPolling] = useState(false);
  const [taskProgress, setTaskProgress] = useState(0);
  const taskPollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // ── Feedback flow state ───────────────────────────────────
  const [feedbackModalOpen, setFeedbackModalOpen] = useState(false);
  const [pendingFeedbackText, setPendingFeedbackText] = useState<string | null>(null);
  const [pendingRecordId, setPendingRecordId] = useState<string | null>(null);
  const [feedbackVideoPolling, setFeedbackVideoPolling] = useState(false);
  const [feedbackVideoProgress, setFeedbackVideoProgress] = useState(0);
  const feedbackPollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // ── History video playback state ──────────────────────────
  const [playingRecordVideo, setPlayingRecordVideo] = useState<{ recordId: string; type: 'question' | 'feedback' } | null>(null);
  const [videoErrors, setVideoErrors] = useState<Set<string>>(new Set());
  const [recordVideoTasks, setRecordVideoTasks] = useState<Record<string, VideoTask>>({});

  // ── LiveAvatar state ──────────────────────────────────────
  const sessionRef = useRef<LiveAvatarSession | null>(null);
  const [liveAvatarReady, setLiveAvatarReady] = useState(false);

  // ── Avatar/Voice customization state ──────────────────────
  const [heygenVoices, setHeygenVoices] = useState<Array<{ voice_id: string; name: string; language: string; gender: string; preview_audio: string; is_custom: boolean }>>([]);
  const [heygenCharacters, setHeygenCharacters] = useState<AvatarInfo[]>([]);
  const [liveAvatarList, setLiveAvatarList] = useState<Array<{ id: string; name: string; preview_image_url: string }>>([]);
  const [selectedVoiceId, setSelectedVoiceId] = useState<string | undefined>(undefined);
  const [selectedCharacterId, setSelectedCharacterId] = useState<string | undefined>(undefined);
  const [selectedLiveAvatarId, setSelectedLiveAvatarId] = useState<string | undefined>(undefined);
  const [loadingResources, setLoadingResources] = useState(false);
  const [defaultAvatarId, setDefaultAvatarId] = useState('');
  const [defaultVoiceId, setDefaultVoiceId] = useState('');

  // ── Video options state ───────────────────────────────────
  const [voiceLocale, setVoiceLocale] = useState('zh-CN');
  const [resolution, setResolution] = useState('720p');
  const [aspectRatio, setAspectRatio] = useState('16:9');
  const [expressiveness, setExpressiveness] = useState('medium');
  const [removeBackground, setRemoveBackground] = useState(false);

  // ── Photo Avatar creation state ───────────────────────────
  const [photoAvatarModalOpen, setPhotoAvatarModalOpen] = useState(false);
  const [photoAvatarCreating, setPhotoAvatarCreating] = useState(false);
  const [photoAvatarForm] = Form.useForm();

  // ── Fullscreen video playback state ───────────────────────
  const [fullscreenVideo, setFullscreenVideo] = useState(false);
  const fullscreenVideoRef = useRef<HTMLVideoElement>(null);

  // ── Media refs ────────────────────────────────────────────
  const videoRef = useRef<HTMLVideoElement>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioStreamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const countdownTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const [audioStream, setAudioStream] = useState<MediaStream | null>(null);

  // Refs for latest state in callbacks
  const phaseRef = useRef(phase);
  phaseRef.current = phase;
  const providerRef = useRef(provider);
  providerRef.current = provider;

  // ── Load data ─────────────────────────────────────────────
  const loadRecords = useCallback(async () => {
    if (!projectId) return;
    try { setRecords(await defenseApi.listRecords(projectId)); }
    catch { /* interceptor */ }
    finally { setLoadingRecords(false); }
  }, [projectId]);

  const loadQuestions = useCallback(async () => {
    if (!projectId) return;
    try { setQuestions(await defenseApi.listQuestions(projectId)); }
    catch { /* interceptor */ }
  }, [projectId]);

  // ── Load video tasks for history records ──────────────────
  const loadRecordVideoTasks = useCallback(async (recs: DefenseRecord[]) => {
    if (!projectId) return;
    const taskIds = new Set<string>();
    for (const r of recs) {
      if (r.question_video_task_id) taskIds.add(r.question_video_task_id);
      if (r.feedback_video_task_id) taskIds.add(r.feedback_video_task_id);
    }
    const tasks: Record<string, VideoTask> = {};
    for (const tid of taskIds) {
      try {
        const t = await defenseApi.getVideoTask(projectId, tid);
        tasks[tid] = t;
      } catch { /* skip */ }
    }
    setRecordVideoTasks(tasks);
  }, [projectId]);

  useEffect(() => {
    if (!projectId) return;
    projectApi.get(projectId).then((res) => setProjectName(res.data.name)).catch(() => {});
    loadRecords();
    loadQuestions();
  }, [projectId, loadRecords, loadQuestions]);

  // ── Load avatar/voice resources ───────────────────────────
  useEffect(() => {
    if (!projectId) return;
    setLoadingResources(true);
    const loadHeygenResources = async () => {
      try {
        const [voices, avatars, defaults] = await Promise.all([
          defenseApi.listHeygenVoices(projectId),
          defenseApi.listHeygenAvatars(projectId),
          defenseApi.getAvatarDefaults(projectId),
        ]);
        setHeygenVoices(voices);
        setHeygenCharacters(avatars);
        setDefaultAvatarId(defaults.heygen_video_avatar_id || '');
        setDefaultVoiceId(defaults.heygen_video_voice_id || '');
      } catch { /* silent */ }
    };
    const loadLiveAvatarResources = async () => {
      try {
        setLiveAvatarList(await defenseApi.listLiveAvatarAvatars(projectId));
      } catch { /* silent */ }
    };
    Promise.all([loadHeygenResources(), loadLiveAvatarResources()]).finally(() => setLoadingResources(false));
  }, [projectId]);

  // Load video tasks when records change
  useEffect(() => {
    if (records.length > 0) loadRecordVideoTasks(records);
  }, [records, loadRecordVideoTasks]);

  // ── Task polling helpers ──────────────────────────────────
  const stopTaskPolling = useCallback(() => {
    if (taskPollRef.current) {
      clearInterval(taskPollRef.current);
      taskPollRef.current = null;
    }
    setTaskPolling(false);
  }, []);

  const startTaskPolling = useCallback((taskId: string) => {
    if (!projectId) return;
    stopTaskPolling();
    setTaskPolling(true);
    setTaskProgress(5);
    let attempts = 0;
    const maxAttempts = 720;
    taskPollRef.current = setInterval(async () => {
      attempts++;
      setTaskProgress(Math.min(5 + (attempts / maxAttempts) * 90, 95));
      try {
        const task = await defenseApi.getVideoTask(projectId, taskId);
        setQuestionTask(task);
        if (task.status === 'completed') {
          setTaskProgress(100);
          stopTaskPolling();
          setPhase('ready');
        } else if (task.status === 'failed') {
          stopTaskPolling();
          msg.error(task.error_message || '视频生成失败');
          setPhase('idle');
        }
      } catch {
        // network error, continue polling
      }
      if (attempts >= maxAttempts) {
        stopTaskPolling();
        msg.error('视频生成超时');
        setPhase('idle');
      }
    }, 5000);
  }, [projectId, stopTaskPolling]);

  // ── Feedback video polling helpers ────────────────────────
  const stopFeedbackPolling = useCallback(() => {
    if (feedbackPollRef.current) {
      clearInterval(feedbackPollRef.current);
      feedbackPollRef.current = null;
    }
    setFeedbackVideoPolling(false);
  }, []);

  const pollFeedbackVideo = useCallback((taskId: string): Promise<VideoTask | null> => {
    if (!projectId) return Promise.resolve(null);
    return new Promise((resolve) => {
      setFeedbackVideoPolling(true);
      setFeedbackVideoProgress(5);
      let attempts = 0;
      const maxAttempts = 720;
      feedbackPollRef.current = setInterval(async () => {
        attempts++;
        setFeedbackVideoProgress(Math.min(5 + (attempts / maxAttempts) * 90, 95));
        try {
          const task = await defenseApi.getVideoTask(projectId, taskId);
          if (task.status === 'completed') {
            setFeedbackVideoProgress(100);
            stopFeedbackPolling();
            resolve(task);
          } else if (task.status === 'failed') {
            stopFeedbackPolling();
            resolve(null);
          }
        } catch {
          // continue
        }
        if (attempts >= maxAttempts) {
          stopFeedbackPolling();
          resolve(null);
        }
      }, 5000);
    });
  }, [projectId, stopFeedbackPolling]);

  // ── Page mount: recover existing task ─────────────────────
  useEffect(() => {
    if (!projectId || provider !== 'heygen') return;
    (async () => {
      try {
        const task = await defenseApi.getLatestQuestionTask(projectId);
        if (!task) return;
        setQuestionTask(task);
        if (task.status === 'pending' || task.status === 'processing') {
          setPhase('generating');
          startTaskPolling(task.id);
        } else if (task.status === 'completed' && task.persistent_url) {
          setPhase('ready');
        }
      } catch { /* no task */ }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId, provider]);

  // ── Cleanup ───────────────────────────────────────────────
  const cleanupMedia = useCallback(() => {
    if (countdownTimerRef.current) { clearInterval(countdownTimerRef.current); countdownTimerRef.current = null; }
    if (mediaRecorderRef.current?.state !== 'inactive') mediaRecorderRef.current?.stop();
    mediaRecorderRef.current = null;
    audioStreamRef.current?.getTracks().forEach((t) => t.stop());
    audioStreamRef.current = null;
    setAudioStream(null);
    chunksRef.current = [];
  }, []);

  useEffect(() => () => {
    cleanupMedia();
    stopTaskPolling();
    stopFeedbackPolling();
    sessionRef.current?.stop().catch(() => {});
  }, [cleanupMedia, stopTaskPolling, stopFeedbackPolling]);

  // ── Finish defense ────────────────────────────────────────
  const finishDefense = useCallback(() => {
    setPhase('done');
    setPendingFeedbackText(null);
    setPendingRecordId(null);
    loadRecords();
    setTimeout(() => setPhase('idle'), 3000);
  }, [loadRecords]);

  // ── Recording ─────────────────────────────────────────────
  const startRecording = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      audioStreamRef.current = stream;
      setAudioStream(stream);
      const recorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
      mediaRecorderRef.current = recorder;
      chunksRef.current = [];
      recorder.ondataavailable = (e) => { if (e.data.size > 0) chunksRef.current.push(e.data); };
      recorder.start();
      setPhase('recording');
      let remaining = answerDuration;
      setCountdown(remaining);
      countdownTimerRef.current = setInterval(() => {
        remaining -= 1;
        setCountdown(remaining);
        if (remaining <= 0) {
          clearInterval(countdownTimerRef.current!);
          countdownTimerRef.current = null;
        }
      }, 1000);
    } catch {
      msg.warning('请允许麦克风权限以进行回答录音');
      setPhase('idle');
    }
  }, [answerDuration]);

  // Auto-stop recording when countdown reaches 0
  useEffect(() => {
    if (phase === 'recording' && countdown <= 0 && mediaRecorderRef.current?.state === 'recording') {
      doStopAndSubmit();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [countdown, phase]);

  // ── Stop recording + submit → show FeedbackTypeModal ──────
  const doStopAndSubmit = useCallback(async () => {
    if (!projectId) return;
    const recorder = mediaRecorderRef.current;
    if (!recorder || recorder.state === 'inactive') return;

    const audioBlob = await new Promise<Blob>((resolve) => {
      recorder.onstop = () => resolve(new Blob(chunksRef.current, { type: 'audio/webm' }));
      recorder.stop();
    });
    audioStreamRef.current?.getTracks().forEach((t) => t.stop());
    audioStreamRef.current = null;
    setAudioStream(null);

    setPhase('processing');
    try {
      const record = await defenseApi.submitAnswer(projectId, audioBlob, answerDuration, questionTask?.id);

      if (record.ai_feedback_text) {
        setPendingFeedbackText(record.ai_feedback_text);
        setPendingRecordId(record.id);

        if (providerRef.current === 'heygen') {
          // Show feedback type modal for heygen provider
          setPhase('feedback_modal');
          setFeedbackModalOpen(true);
        } else {
          // LiveAvatar: show text feedback directly then finish
          setPhase('feedback_text');
          setTimeout(finishDefense, 4000);
        }
      } else {
        finishDefense();
      }
    } catch {
      msg.error('提交回答失败，请重试');
      setPhase('idle');
      cleanupMedia();
    }
  }, [projectId, answerDuration, questionTask, finishDefense, cleanupMedia]);

  // ── Handle feedback type selection ────────────────────────
  const handleFeedbackTypeSelect = useCallback(async (type: 'text' | 'video') => {
    setFeedbackModalOpen(false);

    if (type === 'text') {
      // Show text feedback in a card, then finish
      setPhase('feedback_text');
      setTimeout(finishDefense, 4000);
    } else {
      // Generate feedback video
      if (!projectId || !pendingRecordId || !pendingFeedbackText) {
        finishDefense();
        return;
      }
      setPhase('feedback_video');
      try {
        const task = await defenseApi.generateFeedbackVideo(projectId, pendingRecordId, pendingFeedbackText);
        const completedTask = await pollFeedbackVideo(task.id);
        if (completedTask?.persistent_url) {
          // Play the feedback video
          await new Promise<void>((resolve) => {
            const video = videoRef.current;
            if (!video) { resolve(); return; }
            video.src = completedTask.persistent_url!;
            video.load();
            video.onended = () => resolve();
            video.onerror = () => resolve();
            video.play().catch(() => resolve());
          });
        } else {
          msg.warning('反馈视频生成失败，已保存文本反馈');
        }
        finishDefense();
      } catch {
        msg.warning('反馈视频生成失败，已保存文本反馈');
        finishDefense();
      }
    }
  }, [projectId, pendingRecordId, pendingFeedbackText, finishDefense, pollFeedbackVideo]);

  // ── Generate question video (pre-generate) ────────────────
  const handleGenerateQuestionVideo = useCallback(async () => {
    if (!projectId) return;
    try {
      const task = await defenseApi.generateQuestionVideo(projectId, {
        avatar_id: selectedCharacterId || undefined,
        voice_id: selectedVoiceId || undefined,
        avatar_type: selectedAvatarType,
        resolution,
        aspect_ratio: aspectRatio,
        expressiveness,
        remove_background: removeBackground,
        voice_locale: voiceLocale,
      });
      setQuestionTask(task);
      if (task.is_reused) {
        msg.success('复用已有视频，无需重新生成');
        setPhase('ready');
      } else if (task.status === 'completed' && task.persistent_url) {
        msg.success('复用已有视频，无需重新生成');
        setPhase('ready');
      } else {
        setPhase('generating');
        startTaskPolling(task.id);
      }
    } catch {
      msg.error('生成提问视频失败');
    }
  }, [projectId, selectedCharacterId, selectedVoiceId, selectedAvatarType, resolution, aspectRatio, expressiveness, removeBackground, voiceLocale, startTaskPolling]);

  // ── Start defense with pre-generated video (heygen) ───────
  const handleStartWithVideo = useCallback(async () => {
    if (!questionTask?.persistent_url) return;
    setPhase('speaking');
    setFullscreenVideo(true);
    // Wait for modal to mount, then play
    await new Promise<void>((resolve) => setTimeout(resolve, 300));
    await new Promise<void>((resolve) => {
      const video = fullscreenVideoRef.current;
      if (!video) { resolve(); return; }
      video.src = questionTask.persistent_url!;
      video.load();
      video.onended = () => { setFullscreenVideo(false); resolve(); };
      video.onerror = () => { setFullscreenVideo(false); resolve(); };
      video.play().catch(() => { setFullscreenVideo(false); resolve(); });
    });
    // Transition to recording
    startRecording();
  }, [questionTask, startRecording]);

  // ── Abandon defense ───────────────────────────────────────
  const handleAbandon = useCallback(() => {
    setPhase('idle');
    setQuestionTask(null);
  }, []);

  // ── Start defense (LiveAvatar flow — unchanged) ───────────
  const handleStartDefense = useCallback(async () => {
    if (!projectId) return;
    setErrorMsg(null);
    setPhase('loading');

    try {
      const qs = await defenseApi.listQuestions(projectId);
      if (!qs.length) {
        msg.warning('请先添加至少一个评委问题');
        setPhase('idle');
        return;
      }
      setQuestions(qs);

      const speechText = buildSpeechText(projectName, qs);

      // LiveAvatar streaming mode
      try {
        const { session_token } = await defenseApi.createLiveAvatarSession(projectId, selectedLiveAvatarId);
        const session = new LiveAvatarSession(session_token, { voiceChat: false });
        sessionRef.current = session;

        session.on(SessionEvent.SESSION_STATE_CHANGED, (state: SessionState) => {
          if (state === SessionState.CONNECTED) setLiveAvatarReady(true);
          if (state === SessionState.DISCONNECTED) setLiveAvatarReady(false);
        });

        session.on(SessionEvent.SESSION_STREAM_READY, () => {
          if (videoRef.current) session.attach(videoRef.current);
          setLiveAvatarReady(true);
        });

        let speakEnded = false;
        session.on(AgentEventsEnum.AVATAR_SPEAK_ENDED, () => {
          if (!speakEnded && phaseRef.current === 'speaking') {
            speakEnded = true;
            startRecording();
          }
        });

        await session.start();
        setPhase('speaking');

        // 让数字人朗读提问内容
        session.repeat(speechText);

        const fallbackMs = Math.ceil(speechText.length / 5) * 1000 + 5000;
        setTimeout(() => {
          if (!speakEnded && phaseRef.current === 'speaking') {
            speakEnded = true;
            startRecording();
          }
        }, fallbackMs);

      } catch (err) {
        console.warn('[DigitalDefense] LiveAvatar error:', err);
        setErrorMsg('LiveAvatar 服务暂时不可用，请尝试 HeyGen 模式');
        setPhase('idle');
      }
    } catch {
      msg.error('开始问辩失败，请重试');
      setPhase('idle');
    }
  }, [projectId, projectName, startRecording]);

  // ── History: toggle video playback ────────────────────────
  const handlePlayVideo = useCallback((recordId: string, type: 'question' | 'feedback') => {
    setPlayingRecordVideo((prev) =>
      prev?.recordId === recordId && prev.type === type ? null : { recordId, type },
    );
  }, []);

  const handleVideoError = useCallback((taskId: string) => {
    setVideoErrors((prev) => new Set(prev).add(taskId));
    setPlayingRecordVideo(null);
  }, []);

  const handleDeleteRecord = useCallback(async (recordId: string) => {
    if (!projectId) return;
    try {
      await defenseApi.deleteRecord(projectId, recordId);
      setRecords((prev) => prev.filter((r) => r.id !== recordId));
      msg.success('已删除');
    } catch {
      msg.error('删除失败');
    }
  }, [projectId]);

  // ── Derived state ─────────────────────────────────────────
  const selectedAvatarType = heygenCharacters.find(c => c.id === selectedCharacterId)?.avatar_type;
  const isHeygen = provider === 'heygen';
  const hasQuestions = questions.length > 0;
  const hasActiveTask = questionTask?.status === 'pending' || questionTask?.status === 'processing';
  const showGenerateBtn = isHeygen && hasQuestions;
  const showReadyButtons = isHeygen && phase === 'ready' && questionTask?.status === 'completed' && questionTask?.persistent_url;
  const showQuestionPanel = (phase === 'speaking' || phase === 'recording') && questions.length > 0;

  if (!projectId) { navigate('/'); return null; }

  return (
    <div style={{ maxWidth: 900, margin: '0 auto', padding: '24px 16px' }}>
      <BackButton to={`/projects/${projectId}`} label="返回项目" />
      <Title level={3} style={{ marginBottom: 24 }}>
        <RobotOutlined style={{ marginRight: 8 }} />
        数字人问辩
      </Title>

      {errorMsg && (
        <Alert type="warning" description={errorMsg} showIcon closable={{ closeIcon: true }} onClose={() => setErrorMsg(null)} style={{ marginBottom: 24 }} />
      )}

      {/* Provider selector */}
      <Card size="small" style={{ marginBottom: 24 }}>
        <Flex vertical gap={8}>
          <Text strong>数字人服务</Text>
          <Radio.Group
            value={provider}
            onChange={(e) => {
              setProvider(e.target.value);
              // Reset phase when switching provider to avoid stuck states
              if (phase === 'ready' || phase === 'generating') {
                setPhase('idle');
                stopTaskPolling();
              }
            }}
            disabled={phase !== 'idle' && phase !== 'ready' && phase !== 'generating'}
            optionType="button"
            buttonStyle="solid"
          >
            <Radio.Button value="liveavatar">
              <ThunderboltOutlined style={{ marginRight: 4 }} />
              LiveAvatar（实时流式）
            </Radio.Button>
            <Radio.Button value="heygen">
              <VideoCameraOutlined style={{ marginRight: 4 }} />
              HeyGen（视频生成）
            </Radio.Button>
          </Radio.Group>
          <Text type="secondary" style={{ fontSize: 12 }}>
            {provider === 'liveavatar'
              ? 'LiveAvatar 提供实时流式数字人，延迟低，交互自然'
              : 'HeyGen 生成高质量数字人视频，需等待视频渲染（约1-3分钟）'}
          </Text>
        </Flex>
      </Card>

      {/* HeyGen pre-generate section */}
      {isHeygen && (
        <Card size="small" style={{ marginBottom: 24 }}>
          <Flex vertical gap={12}>
            {/* Avatar/Voice selectors */}
            <Flex gap={12} wrap="wrap">
              <div style={{ flex: '1 1 45%', minWidth: 200 }}>
                <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>数字人形象</Text>
                <Flex gap={8}>
                  <Select
                    placeholder="默认形象"
                    value={selectedCharacterId}
                    onChange={setSelectedCharacterId}
                    allowClear
                    disabled={phase !== 'idle'}
                    loading={loadingResources}
                    style={{ flex: 1 }}
                    optionLabelProp="label"
                    virtual
                    listHeight={300}
                  >
                    {(() => {
                      const myAvatars = heygenCharacters.filter(c => c.id && c.is_custom);
                      const publicAvatars = heygenCharacters.filter(c => c.id && !c.is_custom);
                      return (
                        <>
                          {myAvatars.length > 0 && (
                            <Select.OptGroup label="我的">
                              {myAvatars.map((c, idx) => {
                                const isDefault = c.id === defaultAvatarId;
                                const label = (c.name || c.id) + (isDefault ? '（默认）' : '');
                                const typeLabel = c.avatar_type === 'photo_avatar' ? 'Photo Avatar' : 'Digital Twin';
                                return (
                                  <Select.Option key={c.id || `my-${idx}`} value={c.id} label={label}>
                                    <Flex align="center" gap={8}>
                                      {c.preview_image_url ? (
                                        <img src={c.preview_image_url} alt="" style={{ width: 32, height: 32, borderRadius: 4, objectFit: 'cover' }} loading="lazy" />
                                      ) : (
                                        <UserOutlined style={{ fontSize: 20, color: '#999' }} />
                                      )}
                                      <div>
                                        <div style={{ fontSize: 13 }}>{label}</div>
                                        <div style={{ fontSize: 11, color: '#999' }}>
                                          <Tag color={c.avatar_type === 'photo_avatar' ? 'blue' : 'purple'} style={{ fontSize: 10, lineHeight: '16px', padding: '0 4px', marginRight: 0 }}>{typeLabel}</Tag>
                                        </div>
                                      </div>
                                    </Flex>
                                  </Select.Option>
                                );
                              })}
                            </Select.OptGroup>
                          )}
                          {publicAvatars.length > 0 && (
                            <Select.OptGroup label="公共">
                              {publicAvatars.map((c, idx) => {
                                const isDefault = c.id === defaultAvatarId;
                                const label = (c.name || c.id) + (isDefault ? '（默认）' : '');
                                return (
                                  <Select.Option key={c.id || `pub-${idx}`} value={c.id} label={label}>
                                    <Flex align="center" gap={8}>
                                      {c.preview_image_url ? (
                                        <img src={c.preview_image_url} alt="" style={{ width: 32, height: 32, borderRadius: 4, objectFit: 'cover' }} loading="lazy" />
                                      ) : (
                                        <UserOutlined style={{ fontSize: 20, color: '#999' }} />
                                      )}
                                      <div>
                                        <div style={{ fontSize: 13 }}>{label}</div>
                                        <div style={{ fontSize: 11, color: '#999' }}>{c.avatar_type === 'photo_avatar' ? 'Photo Avatar' : 'Digital Twin'}</div>
                                      </div>
                                    </Flex>
                                  </Select.Option>
                                );
                              })}
                            </Select.OptGroup>
                          )}
                        </>
                      );
                    })()}
                  </Select>
                  <Button icon={<PlusOutlined />} onClick={() => setPhotoAvatarModalOpen(true)} disabled={phase !== 'idle'}>
                    创建
                  </Button>
                </Flex>
              </div>
              <div style={{ flex: '1 1 45%', minWidth: 200 }}>
                <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>语音音色</Text>
                <Select
                  placeholder="默认音色"
                  value={selectedVoiceId}
                  onChange={setSelectedVoiceId}
                  allowClear
                  disabled={phase !== 'idle'}
                  loading={loadingResources}
                  style={{ width: '100%' }}
                  showSearch
                  optionFilterProp="label"
                  virtual
                  listHeight={300}
                >
                  {(() => {
                    const myVoices = heygenVoices.filter(v => v.is_custom);
                    const publicVoices = heygenVoices.filter(v => !v.is_custom);
                    return (
                      <>
                        {myVoices.length > 0 && (
                          <Select.OptGroup label="我的">
                            {myVoices.map((v) => {
                              const isDefault = v.voice_id === defaultVoiceId;
                              const label = v.name + (isDefault ? '（默认）' : '');
                              return (
                                <Select.Option key={v.voice_id} value={v.voice_id} label={label}>
                                  <Flex align="center" gap={8}>
                                    <SoundOutlined />
                                    <div>
                                      <div style={{ fontSize: 13 }}>{label}</div>
                                      <div style={{ fontSize: 11, color: '#999' }}>{v.language} · {v.gender}</div>
                                    </div>
                                  </Flex>
                                </Select.Option>
                              );
                            })}
                          </Select.OptGroup>
                        )}
                        {publicVoices.length > 0 && (
                          <Select.OptGroup label="公共">
                            {publicVoices.map((v) => {
                              const isDefault = v.voice_id === defaultVoiceId;
                              const label = v.name + (isDefault ? '（默认）' : '');
                              return (
                                <Select.Option key={v.voice_id} value={v.voice_id} label={label}>
                                  <Flex align="center" gap={8}>
                                    <SoundOutlined />
                                    <div>
                                      <div style={{ fontSize: 13 }}>{label}</div>
                                      <div style={{ fontSize: 11, color: '#999' }}>{v.language} · {v.gender}</div>
                                    </div>
                                  </Flex>
                                </Select.Option>
                              );
                            })}
                          </Select.OptGroup>
                        )}
                      </>
                    );
                  })()}
                </Select>
              </div>
            </Flex>

            {/* Selected character preview */}
            {selectedCharacterId && (() => {
              const ch = heygenCharacters.find((c) => c.id === selectedCharacterId);
              return ch?.preview_image_url ? (
                <div style={{ textAlign: 'center' }}>
                  <Image src={ch.preview_image_url} alt={ch.name} style={{ maxHeight: 120, borderRadius: 8 }} preview={false} />
                </div>
              ) : null;
            })()}

            {/* Video options panel */}
            <Flex gap={12} wrap="wrap" align="center">
              <div>
                <Text type="secondary" style={{ fontSize: 11, display: 'block', marginBottom: 2 }}>语种</Text>
                <Select value={voiceLocale} onChange={setVoiceLocale} disabled={phase !== 'idle'} style={{ width: 120 }}>
                  <Select.Option value="zh-CN">中文</Select.Option>
                  <Select.Option value="en-US">English</Select.Option>
                  <Select.Option value="ja-JP">日本語</Select.Option>
                  <Select.Option value="ko-KR">한국어</Select.Option>
                </Select>
              </div>
              <div>
                <Text type="secondary" style={{ fontSize: 11, display: 'block', marginBottom: 2 }}>分辨率</Text>
                <Select value={resolution} onChange={setResolution} disabled={phase !== 'idle'} style={{ width: 100 }}>
                  <Select.Option value="1080p">1080p</Select.Option>
                  <Select.Option value="720p">720p</Select.Option>
                </Select>
              </div>
              <div>
                <Text type="secondary" style={{ fontSize: 11, display: 'block', marginBottom: 2 }}>宽高比</Text>
                <Select value={aspectRatio} onChange={setAspectRatio} disabled={phase !== 'idle'} style={{ width: 100 }}>
                  <Select.Option value="16:9">16:9</Select.Option>
                  <Select.Option value="9:16">9:16</Select.Option>
                </Select>
              </div>
              {selectedAvatarType === 'photo_avatar' && (
                <div>
                  <Text type="secondary" style={{ fontSize: 11, display: 'block', marginBottom: 2 }}>表情丰富度</Text>
                  <Select value={expressiveness} onChange={setExpressiveness} disabled={phase !== 'idle'} style={{ width: 100 }}>
                    <Select.Option value="low">低</Select.Option>
                    <Select.Option value="medium">中</Select.Option>
                    <Select.Option value="high">高</Select.Option>
                  </Select>
                </div>
              )}
              <div>
                <Text type="secondary" style={{ fontSize: 11, display: 'block', marginBottom: 2 }}>移除背景</Text>
                <Switch checked={removeBackground} onChange={setRemoveBackground} disabled={phase !== 'idle'} />
              </div>
            </Flex>

            <Flex align="center" gap={12} wrap="wrap">
              {showGenerateBtn && (
                <Button
                  type="primary"
                  icon={<VideoCameraOutlined />}
                  onClick={handleGenerateQuestionVideo}
                  disabled={hasActiveTask || phase !== 'idle'}
                  loading={phase === 'generating' && taskPolling}
                >
                  生成提问视频
                </Button>
              )}
              {questionTask && (
                <>
                  {questionTask.is_reused && <Tag color="cyan">已复用</Tag>}
                  <VideoTaskStatus status={questionTask.status} persistentUrl={questionTask.persistent_url} />
                </>
              )}
            </Flex>

            {/* Polling progress */}
            {taskPolling && (
              <div>
                <Progress percent={Math.round(taskProgress)} status="active" />
                <Text type="secondary" style={{ fontSize: 12 }}>提问视频生成中，请稍候…</Text>
              </div>
            )}

            {/* Ready state: start or abandon */}
            {showReadyButtons && (
              <Flex gap={12}>
                <Button type="primary" icon={<PlayCircleOutlined />} onClick={handleStartWithVideo}>
                  开始数字人问辩
                </Button>
                <Button icon={<StopOutlined />} onClick={handleAbandon}>
                  放弃此次问辩
                </Button>
              </Flex>
            )}

            {/* Outdated warning */}
            {questionTask?.status === 'outdated' && (
              <Alert type="warning" description="问题已修改，请重新生成提问视频" showIcon />
            )}
          </Flex>
        </Card>
      )}

      {/* History records */}
      <Card title="问辩记录" style={{ marginBottom: 24 }} size="small">
        {loadingRecords ? (
          <div style={{ display: 'flex', justifyContent: 'center', padding: 24 }}><Spin /></div>
        ) : records.length === 0 ? (
          <Empty description="暂无问辩记录" image={Empty.PRESENTED_IMAGE_SIMPLE} />
        ) : (
          <div>
            {records.map((record, idx) => {
              const qTask = record.question_video_task_id ? recordVideoTasks[record.question_video_task_id] : null;
              const fTask = record.feedback_video_task_id ? recordVideoTasks[record.feedback_video_task_id] : null;

              return (
                <div key={record.id} style={{ padding: '12px 0', borderBottom: idx < records.length - 1 ? '1px solid #f0f0f0' : undefined }}>
                  <Flex align="center" gap={8} wrap="wrap" style={{ marginBottom: 8 }}>
                    <Text type="secondary"><ClockCircleOutlined style={{ marginRight: 4 }} />{formatTime(record.created_at)}</Text>
                    <Tag color={record.status === 'completed' ? 'green' : 'red'}>{record.status === 'completed' ? '已完成' : '失败'}</Tag>
                    {record.feedback_type && (
                      <Tag>{record.feedback_type === 'text' ? '文本反馈' : '视频反馈'}</Tag>
                    )}
                    {qTask && <VideoTaskStatus status={qTask.status} persistentUrl={qTask.persistent_url} compact />}
                    {fTask && <VideoTaskStatus status={fTask.status} persistentUrl={fTask.persistent_url} compact />}
                  </Flex>

                  {record.questions_snapshot.length > 0 && (
                    <div style={{ marginBottom: 4 }}>
                      <Text strong>问题：</Text>
                      {[...record.questions_snapshot].sort((a, b) => a.sort_order - b.sort_order).map((q, i) => (
                        <Tag key={i} style={{ marginTop: 4 }}>{q.content}</Tag>
                      ))}
                    </div>
                  )}

                  {record.user_answer_text && (
                    <Paragraph ellipsis={{ rows: 2, expandable: true, symbol: '展开' }} style={{ marginBottom: 4 }}>
                      <Text strong>回答：</Text>{record.user_answer_text}
                    </Paragraph>
                  )}

                  {record.ai_feedback_text && (
                    <Paragraph style={{ marginBottom: 4 }}>
                      <Text strong>反馈：</Text><Text type="success">{record.ai_feedback_text}</Text>
                    </Paragraph>
                  )}

                  {/* Video playback buttons */}
                  <Flex gap={8} wrap="wrap" style={{ marginTop: 8 }}>
                    {qTask?.status === 'completed' && qTask.persistent_url && !videoErrors.has(qTask.id) && (
                      <Button
                        size="small"
                        icon={<PlayCircleOutlined />}
                        onClick={() => handlePlayVideo(record.id, 'question')}
                      >
                        {playingRecordVideo?.recordId === record.id && playingRecordVideo.type === 'question' ? '收起视频' : '播放提问视频'}
                      </Button>
                    )}
                    {qTask && videoErrors.has(qTask.id) && (
                      <Text type="danger" style={{ fontSize: 12 }}>视频链接已失效</Text>
                    )}

                    {fTask?.status === 'completed' && fTask.persistent_url && !videoErrors.has(fTask.id) && (
                      <Button
                        size="small"
                        icon={<PlayCircleOutlined />}
                        onClick={() => handlePlayVideo(record.id, 'feedback')}
                      >
                        {playingRecordVideo?.recordId === record.id && playingRecordVideo.type === 'feedback' ? '收起视频' : '播放反馈视频'}
                      </Button>
                    )}
                    {fTask && videoErrors.has(fTask.id) && (
                      <Text type="danger" style={{ fontSize: 12 }}>视频链接已失效</Text>
                    )}

                    <Popconfirm title="确定删除这条记录？" onConfirm={() => handleDeleteRecord(record.id)} okText="删除" cancelText="取消">
                      <Button size="small" danger icon={<DeleteOutlined />}>删除</Button>
                    </Popconfirm>
                  </Flex>

                  {/* Inline video player */}
                  {playingRecordVideo?.recordId === record.id && (() => {
                    const task = playingRecordVideo.type === 'question' ? qTask : fTask;
                    return task?.persistent_url ? (
                      <div style={{ marginTop: 8 }}>
                        <video
                          src={task.persistent_url}
                          controls
                          autoPlay
                          style={{ width: '100%', maxWidth: 480, borderRadius: 8, background: '#000' }}
                          onError={() => handleVideoError(task.id)}
                        />
                      </div>
                    ) : null;
                  })()}
                </div>
              );
            })}
          </div>
        )}
      </Card>

      {/* Settings */}
      <Card size="small" style={{ marginBottom: 24 }}>
        <Flex align="center" gap={8}>
          <Text>回答时长：</Text>
          <InputNumber value={answerDuration} onChange={(v) => setAnswerDuration(v ?? 30)} min={10} max={120} step={5} suffix="秒" disabled={phase !== 'idle'} style={{ width: 140 }} />
        </Flex>
      </Card>

      {/* Start button — LiveAvatar only */}
      {provider === 'liveavatar' && (
        <>
          {/* LiveAvatar avatar selector */}
          {liveAvatarList.length > 0 && (
            <Card size="small" style={{ marginBottom: 16 }}>
              <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>选择数字人形象</Text>
              <Select
                placeholder="默认数字人"
                value={selectedLiveAvatarId}
                onChange={setSelectedLiveAvatarId}
                allowClear
                disabled={phase !== 'idle'}
                loading={loadingResources}
                style={{ width: '100%', maxWidth: 400 }}
                optionLabelProp="label"
              >
                {liveAvatarList.map((a) => (
                  <Select.Option key={a.id} value={a.id} label={a.name || a.id}>
                    <Flex align="center" gap={8}>
                      {a.preview_image_url ? (
                        <img src={a.preview_image_url} alt="" style={{ width: 32, height: 32, borderRadius: 4, objectFit: 'cover' }} />
                      ) : (
                        <UserOutlined style={{ fontSize: 20, color: '#999' }} />
                      )}
                      <span>{a.name || a.id}</span>
                    </Flex>
                  </Select.Option>
                ))}
              </Select>
            </Card>
          )}
          <Button
            type="primary" size="large" icon={<SoundOutlined />}
            onClick={handleStartDefense}
            disabled={phase !== 'idle' || !!errorMsg}
            loading={phase === 'loading'}
            block style={{ marginBottom: 24 }}
          >
            开始问辩
          </Button>
        </>
      )}

      {/* Video / Avatar area + QuestionPanel side-by-side */}
      {phase !== 'idle' && phase !== 'done' && phase !== 'generating' && phase !== 'ready' && phase !== 'feedback_modal' && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 16, marginBottom: 24 }}>
          {/* Video area */}
          <div style={{ flex: '1 1 58%', minWidth: 300 }}>
            <Card style={{ textAlign: 'center' }}>
              <video
                ref={videoRef}
                autoPlay playsInline
                style={{
                  width: '100%', maxWidth: 480, borderRadius: 8, background: '#000',
                  display: (liveAvatarReady || phase === 'speaking' || phase === 'feedback_video') ? 'block' : 'none',
                  margin: '0 auto',
                }}
              />

              {/* Loading state */}
              {phase === 'loading' && (
                <div style={{ padding: 40 }}>
                  <Spin size="large" />
                  <div style={{ marginTop: 16 }}>
                    <Text type="secondary">
                      {provider === 'heygen' ? '正在准备数字人视频…' : '数字人评委正在入场…'}
                    </Text>
                  </div>
                </div>
              )}

              {/* Speaking indicator */}
              {phase === 'speaking' && (
                <div style={{ marginTop: 12 }}>
                  <Tag icon={<SoundOutlined />} color="processing">数字人评委正在提问…</Tag>
                </div>
              )}

              {/* Feedback video polling progress */}
              {phase === 'feedback_video' && feedbackVideoPolling && (
                <div style={{ padding: 16 }}>
                  <Progress percent={Math.round(feedbackVideoProgress)} status="active" />
                  <Text type="secondary" style={{ marginTop: 8, display: 'block' }}>反馈视频生成中…</Text>
                </div>
              )}

              {/* Feedback text display */}
              {phase === 'feedback_text' && pendingFeedbackText && (
                <Card size="small" style={{ marginTop: 12, textAlign: 'left' }}>
                  <Text strong>AI 评委反馈：</Text>
                  <Paragraph style={{ marginTop: 8, marginBottom: 0 }}>
                    <Text type="success">{pendingFeedbackText}</Text>
                  </Paragraph>
                </Card>
              )}

              {/* Feedback video indicator (non-polling) */}
              {phase === 'feedback_video' && !feedbackVideoPolling && (
                <div style={{ marginTop: 12 }}>
                  <Tag icon={<RobotOutlined />} color="processing">数字人评委正在给出反馈…</Tag>
                </div>
              )}

              {/* Processing */}
              {phase === 'processing' && (
                <div style={{ padding: 24 }}>
                  <Spin size="large" />
                  <div style={{ marginTop: 16 }}><Text type="secondary">正在处理回答，请稍候…</Text></div>
                </div>
              )}
            </Card>

            {/* Recording controls */}
            {phase === 'recording' && (
              <Card style={{ marginTop: 16, textAlign: 'center' }}>
                <AudioOutlined style={{ fontSize: 32, color: '#f5222d', marginBottom: 16 }} />
                <div style={{ fontSize: 48, fontWeight: 700, color: countdown <= 5 ? '#f5222d' : '#1677ff', marginBottom: 16, fontVariantNumeric: 'tabular-nums' }}>
                  {countdown}
                </div>
                <Text type="secondary">正在录音，请回答评委问题</Text>
                <div style={{ marginTop: 16 }}><AudioWaveform stream={audioStream} height={60} /></div>
                <Button type="primary" danger onClick={doStopAndSubmit} style={{ marginTop: 16 }}>
                  提前结束回答
                </Button>
              </Card>
            )}
          </div>

          {/* Question panel — side panel */}
          {showQuestionPanel && (
            <div style={{ flex: '1 1 38%', minWidth: 260 }}>
              <QuestionPanel questions={questions.map((q) => ({ content: q.content, sort_order: q.sort_order }))} />
            </div>
          )}
        </div>
      )}

      {/* Done */}
      {phase === 'done' && (
        <Result status="success" title="问辩完成" subTitle="评委反馈已记录，可在上方查看历史记录" style={{ marginBottom: 24 }} />
      )}

      {/* Feedback type modal */}
      <FeedbackTypeModal open={feedbackModalOpen} onSelect={handleFeedbackTypeSelect} />

      {/* Fullscreen video playback modal (HeyGen) */}
      <Modal
        open={fullscreenVideo}
        footer={null}
        closable={false}
        centered
        width="100vw"
        styles={{
          body: { padding: 0, background: '#000', overflow: 'hidden', height: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center' },
          content: { padding: 0, borderRadius: 0, background: '#000', maxWidth: '100vw', top: 0 },
          wrapper: { overflow: 'hidden' },
        }}
        style={{ top: 0, padding: 0, maxWidth: '100vw' }}
        destroyOnHidden
      >
        <div style={{ position: 'relative', width: '100vw', height: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#000' }}>
          <video
            ref={fullscreenVideoRef}
            autoPlay
            playsInline
            style={{ maxWidth: '100%', maxHeight: '100%', objectFit: 'contain' }}
          />
          <div style={{ position: 'absolute', bottom: 32, left: '50%', transform: 'translateX(-50%)' }}>
            <Tag icon={<SoundOutlined />} color="processing" style={{ fontSize: 16, padding: '6px 16px' }}>
              数字人评委正在提问…
            </Tag>
          </div>
        </div>
      </Modal>

      {/* Photo Avatar creation modal */}
      <Modal
        title="创建 Photo Avatar"
        open={photoAvatarModalOpen}
        onCancel={() => { setPhotoAvatarModalOpen(false); photoAvatarForm.resetFields(); }}
        onOk={() => photoAvatarForm.submit()}
        confirmLoading={photoAvatarCreating}
        okText="创建"
        cancelText="取消"
        destroyOnHidden
      >
        <Alert
          type="info"
          description="如需效果更好的 Digital Twin，请前往 HeyGen 官网创建"
          showIcon
          style={{ marginBottom: 16 }}
        />
        <Form
          form={photoAvatarForm}
          layout="vertical"
          onFinish={async (values: PhotoAvatarCreateParams) => {
            if (!projectId) return;
            setPhotoAvatarCreating(true);
            try {
              const { generation_id } = await defenseApi.createPhotoAvatar(projectId, values);
              msg.success('Photo Avatar 创建请求已提交');
              setPhotoAvatarModalOpen(false);
              photoAvatarForm.resetFields();
              // Poll for creation status
              const pollStatus = async () => {
                let attempts = 0;
                const maxAttempts = 120;
                const interval = setInterval(async () => {
                  attempts++;
                  try {
                    const res = await defenseApi.checkPhotoAvatarStatus(projectId, generation_id);
                    if (res.status === 'completed') {
                      clearInterval(interval);
                      msg.success('Photo Avatar 创建完成，请刷新页面查看');
                    } else if (res.status === 'failed') {
                      clearInterval(interval);
                      msg.error('Photo Avatar 创建失败');
                    }
                  } catch { /* continue */ }
                  if (attempts >= maxAttempts) {
                    clearInterval(interval);
                    msg.warning('Photo Avatar 创建超时，请稍后手动查询');
                  }
                }, 5000);
              };
              pollStatus();
            } catch {
              msg.error('创建 Photo Avatar 失败');
            } finally {
              setPhotoAvatarCreating(false);
            }
          }}
        >
          <Form.Item name="name" label="名称" rules={[{ required: true, message: '请输入名称' }]}>
            <Input placeholder="输入 Avatar 名称" />
          </Form.Item>
          <Flex gap={12} wrap="wrap">
            <Form.Item name="age" label="年龄段" rules={[{ required: true, message: '请选择' }]} style={{ flex: 1, minWidth: 140 }}>
              <Select placeholder="选择年龄段">
                <Select.Option value="Young Adult">青年</Select.Option>
                <Select.Option value="Early Middle Age">中年前期</Select.Option>
                <Select.Option value="Late Middle Age">中年后期</Select.Option>
                <Select.Option value="Senior">老年</Select.Option>
                <Select.Option value="Unspecified">不指定</Select.Option>
              </Select>
            </Form.Item>
            <Form.Item name="gender" label="性别" rules={[{ required: true, message: '请选择' }]} style={{ flex: 1, minWidth: 140 }}>
              <Select placeholder="选择性别">
                <Select.Option value="Woman">女</Select.Option>
                <Select.Option value="Man">男</Select.Option>
                <Select.Option value="Unspecified">不指定</Select.Option>
              </Select>
            </Form.Item>
          </Flex>
          <Form.Item name="ethnicity" label="种族" rules={[{ required: true, message: '请输入种族' }]}>
            <Input placeholder="如：Asian, Caucasian 等" />
          </Form.Item>
          <Flex gap={12} wrap="wrap">
            <Form.Item name="orientation" label="朝向" rules={[{ required: true, message: '请选择' }]} style={{ flex: 1, minWidth: 120 }}>
              <Select placeholder="选择朝向">
                <Select.Option value="square">正面</Select.Option>
                <Select.Option value="horizontal">水平</Select.Option>
                <Select.Option value="vertical">垂直</Select.Option>
              </Select>
            </Form.Item>
            <Form.Item name="pose" label="姿势" rules={[{ required: true, message: '请选择' }]} style={{ flex: 1, minWidth: 120 }}>
              <Select placeholder="选择姿势">
                <Select.Option value="half_body">半身</Select.Option>
                <Select.Option value="close_up">特写</Select.Option>
                <Select.Option value="full_body">全身</Select.Option>
              </Select>
            </Form.Item>
            <Form.Item name="style" label="风格" rules={[{ required: true, message: '请选择' }]} style={{ flex: 1, minWidth: 120 }}>
              <Select placeholder="选择风格">
                <Select.Option value="Realistic">写实</Select.Option>
                <Select.Option value="Pixar">Pixar</Select.Option>
                <Select.Option value="Cinematic">电影</Select.Option>
                <Select.Option value="Vintage">复古</Select.Option>
                <Select.Option value="Noir">黑色</Select.Option>
                <Select.Option value="Cyberpunk">赛博朋克</Select.Option>
                <Select.Option value="Unspecified">不指定</Select.Option>
              </Select>
            </Form.Item>
          </Flex>
          <Form.Item name="appearance" label="外观描述" rules={[{ required: true, message: '请输入外观描述' }, { max: 1000, message: '最多 1000 字符' }]}>
            <Input.TextArea rows={3} placeholder="描述 Avatar 的外观特征（最多 1000 字符）" maxLength={1000} showCount />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
