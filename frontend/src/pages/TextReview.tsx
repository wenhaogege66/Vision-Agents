import { useEffect, useMemo, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Alert, Button, Card, Checkbox, Spin, Typography, Flex, Select, Tag } from 'antd';
import { msg } from '@/utils/messageHolder';
import { SendOutlined, HistoryOutlined, RobotOutlined } from '@ant-design/icons';
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
  .filter(([k]) => k.includes('text'))
  .map(([value, label]) => ({ value, label }));

/** Material types relevant to text review. */
const TEXT_MATERIAL_TYPES = ['text_ppt', 'bp'] as const;
type TextMaterialType = (typeof TEXT_MATERIAL_TYPES)[number];

const MATERIAL_LABELS: Record<TextMaterialType, string> = {
  text_ppt: '文本PPT',
  bp: '商业计划书 (BP)',
};

/** Determine the display state for a material item. */
function getMaterialState(
  _type: TextMaterialType,
  item: MaterialStatusItem | undefined,
): 'ready' | 'not_uploaded' {
  if (!item || !item.uploaded) return 'not_uploaded';
  return 'ready';
}

export default function TextReview() {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const [judgeStyle, setJudgeStyle] = useState('strict');
  const [stage, setStage] = useState<CompetitionStage>('school_text');
  const { startOperation, completeOperation, failOperation, getStatus } = useConcurrentState();
  const [result, setResult] = useState<ReviewResult | null>(null);
  const [selectedMaterials, setSelectedMaterials] = useState<TextMaterialType[]>([]);

  // Pending review check
  const [pendingReview, setPendingReview] = useState<{ id: string; auto_triggered: boolean; created_at: string } | null>(null);
  const [checkingPending, setCheckingPending] = useState(true);

  const loading = getStatus('text_review') === 'loading';

  const { status, loading: statusLoading } = useReadinessChecker(projectId ?? '');

  // Check for pending text reviews on mount
  useEffect(() => {
    if (!projectId) return;
    reviewApi.pending(projectId)
      .then((pending) => {
        const textPending = pending.find((r) => r.review_type === 'text_review');
        if (textPending) {
          setPendingReview({ id: textPending.id, auto_triggered: textPending.auto_triggered, created_at: textPending.created_at });
        }
      })
      .catch(() => {})
      .finally(() => setCheckingPending(false));
  }, [projectId]);

  // Derive per-material state from the readiness status.
  const materialStates = useMemo(() => {
    if (!status) return null;
    const map: Record<TextMaterialType, 'ready' | 'not_uploaded'> = {
      text_ppt: getMaterialState('text_ppt', status.text_ppt),
      bp: getMaterialState('bp', status.bp),
    };
    return map;
  }, [status]);

  // Default-check all ready materials when status first loads.
  useEffect(() => {
    if (!materialStates) return;
    const readyTypes = TEXT_MATERIAL_TYPES.filter((t) => materialStates[t] === 'ready');
    setSelectedMaterials(readyTypes as TextMaterialType[]);
  }, [materialStates]);

  const canReview = selectedMaterials.length > 0 && !loading && !pendingReview;

  const handleCheckChange = (type: TextMaterialType, checked: boolean) => {
    setSelectedMaterials((prev) =>
      checked ? [...prev, type] : prev.filter((t) => t !== type),
    );
  };

  const handleReview = async () => {
    if (!projectId || selectedMaterials.length === 0) return;
    startOperation('text_review');
    setResult(null);
    try {
      const res = await reviewApi.textReview(projectId, stage, judgeStyle, selectedMaterials);
      setResult(res.data);
      completeOperation('text_review');
      msg.success('文本评审完成');
    } catch (err: unknown) {
      const errMsg =
        (err as { response?: { data?: { message?: string } } })?.response?.data
          ?.message ?? '评审失败，请稍后重试';
      failOperation('text_review', errMsg);
      msg.error(errMsg);
    }
  };

  return (
    <div style={{ padding: 24 }}>
      <BackButton to={`/projects/${projectId}`} label="返回项目仪表盘" />

      <Title level={3}>AI文本评审</Title>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <Text type="secondary">
          基于文本PPT和BP，AI将按照评审规则进行多维度评分和建议。
        </Text>
        <Button
          icon={<HistoryOutlined />}
          onClick={() => navigate(`/projects/${projectId}/reviews`)}
        >
          评审历史
        </Button>
      </div>

      {/* Pending review alert */}
      {!checkingPending && pendingReview && (
        <Alert
          type="warning"
          showIcon
          icon={<RobotOutlined />}
          style={{ marginBottom: 24 }}
          message={
            <span>
              当前有一项文本评审正在进行中
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

      {/* Material selection area */}
      <Card
        title="评审材料选择"
        style={{ marginBottom: 24 }}
      >
        {statusLoading ? (
          <Spin style={{ display: 'block', textAlign: 'center', padding: 16 }} />
        ) : materialStates ? (
          <Flex vertical gap="small" style={{ width: '100%' }}>
            {TEXT_MATERIAL_TYPES.map((type) => {
              const state = materialStates[type];
              const isReady = state === 'ready';
              const disabled = !isReady;
              return (
                <div key={type} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <Checkbox
                    checked={selectedMaterials.includes(type)}
                    disabled={disabled}
                    onChange={(e) => handleCheckChange(type, e.target.checked)}
                  >
                    {MATERIAL_LABELS[type]}
                  </Checkbox>
                  {state === 'not_uploaded' && (
                    <Tag color="default">未上传</Tag>
                  )}
                </div>
              );
            })}
            {selectedMaterials.length === 0 && !statusLoading && (
              <Text type="warning" style={{ marginTop: 8 }}>
                请先上传至少一种评审材料
              </Text>
            )}
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
            icon={<SendOutlined />}
            onClick={handleReview}
            loading={loading}
            disabled={!canReview}
            size="large"
          >
            {pendingReview ? '评审进行中，请稍候…' : '发起文本评审'}
          </Button>
        </Flex>
      </Card>

      {loading && (
        <AIProcessingCard
          title="正在进行 AI 文本评审"
          estimate="预计需要 1~3 分钟"
          steps={[
            '正在读取评审材料...',
            '正在分析项目内容与创新点...',
            '正在进行多维度评分...',
            '正在生成评审意见和改进建议...',
          ]}
          style={{ marginBottom: 24 }}
        />
      )}
      {result && <TextReviewPanel result={result} />}
    </div>
  );
}
