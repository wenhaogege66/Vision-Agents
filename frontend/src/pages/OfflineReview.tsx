import { useMemo, useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Alert, Button, Card, Flex, Spin, Typography, Select, Tag } from 'antd';
import { msg } from '@/utils/messageHolder';
import { CloudUploadOutlined, CheckCircleOutlined, CloseCircleOutlined, SoundOutlined, VideoCameraOutlined, HistoryOutlined, RobotOutlined } from '@ant-design/icons';
import JudgeStyleSelector from '@/components/JudgeStyleSelector';
import TextReviewPanel from '@/components/TextReviewPanel';
import AIProcessingCard from '@/components/AIProcessingCard';
import BackButton from '@/components/BackButton';
import { reviewApi } from '@/services/api';
import { useReadinessChecker } from '@/hooks/useReadinessChecker';
import { useConcurrentState } from '@/hooks/useConcurrentState';
import type { ReviewResult, CompetitionStage, MaterialStatusItem } from '@/types';
import { STAGE_LABELS } from '@/types';

const { Title, Text } = Typography;

const stageOptions = Object.entries(STAGE_LABELS)
  .filter(([k]) => k.includes('presentation'))
  .map(([value, label]) => ({ value, label }));

/** Auxiliary material types for offline review (ordered by priority). */
const AUX_MATERIAL_TYPES = ['presentation_ppt', 'text_ppt', 'bp'] as const;
type AuxMaterialType = (typeof AUX_MATERIAL_TYPES)[number];

const AUX_MATERIAL_LABELS: Record<AuxMaterialType, string> = {
  presentation_ppt: '路演PPT',
  text_ppt: '文本PPT',
  bp: '商业计划书 (BP)',
};

/** Determine the display state for an auxiliary material item. */
function getAuxMaterialState(
  _type: AuxMaterialType,
  item: MaterialStatusItem | undefined,
): 'ready' | 'not_uploaded' {
  if (!item || !item.uploaded) return 'not_uploaded';
  return 'ready';
}

export default function OfflineReview() {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const [judgeStyle, setJudgeStyle] = useState('strict');
  const [stage, setStage] = useState<CompetitionStage>('school_presentation');
  const { startOperation, completeOperation, failOperation, getStatus } = useConcurrentState();
  const [result, setResult] = useState<ReviewResult | null>(null);

  // Pending review check
  const [pendingReview, setPendingReview] = useState<{ id: string; auto_triggered: boolean; created_at: string } | null>(null);
  const [checkingPending, setCheckingPending] = useState(true);

  const loading = getStatus('offline_review') === 'loading';

  const { status, loading: statusLoading } = useReadinessChecker(projectId ?? '');

  // Check for pending offline reviews on mount
  useEffect(() => {
    if (!projectId) return;
    reviewApi.pending(projectId)
      .then((pending) => {
        const offlinePending = pending.find((r) => r.review_type === 'offline_presentation');
        if (offlinePending) {
          setPendingReview({ id: offlinePending.id, auto_triggered: offlinePending.auto_triggered, created_at: offlinePending.created_at });
        }
      })
      .catch(() => {})
      .finally(() => setCheckingPending(false));
  }, [projectId]);

  // Whether at least one media source (video or audio) is uploaded.
  const videoReady = status?.presentation_video?.uploaded ?? false;
  const audioReady = status?.presentation_audio?.uploaded ?? false;
  const mediaReady = videoReady || audioReady;

  // Derive per-auxiliary-material state from the readiness status.
  const auxMaterialStates = useMemo(() => {
    if (!status) return null;
    const map: Record<AuxMaterialType, 'ready' | 'not_uploaded'> = {
      presentation_ppt: getAuxMaterialState('presentation_ppt', status.presentation_ppt),
      text_ppt: getAuxMaterialState('text_ppt', status.text_ppt),
      bp: getAuxMaterialState('bp', status.bp),
    };
    return map;
  }, [status]);

  const handleReview = async () => {
    if (!projectId) return;
    startOperation('offline_review');
    setResult(null);
    try {
      const res = await reviewApi.offlineReview(projectId, stage, judgeStyle);
      setResult(res.data);
      completeOperation('offline_review');
      msg.success('离线路演评审完成');
    } catch (err: unknown) {
      const errMsg =
        (err as { response?: { data?: { message?: string } } })?.response?.data
          ?.message ?? '评审失败，请确保已上传路演PPT和路演视频';
      failOperation('offline_review', errMsg);
      msg.error(errMsg);
    }
  };

  return (
    <div style={{ padding: 24 }}>
      <BackButton to={`/projects/${projectId}`} label="返回项目仪表盘" />

      <Title level={3}>离线路演评审</Title>
      <Text type="secondary" style={{ display: 'block', marginBottom: 24 }}>
        基于已上传的路演视频或路演音频和路演PPT进行AI评审，生成综合评审报告（演讲表现、PPT内容、综合评分、改进建议）。
      </Text>

      {/* Pending review alert */}
      {!checkingPending && pendingReview && (
        <Alert
          type="warning"
          showIcon
          icon={<RobotOutlined />}
          style={{ marginBottom: 24 }}
          message={
            <span>
              当前有一项离线路演评审正在进行中
              {pendingReview.auto_triggered && <Tag color="blue" style={{ marginLeft: 8 }}>系统自动触发</Tag>}
            </span>
          }
          description={
            <span>
              开始于 {new Date(pendingReview.created_at).toLocaleString('zh-CN')}，请等待评审完成后再发起新的评审。
              <Button
                type="link"
                icon={<HistoryOutlined />}
                onClick={() => navigate(`/projects/${projectId}/reviews`)}
                style={{ padding: '0 4px' }}
              >
                查看评审历史
              </Button>
            </span>
          }
        />
      )}

      {/* Media material status (video / audio) — at least one required */}
      <Card
        title="媒体材料状态"
        extra={<Text type="secondary" style={{ fontSize: 12 }}>路演视频和路演音频至少上传一种</Text>}
        style={{ marginBottom: 24 }}
      >
        {statusLoading ? (
          <Spin style={{ display: 'block', textAlign: 'center', padding: 16 }} />
        ) : (
          <Flex vertical gap={8}>
            {[
              { key: 'video', label: '路演视频', ready: videoReady, icon: <VideoCameraOutlined /> },
              { key: 'audio', label: '路演音频', ready: audioReady, icon: <SoundOutlined /> },
            ].map((item) => (
              <Flex key={item.key} align="center" gap={8} style={{ padding: '6px 0', borderBottom: '1px solid #f0f0f0' }}>
                {item.icon}
                <Text>{item.label}</Text>
                {item.ready ? (
                  <Tag icon={<CheckCircleOutlined />} color="success">已上传</Tag>
                ) : (
                  <Tag icon={<CloseCircleOutlined />} color="default">未上传</Tag>
                )}
              </Flex>
            ))}
          </Flex>
        )}
      </Card>

      {/* Auxiliary material status list */}
      <Card
        title="辅助材料状态"
        style={{ marginBottom: 24 }}
      >
        {statusLoading ? (
          <Spin style={{ display: 'block', textAlign: 'center', padding: 16 }} />
        ) : auxMaterialStates ? (
          <Flex vertical gap={8}>
            {AUX_MATERIAL_TYPES.map((type) => {
              const label = AUX_MATERIAL_LABELS[type];
              const state = auxMaterialStates[type];
              return (
                <Flex key={type} align="center" gap={8} wrap="wrap" style={{ padding: '6px 0', borderBottom: '1px solid #f0f0f0' }}>
                  <Text>{label}</Text>
                  {state === 'ready' && (
                    <Tag icon={<CheckCircleOutlined />} color="success">已就绪</Tag>
                  )}
                  {state === 'not_uploaded' && (
                    <Tag icon={<CloseCircleOutlined />} color="default">未上传</Tag>
                  )}
                  {type === 'presentation_ppt' && state === 'not_uploaded' && (
                    <Text type="warning" style={{ fontSize: 12 }}>
                      路演PPT未上传，评审将不包含PPT辅助内容
                    </Text>
                  )}
                </Flex>
              );
            })}
          </Flex>
        ) : null}
      </Card>

      <Card title="评审设置" style={{ marginBottom: 24 }}>
        <Flex vertical gap="middle" style={{ width: '100%' }}>
          <div>
            <Text strong style={{ display: 'block', marginBottom: 8 }}>比赛阶段</Text>
            <Select
              value={stage}
              onChange={(v) => setStage(v as CompetitionStage)}
              options={stageOptions}
              style={{ width: 200 }}
            />
          </div>
          <div>
            <Text strong style={{ display: 'block', marginBottom: 8 }}>评委风格</Text>
            <JudgeStyleSelector value={judgeStyle} onChange={setJudgeStyle} />
          </div>
          <Button
            type="primary"
            icon={<CloudUploadOutlined />}
            onClick={handleReview}
            loading={loading}
            disabled={!mediaReady || loading || !!pendingReview}
            size="large"
          >
            {pendingReview ? '评审进行中，请稍候…' : '发起离线路演评审'}
          </Button>
          {!statusLoading && !mediaReady && (
            <Text type="warning">请先上传路演视频或路演音频</Text>
          )}
        </Flex>
      </Card>

      {loading && (
        <AIProcessingCard
          title="正在进行离线路演评审"
          estimate="预计需要 3~6 分钟"
          steps={[
            '正在读取路演视频和辅助材料...',
            '正在转录路演音频内容...',
            '正在分析演讲表现与PPT内容...',
            '正在进行综合评分...',
            '正在生成评审报告和改进建议...',
          ]}
          stepInterval={12}
          style={{ marginBottom: 24 }}
        />
      )}
      {result && <TextReviewPanel result={result} />}
    </div>
  );
}
