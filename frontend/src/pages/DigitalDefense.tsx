import { useEffect, useRef, useState, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Card,
  Button,
  InputNumber,
  Typography,
  Space,
  List,
  Tag,
  Spin,
  Empty,
  Result,
} from 'antd';
import {
  SoundOutlined,
  AudioOutlined,
  RobotOutlined,
  ClockCircleOutlined,
} from '@ant-design/icons';
import StreamingAvatar, {
  AvatarQuality,
  StreamingEvents,
  TaskType,
} from '@heygen/streaming-avatar';
import BackButton from '@/components/BackButton';
import AudioWaveform from '@/components/AudioWaveform';
import { defenseApi, projectApi } from '@/services/api';
import { msg } from '@/utils/messageHolder';
import type { DefenseRecord } from '@/types';

const { Title, Text, Paragraph } = Typography;

type Phase = 'idle' | 'loading' | 'speaking' | 'recording' | 'processing' | 'feedback' | 'done';

const ORDINALS = ['第一', '第二', '第三', '第四', '第五', '第六', '第七', '第八', '第九', '第十'];

/** Estimate speech duration for Chinese text (~5 chars/sec) + 2s buffer */
function estimateSpeechDuration(text: string): number {
  return Math.ceil(text.length / 5) * 1000 + 2000;
}

function formatTime(dateStr: string): string {
  return new Date(dateStr).toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export default function DigitalDefense() {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();

  // Core state machine
  const [phase, setPhase] = useState<Phase>('idle');
  const [avatarReady, setAvatarReady] = useState(false);
  const [countdown, setCountdown] = useState(0);
  const [answerDuration, setAnswerDuration] = useState(30);
  const [records, setRecords] = useState<DefenseRecord[]>([]);
  const [projectName, setProjectName] = useState('');
  const [loadingRecords, setLoadingRecords] = useState(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Refs for SDK and media
  const avatarRef = useRef<StreamingAvatar | null>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioStreamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const countdownTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const speakTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Audio stream for waveform visualization
  const [audioStream, setAudioStream] = useState<MediaStream | null>(null);

  // ── Load project name + records on mount ──────────────────────
  const loadRecords = useCallback(async () => {
    if (!projectId) return;
    try {
      const data = await defenseApi.listRecords(projectId);
      setRecords(data);
    } catch {
      // handled by axios interceptor
    } finally {
      setLoadingRecords(false);
    }
  }, [projectId]);

  useEffect(() => {
    if (!projectId) return;

    projectApi.get(projectId).then((res) => {
      setProjectName(res.data.name);
    }).catch(() => {});

    loadRecords();
  }, [projectId, loadRecords]);

  // ── Initialize HeyGen Avatar on mount ─────────────────────────
  useEffect(() => {
    if (!projectId) return;

    let avatar: StreamingAvatar | null = null;
    let cancelled = false;

    const initAvatar = async () => {
      try {
        const { token } = await defenseApi.getToken(projectId);
        if (cancelled) return;

        avatar = new StreamingAvatar({ token });
        avatarRef.current = avatar;

        avatar.on(StreamingEvents.STREAM_READY, (event: { detail: MediaStream }) => {
          setAvatarReady(true);
          if (videoRef.current && event.detail) {
            videoRef.current.srcObject = event.detail;
            videoRef.current.play().catch(() => {});
          }
        });

        avatar.on(StreamingEvents.STREAM_DISCONNECTED, () => {
          setAvatarReady(false);
          if (phase !== 'idle' && phase !== 'done') {
            msg.warning('数字人连接已断开');
            setPhase('idle');
          }
        });

        await avatar.createStartAvatar({
          quality: AvatarQuality.High,
          avatarName: '80d4afa941c243beb0a1116c95ea48ee',
        });
      } catch {
        if (!cancelled) {
          setErrorMsg('数字人服务暂时不可用，请稍后重试');
        }
      }
    };

    initAvatar();

    return () => {
      cancelled = true;
      avatar?.stopAvatar().catch(() => {});
      avatarRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  // ── beforeunload cleanup ──────────────────────────────────────
  useEffect(() => {
    const handleBeforeUnload = () => {
      avatarRef.current?.stopAvatar().catch(() => {});
    };
    window.addEventListener('beforeunload', handleBeforeUnload);
    return () => window.removeEventListener('beforeunload', handleBeforeUnload);
  }, []);

  // ── Cleanup media resources helper ────────────────────────────
  const cleanupMedia = useCallback(() => {
    if (countdownTimerRef.current) {
      clearInterval(countdownTimerRef.current);
      countdownTimerRef.current = null;
    }
    if (speakTimeoutRef.current) {
      clearTimeout(speakTimeoutRef.current);
      speakTimeoutRef.current = null;
    }
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop();
    }
    mediaRecorderRef.current = null;
    if (audioStreamRef.current) {
      audioStreamRef.current.getTracks().forEach((t) => t.stop());
      audioStreamRef.current = null;
    }
    setAudioStream(null);
    chunksRef.current = [];
  }, []);

  // ── Start recording ───────────────────────────────────────────
  const startRecording = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      audioStreamRef.current = stream;
      setAudioStream(stream);

      const recorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
      mediaRecorderRef.current = recorder;
      chunksRef.current = [];

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };

      recorder.start();
      setPhase('recording');

      // Start countdown
      let remaining = answerDuration;
      setCountdown(remaining);

      countdownTimerRef.current = setInterval(() => {
        remaining -= 1;
        setCountdown(remaining);
        if (remaining <= 0) {
          clearInterval(countdownTimerRef.current!);
          countdownTimerRef.current = null;
          stopRecordingAndSubmit();
        }
      }, 1000);
    } catch {
      msg.warning('请允许麦克风权限以进行回答录音');
      setPhase('idle');
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [answerDuration, projectId]);

  // ── Stop recording and submit ─────────────────────────────────
  const stopRecordingAndSubmit = useCallback(async () => {
    if (!projectId) return;

    const recorder = mediaRecorderRef.current;
    if (!recorder || recorder.state === 'inactive') return;

    // Wait for the recorder to finish
    const audioBlob = await new Promise<Blob>((resolve) => {
      recorder.onstop = () => {
        resolve(new Blob(chunksRef.current, { type: 'audio/webm' }));
      };
      recorder.stop();
    });

    // Cleanup media tracks
    if (audioStreamRef.current) {
      audioStreamRef.current.getTracks().forEach((t) => t.stop());
      audioStreamRef.current = null;
    }
    setAudioStream(null);

    setPhase('processing');

    try {
      const record = await defenseApi.submitAnswer(projectId, audioBlob, answerDuration);

      if (record.ai_feedback_text) {
        setPhase('feedback');

        const avatar = avatarRef.current;
        if (avatar && avatarReady) {
          // Listen for stop talking event
          const onStopTalking = () => {
            avatar.off(StreamingEvents.AVATAR_STOP_TALKING, onStopTalking);
            finishDefense();
          };
          avatar.on(StreamingEvents.AVATAR_STOP_TALKING, onStopTalking);

          await avatar.speak({
            text: record.ai_feedback_text,
            task_type: TaskType.REPEAT,
          });

          // Fallback timeout in case event doesn't fire
          speakTimeoutRef.current = setTimeout(() => {
            avatar.off(StreamingEvents.AVATAR_STOP_TALKING, onStopTalking);
            finishDefense();
          }, estimateSpeechDuration(record.ai_feedback_text));
        } else {
          // Avatar not available, just show feedback
          setTimeout(finishDefense, 3000);
        }
      } else {
        finishDefense();
      }
    } catch {
      msg.error('提交回答失败，请重试');
      setPhase('idle');
      cleanupMedia();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId, answerDuration, avatarReady, cleanupMedia]);

  // ── Finish defense session ────────────────────────────────────
  const finishDefense = useCallback(() => {
    setPhase('done');
    loadRecords();
    // Reset to idle after a short delay
    setTimeout(() => setPhase('idle'), 3000);
  }, [loadRecords]);

  // ── Start defense flow ────────────────────────────────────────
  const handleStartDefense = useCallback(async () => {
    if (!projectId) return;
    setErrorMsg(null);
    setPhase('loading');

    try {
      if (!avatarReady) {
        msg.info('数字人评委正在入场…');
      }

      const questions = await defenseApi.listQuestions(projectId);
      if (!questions.length) {
        msg.warning('请先添加至少一个评委问题');
        setPhase('idle');
        return;
      }

      // Build speech text
      const sorted = [...questions].sort((a, b) => a.sort_order - b.sort_order);
      const qParts = sorted.map((q, i) => {
        const ord = ORDINALS[i] ?? `第${i + 1}`;
        return `${ord}，${q.content}`;
      });
      const speechText = `你好，我是数字人评委，对于你们的${projectName}项目，我有以下${sorted.length}个问题：${qParts.join('；')}`;

      const avatar = avatarRef.current;
      if (!avatar) {
        msg.error('数字人服务未就绪，请刷新页面重试');
        setPhase('idle');
        return;
      }

      setPhase('speaking');

      // Listen for avatar stop talking to start recording
      const onStopTalking = () => {
        avatar.off(StreamingEvents.AVATAR_STOP_TALKING, onStopTalking);
        if (speakTimeoutRef.current) {
          clearTimeout(speakTimeoutRef.current);
          speakTimeoutRef.current = null;
        }
        startRecording();
      };
      avatar.on(StreamingEvents.AVATAR_STOP_TALKING, onStopTalking);

      await avatar.speak({
        text: speechText,
        task_type: TaskType.REPEAT,
      });

      // Fallback timeout in case event doesn't fire
      speakTimeoutRef.current = setTimeout(() => {
        avatar.off(StreamingEvents.AVATAR_STOP_TALKING, onStopTalking);
        startRecording();
      }, estimateSpeechDuration(speechText));
    } catch {
      msg.error('开始问辩失败，请重试');
      setPhase('idle');
    }
  }, [projectId, projectName, avatarReady, startRecording]);

  // ── Retry avatar connection ───────────────────────────────────
  const handleRetry = useCallback(async () => {
    if (!projectId) return;
    setErrorMsg(null);

    try {
      const { token } = await defenseApi.getToken(projectId);
      const avatar = new StreamingAvatar({ token });
      avatarRef.current = avatar;

      avatar.on(StreamingEvents.STREAM_READY, (event: { detail: MediaStream }) => {
        setAvatarReady(true);
        if (videoRef.current && event.detail) {
          videoRef.current.srcObject = event.detail;
          videoRef.current.play().catch(() => {});
        }
      });

      avatar.on(StreamingEvents.STREAM_DISCONNECTED, () => {
        setAvatarReady(false);
      });

      await avatar.createStartAvatar({
        quality: AvatarQuality.High,
        avatarName: '80d4afa941c243beb0a1116c95ea48ee',
      });
    } catch {
      setErrorMsg('数字人服务暂时不可用，请稍后重试');
    }
  }, [projectId]);

  // ── Cleanup on unmount ────────────────────────────────────────
  useEffect(() => {
    return () => {
      cleanupMedia();
    };
  }, [cleanupMedia]);

  if (!projectId) {
    navigate('/');
    return null;
  }

  // ── Render ────────────────────────────────────────────────────
  return (
    <div style={{ maxWidth: 800, margin: '0 auto', padding: '24px 16px' }}>
      <BackButton to={`/projects/${projectId}`} label="返回项目" />
      <Title level={3} style={{ marginBottom: 24 }}>
        <RobotOutlined style={{ marginRight: 8 }} />
        数字人问辩
      </Title>

      {/* Error state with retry */}
      {errorMsg && (
        <Result
          status="warning"
          title={errorMsg}
          extra={
            <Button type="primary" onClick={handleRetry}>
              重试连接
            </Button>
          }
          style={{ marginBottom: 24 }}
        />
      )}

      {/* History records */}
      <Card
        title="问辩记录"
        style={{ marginBottom: 24 }}
        size="small"
      >
        {loadingRecords ? (
          <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', padding: 24 }}>
            <Spin />
          </div>
        ) : records.length === 0 ? (
          <Empty description="暂无问辩记录" image={Empty.PRESENTED_IMAGE_SIMPLE} />
        ) : (
          <List
            dataSource={records}
            renderItem={(record) => (
              <List.Item>
                <div style={{ width: '100%' }}>
                  <Space style={{ marginBottom: 8 }}>
                    <Text type="secondary">
                      <ClockCircleOutlined style={{ marginRight: 4 }} />
                      {formatTime(record.created_at)}
                    </Text>
                    <Tag color={record.status === 'completed' ? 'green' : 'red'}>
                      {record.status === 'completed' ? '已完成' : '失败'}
                    </Tag>
                  </Space>

                  {record.questions_snapshot.length > 0 && (
                    <div style={{ marginBottom: 4 }}>
                      <Text strong>问题：</Text>
                      {record.questions_snapshot
                        .sort((a, b) => a.sort_order - b.sort_order)
                        .map((q, i) => (
                          <Tag key={i} style={{ marginTop: 4 }}>
                            {q.content}
                          </Tag>
                        ))}
                    </div>
                  )}

                  {record.user_answer_text && (
                    <Paragraph
                      ellipsis={{ rows: 2, expandable: true, symbol: '展开' }}
                      style={{ marginBottom: 4 }}
                    >
                      <Text strong>回答：</Text>
                      {record.user_answer_text}
                    </Paragraph>
                  )}

                  {record.ai_feedback_text && (
                    <Paragraph style={{ marginBottom: 0 }}>
                      <Text strong>反馈：</Text>
                      <Text type="success">{record.ai_feedback_text}</Text>
                    </Paragraph>
                  )}
                </div>
              </List.Item>
            )}
          />
        )}
      </Card>

      {/* Settings */}
      <Card size="small" style={{ marginBottom: 24 }}>
        <Space align="center">
          <Text>回答时长：</Text>
          <InputNumber
            value={answerDuration}
            onChange={(v) => setAnswerDuration(v ?? 30)}
            min={10}
            max={120}
            step={5}
            suffix="秒"
            disabled={phase !== 'idle'}
            style={{ width: 140 }}
          />
        </Space>
      </Card>

      {/* Start button */}
      <Button
        type="primary"
        size="large"
        icon={<SoundOutlined />}
        onClick={handleStartDefense}
        disabled={phase !== 'idle' || !!errorMsg}
        loading={phase === 'loading'}
        block
        style={{ marginBottom: 24 }}
      >
        开始问辩
      </Button>

      {/* Avatar video area */}
      {phase !== 'idle' && (
        <Card style={{ marginBottom: 24, textAlign: 'center' }}>
          <video
            ref={videoRef}
            autoPlay
            playsInline
            style={{
              width: '100%',
              maxWidth: 480,
              borderRadius: 8,
              background: '#000',
              display: avatarReady ? 'block' : 'none',
              margin: '0 auto',
            }}
          />
          {!avatarReady && phase === 'loading' && (
            <div style={{ padding: 40 }}>
              <Spin size="large" />
              <div style={{ marginTop: 16 }}>
                <Text type="secondary">数字人评委正在入场…</Text>
              </div>
            </div>
          )}

          {phase === 'speaking' && (
            <div style={{ marginTop: 12 }}>
              <Tag icon={<SoundOutlined />} color="processing">
                数字人评委正在提问…
              </Tag>
            </div>
          )}
        </Card>
      )}

      {/* Recording area */}
      {phase === 'recording' && (
        <Card style={{ marginBottom: 24, textAlign: 'center' }}>
          <div style={{ marginBottom: 16 }}>
            <AudioOutlined style={{ fontSize: 32, color: '#f5222d' }} />
          </div>
          <div
            style={{
              fontSize: 48,
              fontWeight: 700,
              color: countdown <= 5 ? '#f5222d' : '#1677ff',
              marginBottom: 16,
              fontVariantNumeric: 'tabular-nums',
            }}
          >
            {countdown}
          </div>
          <Text type="secondary">正在录音，请回答评委问题</Text>
          <div style={{ marginTop: 16 }}>
            <AudioWaveform stream={audioStream} height={60} />
          </div>
        </Card>
      )}

      {/* Processing indicator */}
      {phase === 'processing' && (
        <Card style={{ marginBottom: 24, textAlign: 'center', padding: 24 }}>
          <Spin size="large" />
          <div style={{ marginTop: 16 }}>
            <Text type="secondary">正在处理回答，请稍候…</Text>
          </div>
        </Card>
      )}

      {/* Feedback indicator */}
      {phase === 'feedback' && (
        <Card style={{ marginBottom: 24, textAlign: 'center' }}>
          <Tag icon={<RobotOutlined />} color="processing">
            数字人评委正在给出反馈…
          </Tag>
        </Card>
      )}

      {/* Done indicator */}
      {phase === 'done' && (
        <Result
          status="success"
          title="问辩完成"
          subTitle="评委反馈已记录，可在上方查看历史记录"
          style={{ marginBottom: 24 }}
        />
      )}
    </div>
  );
}
