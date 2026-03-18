import { useMemo, useState } from 'react';
import { useParams } from 'react-router-dom';
import { Button, Card, Spin, Typography, Space, Select, Progress, Tag, List } from 'antd';
import { msg } from '@/utils/messageHolder';
import { CloudUploadOutlined, CheckCircleOutlined, CloseCircleOutlined } from '@ant-design/icons';
import JudgeStyleSelector from '@/components/JudgeStyleSelector';
import TextReviewPanel from '@/components/TextReviewPanel';
import BackButton from '@/components/BackButton';
import { reviewApi } from '@/services/api';
import { useReadinessChecker } from '@/hooks/useReadinessChecker';
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
  const [judgeStyle, setJudgeStyle] = useState('strict');
  const [stage, setStage] = useState<CompetitionStage>('school_presentation');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ReviewResult | null>(null);

  const { status, loading: statusLoading } = useReadinessChecker(projectId ?? '');

  // Whether the presentation video is uploaded (core requirement for offline review).
  const videoReady = status?.presentation_video?.uploaded ?? false;

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
    setLoading(true);
    setResult(null);
    try {
      const res = await reviewApi.offlineReview(projectId, stage, judgeStyle);
      setResult(res.data);
      msg.success('离线路演评审完成');
    } catch (err: unknown) {
      const errMsg =
        (err as { response?: { data?: { message?: string } } })?.response?.data
          ?.message ?? '评审失败，请确保已上传路演PPT和路演视频';
      msg.error(errMsg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ padding: 24 }}>
      <BackButton to={`/projects/${projectId}`} label="返回项目仪表盘" />

      <Title level={3}>离线路演评审</Title>
      <Text type="secondary" style={{ display: 'block', marginBottom: 24 }}>
        基于已上传的路演视频和路演PPT进行AI评审，生成综合评审报告（演讲表现、PPT内容、综合评分、改进建议）。
      </Text>

      {/* Auxiliary material status list */}
      <Card
        title="辅助材料状态"
        style={{ marginBottom: 24 }}
      >
        {statusLoading ? (
          <Spin style={{ display: 'block', textAlign: 'center', padding: 16 }} />
        ) : auxMaterialStates ? (
          <List
            size="small"
            dataSource={AUX_MATERIAL_TYPES.map((type) => ({
              type,
              label: AUX_MATERIAL_LABELS[type],
              state: auxMaterialStates[type],
            }))}
            renderItem={(item) => (
              <List.Item>
                <Space>
                  <Text>{item.label}</Text>
                  {item.state === 'ready' && (
                    <Tag icon={<CheckCircleOutlined />} color="success">已就绪</Tag>
                  )}
                  {item.state === 'not_uploaded' && (
                    <Tag icon={<CloseCircleOutlined />} color="default">未上传</Tag>
                  )}
                </Space>
                {item.type === 'presentation_ppt' && item.state === 'not_uploaded' && (
                  <Text type="warning" style={{ fontSize: 12 }}>
                    路演PPT未上传，评审将不包含PPT辅助内容
                  </Text>
                )}
              </List.Item>
            )}
          />
        ) : null}
      </Card>

      <Card title="评审设置" style={{ marginBottom: 24 }}>
        <Space orientation="vertical" size="middle" style={{ width: '100%' }}>
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
            disabled={!videoReady || loading}
            size="large"
          >
            发起离线路演评审
          </Button>
          {!statusLoading && !videoReady && (
            <Text type="warning">请先上传路演视频</Text>
          )}
        </Space>
      </Card>

      {loading && (
        <Card style={{ textAlign: 'center', padding: 40 }}>
          <Spin size="large" />
          <Text style={{ display: 'block', marginTop: 16 }}>正在分析路演视频和PPT，请稍候...</Text>
          <Progress percent={99.9} status="active" showInfo={false} style={{ maxWidth: 300, margin: '16px auto 0' }} />
        </Card>
      )}
      {result && <TextReviewPanel result={result} />}
    </div>
  );
}
