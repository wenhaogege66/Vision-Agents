import { useState } from 'react';
import { useParams } from 'react-router-dom';
import { Button, Card, message, Spin, Typography, Space, Select } from 'antd';
import { SendOutlined } from '@ant-design/icons';
import JudgeStyleSelector from '@/components/JudgeStyleSelector';
import TextReviewPanel from '@/components/TextReviewPanel';
import { reviewApi } from '@/services/api';
import type { ReviewResult, CompetitionStage } from '@/types';
import { STAGE_LABELS } from '@/types';

const { Title, Text } = Typography;

const stageOptions = Object.entries(STAGE_LABELS)
  .filter(([k]) => k.includes('text'))
  .map(([value, label]) => ({ value, label }));

export default function TextReview() {
  const { projectId } = useParams<{ projectId: string }>();
  const [judgeStyle, setJudgeStyle] = useState('strict');
  const [stage, setStage] = useState<CompetitionStage>('school_text');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ReviewResult | null>(null);

  const handleReview = async () => {
    if (!projectId) return;
    setLoading(true);
    setResult(null);
    try {
      const res = await reviewApi.textReview(projectId, stage, judgeStyle);
      setResult(res.data);
      message.success('文本评审完成');
    } catch (err: any) {
      message.error(err.response?.data?.message ?? '评审失败，请稍后重试');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ padding: 24 }}>
      <Title level={3}>AI文本评审</Title>
      <Text type="secondary" style={{ display: 'block', marginBottom: 24 }}>
        基于文本PPT和BP，AI将按照评审规则进行多维度评分和建议。
      </Text>

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
