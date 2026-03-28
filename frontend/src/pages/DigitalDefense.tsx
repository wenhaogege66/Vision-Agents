import { useEffect, useRef, useState, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Card,
  Button,
  InputNumber,
  Typography,
  Space,
  Tag,
  Spin,
  Empty,
  Result,
  Radio,
  Alert,
  Progress,
  Flex,
} from 'antd';
import {
  SoundOutlined,
  AudioOutlined,
  RobotOutlined,
  ClockCircleOutlined,
  VideoCameraOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons';
import { LiveAvatarSession, SessionEvent, SessionState, AgentEventsEnum } from '@heygen/liveavatar-web-sdk';
import BackButton from '@/components/BackButton';
import AudioWaveform from '@/components/AudioWaveform';
import { defenseApi, projectApi } from '@/services/api';
import { msg } from '@/utils/messageHolder';
import type { DefenseRecord } from '@/types';

const { Title, Text, Paragraph } = Typography;

type AvatarProvider = 'liveavatar' | 'heygen';
type Phase = 'idle' | 'loading' | 'speaking' | 'recording' | 'processing' | 'feedback' | 'done';

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

  const [provider, setProvider] = useState<AvatarProvider>('liveavatar');
  const [phase, setPhase] = useState<Phase>('idle');
  const [countdown, setCountdown] = useState(0);
  const [answerDuration, setAnswerDuration] = useState(30);
  const [records, setRecords] = useState<DefenseRecord[]>([]);
  const [projectName, setProjectName] = useState('');
  const [loadingRecords, setLoadingRecords] = useState(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // HeyGen video state
  const [heygenVideoUrl, setHeygenVideoUrl] = useState<string | null>(null);
  const [heygenPolling, setHeygenPolling] = useState(false);
  const [heygenProgress, setHeygenProgress] = useState(0);

  // LiveAvatar state
  const sessionRef = useRef<LiveAvatarSession | null>(null);
  const [liveAvatarReady, setLiveAvatarReady] = useState(false);

  // Media refs
  const videoRef = useRef<HTMLVideoElement>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioStreamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const countdownTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const [audioStream, setAudioStream] = useState<MediaStream | null>(null);

  // Use refs for callbacks that need latest state without re-creating
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

  useEffect(() => {
    if (!projectId) return;
    projectApi.get(projectId).then((res) => setProjectName(res.data.name)).catch(() => {});
    loadRecords();
  }, [projectId, loadRecords]);

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
    sessionRef.current?.stop().catch(() => {});
  }, [cleanupMedia]);

  // ── HeyGen: poll video status ─────────────────────────────
  const pollHeyGenVideo = useCallback(async (videoId: string): Promise<string | null> => {
    if (!projectId) return null;
    setHeygenPolling(true);
    setHeygenProgress(5);
    const maxAttempts = 60;
    for (let i = 0; i < maxAttempts; i++) {
      await new Promise((r) => setTimeout(r, 5000));
      setHeygenProgress(Math.min(5 + ((i + 1) / maxAttempts) * 90, 95));
      try {
        const result = await defenseApi.checkHeyGenVideoStatus(projectId, videoId);
        if (result.status === 'completed' && result.video_url) {
          setHeygenProgress(100);
          setHeygenPolling(false);
          return result.video_url;
        }
        if (result.status === 'failed') {
          setHeygenPolling(false);
          return null;
        }
        // processing / pending → continue polling
      } catch {
        // network error → continue polling
      }
    }
    setHeygenPolling(false);
    return null;
  }, [projectId]);

  // ── HeyGen: generate + poll + play video ──────────────────
  const heygenSpeak = useCallback(async (text: string): Promise<boolean> => {
    if (!projectId) return false;
    try {
      setHeygenPolling(true);
      setHeygenProgress(0);
      const { video_id } = await defenseApi.generateHeyGenVideo(projectId, text);
      const url = await pollHeyGenVideo(video_id);
      if (!url) {
        msg.warning('HeyGen 视频生成失败');
        return false;
      }
      setHeygenVideoUrl(url);
      // Play video and wait for it to finish
      return await new Promise<boolean>((resolve) => {
        const video = videoRef.current;
        if (!video) { resolve(false); return; }
        video.src = url;
        video.load();
        video.onended = () => resolve(true);
        video.onerror = () => resolve(false);
        video.play().catch(() => resolve(false));
      });
    } catch {
      msg.warning('HeyGen 视频生成失败');
      return false;
    }
  }, [projectId, pollHeyGenVideo]);

  // ── Finish defense ────────────────────────────────────────
  const finishDefense = useCallback(() => {
    setPhase('done');
    setHeygenVideoUrl(null);
    setHeygenPolling(false);
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
          // Will call stopRecordingAndSubmit via effect or inline
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

  // ── Stop recording + submit + feedback ────────────────────
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
      const record = await defenseApi.submitAnswer(projectId, audioBlob, answerDuration);

      if (record.ai_feedback_text) {
        setPhase('feedback');

        if (providerRef.current === 'heygen') {
          // Generate HeyGen feedback video
          const played = await heygenSpeak(record.ai_feedback_text);
          if (!played) {
            // Video failed but we still have text feedback, show briefly then finish
            await new Promise((r) => setTimeout(r, 3000));
          }
          finishDefense();
        } else {
          // LiveAvatar or fallback: show text feedback for a few seconds
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
  }, [projectId, answerDuration, heygenSpeak, finishDefense, cleanupMedia]);

  // ── Start defense ─────────────────────────────────────────
  const handleStartDefense = useCallback(async () => {
    if (!projectId) return;
    setErrorMsg(null);
    setPhase('loading');
    setHeygenVideoUrl(null);

    try {
      const questions = await defenseApi.listQuestions(projectId);
      if (!questions.length) {
        msg.warning('请先添加至少一个评委问题');
        setPhase('idle');
        return;
      }

      const speechText = buildSpeechText(projectName, questions);

      if (provider === 'heygen') {
        setPhase('speaking');
        const played = await heygenSpeak(speechText);
        if (!played) {
          msg.warning('视频生成失败，直接进入录音');
        }
        startRecording();
      } else {
        // LiveAvatar streaming mode
        try {
          const { session_token } = await defenseApi.createLiveAvatarSession(projectId);
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

          // Fallback timeout
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
      }
    } catch {
      msg.error('开始问辩失败，请重试');
      setPhase('idle');
    }
  }, [projectId, projectName, provider, heygenSpeak, startRecording]);

  if (!projectId) { navigate('/'); return null; }

  return (
    <div style={{ maxWidth: 800, margin: '0 auto', padding: '24px 16px' }}>
      <BackButton to={`/projects/${projectId}`} label="返回项目" />
      <Title level={3} style={{ marginBottom: 24 }}>
        <RobotOutlined style={{ marginRight: 8 }} />
        数字人问辩
      </Title>

      {errorMsg && (
        <Alert type="warning" message={errorMsg} showIcon closable onClose={() => setErrorMsg(null)} style={{ marginBottom: 24 }} />
      )}

      {/* Provider selector */}
      <Card size="small" style={{ marginBottom: 24 }}>
        <Flex vertical gap={8}>
          <Text strong>数字人服务</Text>
          <Radio.Group
            value={provider}
            onChange={(e) => setProvider(e.target.value)}
            disabled={phase !== 'idle'}
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

      {/* History records */}
      <Card title="问辩记录" style={{ marginBottom: 24 }} size="small">
        {loadingRecords ? (
          <div style={{ display: 'flex', justifyContent: 'center', padding: 24 }}><Spin /></div>
        ) : records.length === 0 ? (
          <Empty description="暂无问辩记录" image={Empty.PRESENTED_IMAGE_SIMPLE} />
        ) : (
          <div>
            {records.map((record, idx) => (
              <div key={record.id} style={{ padding: '12px 0', borderBottom: idx < records.length - 1 ? '1px solid #f0f0f0' : undefined }}>
                <Space style={{ marginBottom: 8 }}>
                  <Text type="secondary"><ClockCircleOutlined style={{ marginRight: 4 }} />{formatTime(record.created_at)}</Text>
                  <Tag color={record.status === 'completed' ? 'green' : 'red'}>{record.status === 'completed' ? '已完成' : '失败'}</Tag>
                </Space>
                {record.questions_snapshot.length > 0 && (
                  <div style={{ marginBottom: 4 }}>
                    <Text strong>问题：</Text>
                    {record.questions_snapshot.sort((a, b) => a.sort_order - b.sort_order).map((q, i) => (
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
                  <Paragraph style={{ marginBottom: 0 }}>
                    <Text strong>反馈：</Text><Text type="success">{record.ai_feedback_text}</Text>
                  </Paragraph>
                )}
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* Settings */}
      <Card size="small" style={{ marginBottom: 24 }}>
        <Space>
          <Text>回答时长：</Text>
          <InputNumber value={answerDuration} onChange={(v) => setAnswerDuration(v ?? 30)} min={10} max={120} step={5} suffix="秒" disabled={phase !== 'idle'} style={{ width: 140 }} />
        </Space>
      </Card>

      {/* Start button */}
      <Button
        type="primary" size="large" icon={<SoundOutlined />}
        onClick={handleStartDefense}
        disabled={phase !== 'idle' || !!errorMsg}
        loading={phase === 'loading'}
        block style={{ marginBottom: 24 }}
      >
        开始问辩
      </Button>

      {/* Video / Avatar area */}
      {phase !== 'idle' && phase !== 'done' && (
        <Card style={{ marginBottom: 24, textAlign: 'center' }}>
          <video
            ref={videoRef}
            autoPlay playsInline
            style={{
              width: '100%', maxWidth: 480, borderRadius: 8, background: '#000',
              display: (heygenVideoUrl || liveAvatarReady) ? 'block' : 'none',
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

          {/* HeyGen polling progress */}
          {(phase === 'speaking' || phase === 'feedback') && heygenPolling && (
            <div style={{ padding: 16 }}>
              <Progress percent={Math.round(heygenProgress)} status="active" />
              <Text type="secondary" style={{ marginTop: 8, display: 'block' }}>
                {phase === 'speaking' ? 'HeyGen 提问视频渲染中…' : 'HeyGen 反馈视频渲染中…'}
              </Text>
            </div>
          )}

          {/* Speaking indicator (non-polling) */}
          {phase === 'speaking' && !heygenPolling && (
            <div style={{ marginTop: 12 }}>
              <Tag icon={<SoundOutlined />} color="processing">数字人评委正在提问…</Tag>
            </div>
          )}

          {/* Feedback indicator (non-polling) */}
          {phase === 'feedback' && !heygenPolling && (
            <div style={{ marginTop: 12 }}>
              <Tag icon={<RobotOutlined />} color="processing">数字人评委正在给出反馈…</Tag>
            </div>
          )}
        </Card>
      )}

      {/* Recording */}
      {phase === 'recording' && (
        <Card style={{ marginBottom: 24, textAlign: 'center' }}>
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

      {/* Processing */}
      {phase === 'processing' && (
        <Card style={{ marginBottom: 24, textAlign: 'center', padding: 24 }}>
          <Spin size="large" />
          <div style={{ marginTop: 16 }}><Text type="secondary">正在处理回答，请稍候…</Text></div>
        </Card>
      )}

      {/* Done */}
      {phase === 'done' && (
        <Result status="success" title="问辩完成" subTitle="评委反馈已记录，可在上方查看历史记录" style={{ marginBottom: 24 }} />
      )}
    </div>
  );
}
