import { useState } from 'react';
import { useParams } from 'react-router-dom';
import { Button, Card, message, Spin, Typography, Space, Select, Progress } from 'antd';
import { CloudUploadOutlined } from '@ant-design/icons';
import JudgeStyleSelector from '@/components/JudgeStyleSelector';
import TextReviewPanel from '@/components/TextReviewPanel';
import { reviewApi } from '@/services/api';
import type { ReviewResult, CompetitionStage } from '@/types';
import { STAGE_LABELS } from '@/types';

const { Title, Text } = Typography;

const stageOptions = Object.entries(STAGE_LABELS)
  .filter(([k]) => k.includes('presentation'))
  .map(([value, label]) => ({ value, label }));

export default function OfflineReview() {
  const { projectId } = useParams<{ projectId: string }>();
  const [judgeStyle, setJudgeStyle] = useState('strict');
  const [stage, setStage] = useState<CompetitionStage>('school_presentation');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ReviewResult | null>(null);

  const handleReview = async () => {
    if (!projectId) return;
    setLoading(true);
    setResult(null);
    try {
      const res = await reviewApi.offlineReview(projectId, stage, judgeStyle);
      setResult(res.data);
      message.success('离线路演评审完成');
    } catch (err: any) {
      message.error(err.response?.data?.message ?? '评审失败，请确保已上传路演PPT和路演视频');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ padding: 24 }}>
      <Title level={3}>离线路演评审</Title>
      <Text type="secondary" style={{ display: 'block', marginBottom: 24 }}>
        基于已上传的路演视频和路演PPT进行AI评审，生成综合评审报告（演讲表现、PPT内容、综合评分、改进建议）。
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
            icon={<CloudUploadOutlined />}
            onClick={handleReview}
            loading={loading}
            size="large"
          >
            发起离线路演评审
          </Button>
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
