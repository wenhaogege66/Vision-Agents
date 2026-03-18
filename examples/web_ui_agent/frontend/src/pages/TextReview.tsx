import { useEffect, useMemo, useState } from 'react';
import { useParams } from 'react-router-dom';
import { Button, Card, Checkbox, Spin, Typography, Space, Select, Tag } from 'antd';
import { msg } from '@/utils/messageHolder';
import { SendOutlined, LoadingOutlined } from '@ant-design/icons';
import JudgeStyleSelector from '@/components/JudgeStyleSelector';
import TextReviewPanel from '@/components/TextReviewPanel';
import BackButton from '@/components/BackButton';
import { reviewApi } from '@/services/api';
import { useReadinessChecker } from '@/hooks/useReadinessChecker';
import type { ReviewResult, CompetitionStage, MaterialStatusItem } from '@/types';
import { STAGE_LABELS } from '@/types';

const { Title, Text } = Typography;

const stageOptions = Object.entries(STAGE_LABELS)
  .filter(([k]) => k.includes('text'))
  .map(([value, label]) => ({ value, label }));

/** Material types relevant to text review. */
const TEXT_MATERIAL_TYPES = ['bp', 'text_ppt', 'presentation_ppt'] as const;
type TextMaterialType = (typeof TEXT_MATERIAL_TYPES)[number];

const MATERIAL_LABELS: Record<TextMaterialType, string> = {
  bp: '商业计划书 (BP)',
  text_ppt: '文本PPT',
  presentation_ppt: '路演PPT',
};

/** Determine the display state for a material item. */
function getMaterialState(
  type: TextMaterialType,
  item: MaterialStatusItem | undefined,
): 'ready' | 'converting' | 'not_uploaded' {
  if (!item || !item.uploaded) return 'not_uploaded';
  // BP has no conversion step – uploaded means ready
  if (type === 'bp') return 'ready';
  // PPT types need image_paths_ready
  if (item.image_paths_ready === false) return 'converting';
  return 'ready';
}

export default function TextReview() {
  const { projectId } = useParams<{ projectId: string }>();
  const [judgeStyle, setJudgeStyle] = useState('strict');
  const [stage, setStage] = useState<CompetitionStage>('school_text');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ReviewResult | null>(null);
  const [selectedMaterials, setSelectedMaterials] = useState<TextMaterialType[]>([]);

  const { status, loading: statusLoading } = useReadinessChecker(projectId ?? '');

  // Derive per-material state from the readiness status.
  const materialStates = useMemo(() => {
    if (!status) return null;
    const map: Record<TextMaterialType, 'ready' | 'converting' | 'not_uploaded'> = {
      bp: getMaterialState('bp', status.bp),
      text_ppt: getMaterialState('text_ppt', status.text_ppt),
      presentation_ppt: getMaterialState('presentation_ppt', status.presentation_ppt),
    };
    return map;
  }, [status]);

  // Whether any PPT is still converting (show global Spin indicator).
  const isConverting = useMemo(() => {
    if (!materialStates) return false;
    return materialStates.text_ppt === 'converting' || materialStates.presentation_ppt === 'converting';
  }, [materialStates]);

  // Default-check all ready materials when status first loads.
  useEffect(() => {
    if (!materialStates) return;
    const readyTypes = TEXT_MATERIAL_TYPES.filter((t) => materialStates[t] === 'ready');
    setSelectedMaterials(readyTypes as TextMaterialType[]);
  }, [materialStates]);

  const canReview = selectedMaterials.length > 0 && !loading;

  const handleCheckChange = (type: TextMaterialType, checked: boolean) => {
    setSelectedMaterials((prev) =>
      checked ? [...prev, type] : prev.filter((t) => t !== type),
    );
  };

  const handleReview = async () => {
    if (!projectId || selectedMaterials.length === 0) return;
    setLoading(true);
    setResult(null);
    try {
      const res = await reviewApi.textReview(projectId, stage, judgeStyle, selectedMaterials);
      setResult(res.data);
      msg.success('文本评审完成');
    } catch (err: unknown) {
      const errMsg =
        (err as { response?: { data?: { message?: string } } })?.response?.data
          ?.message ?? '评审失败，请稍后重试';
      msg.error(errMsg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ padding: 24 }}>
      <BackButton to={`/projects/${projectId}`} label="返回项目仪表盘" />

      <Title level={3}>AI文本评审</Title>
      <Text type="secondary" style={{ display: 'block', marginBottom: 24 }}>
        基于文本PPT和BP，AI将按照评审规则进行多维度评分和建议。
      </Text>

      {/* Material selection area */}
      <Card
        title="评审材料选择"
        style={{ marginBottom: 24 }}
        extra={isConverting ? <Spin indicator={<LoadingOutlined spin />} size="small" /> : null}
      >
        {statusLoading ? (
          <Spin style={{ display: 'block', textAlign: 'center', padding: 16 }} />
        ) : materialStates ? (
          <Space direction="vertical" size="small" style={{ width: '100%' }}>
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
                  {state === 'converting' && (
                    <Tag icon={<LoadingOutlined spin />} color="processing">
                      转换中
                    </Tag>
                  )}
                </div>
              );
            })}
            {selectedMaterials.length === 0 && !statusLoading && (
              <Text type="warning" style={{ marginTop: 8 }}>
                请先上传至少一种评审材料
              </Text>
            )}
          </Space>
        ) : null}
      </Card>

      <Card title="评审设置" style={{ marginBottom: 24 }}>
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
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
            发起文本评审
          </Button>
        </Space>
      </Card>

      {loading && <Spin size="large" style={{ display: 'block', margin: '40px auto' }} />}
      {result && <TextReviewPanel result={result} />}
    </div>
  );
}
