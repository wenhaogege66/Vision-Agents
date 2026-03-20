import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import BackButton from '@/components/BackButton';
import {
  Button,
  Card,
  Descriptions,
  Divider,
  List,
  Space,
  Spin,
  Table,
  Tag,
  Typography,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { msg } from '@/utils/messageHolder';
import { DownloadOutlined } from '@ant-design/icons';
import TextReviewPanel from '@/components/TextReviewPanel';
import { reviewApi } from '@/services/api';
import type { ReviewResult, PPTVisualDimension } from '@/types';

const { Title, Text, Paragraph } = Typography;

/* ── material type → Chinese label mapping ──────────────────── */
const MATERIAL_LABELS: Record<string, string> = {
  text_ppt: '文本PPT',
  bp: 'BP',
  presentation_ppt: '路演PPT',
  presentation_video: '路演视频',
  presentation_audio: '路演音频',
};

/* ── rating → tag color mapping (consistent with TextReviewPanel) */
const RATING_COLORS: Record<string, string> = {
  优秀: 'green',
  良好: 'blue',
  一般: 'orange',
  较差: 'red',
};

export default function ReviewDetail() {
  const { projectId, reviewId } = useParams<{ projectId: string; reviewId: string }>();
  const [result, setResult] = useState<ReviewResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);

  useEffect(() => {
    if (!projectId || !reviewId) return;
    reviewApi.get(projectId, reviewId).then((res) => {
      setResult(res.data);
      setLoading(false);
    }).catch(() => {
      msg.error('获取评审详情失败');
      setLoading(false);
    });
  }, [projectId, reviewId]);

  const handleExport = async () => {
    if (!projectId || !reviewId) return;
    setExporting(true);
    try {
      const res = await reviewApi.exportPdf(projectId, reviewId);
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const a = document.createElement('a');
      a.href = url;
      a.download = `review_${reviewId}.pdf`;
      a.click();
      window.URL.revokeObjectURL(url);
    } catch {
      msg.error('导出失败');
    } finally {
      setExporting(false);
    }
  };

  if (loading) return <Spin size="large" style={{ display: 'block', margin: '100px auto' }} />;
  if (!result) return <Title level={4}>评审记录不存在</Title>;

  /* ── PPT visual review table columns ──────────────────────── */
  const visualColumns: ColumnsType<PPTVisualDimension> = [
    {
      title: '评审维度',
      dataIndex: 'name',
      key: 'name',
      width: 120,
    },
    {
      title: '评级',
      dataIndex: 'rating',
      key: 'rating',
      width: 80,
      align: 'center',
      render: (rating: string) => (
        <Tag color={RATING_COLORS[rating] ?? 'default'}>{rating}</Tag>
      ),
    },
    {
      title: '评价',
      dataIndex: 'comment',
      key: 'comment',
    },
  ];

  return (
    <div style={{ padding: 24 }}>
      <BackButton to={`/projects/${projectId}/reviews`} label="返回评审历史" />
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Title level={3} style={{ margin: 0 }}>评审详情</Title>
        <Button icon={<DownloadOutlined />} onClick={handleExport} loading={exporting}>
          导出PDF
        </Button>
      </div>

      {/* ── 所选材料列表 ───────────────────────────────────── */}
      {result.selected_materials && result.selected_materials.length > 0 && (
        <Card title="评审所选材料" style={{ marginBottom: 16 }}>
          <Space size={[8, 8]} wrap>
            {result.selected_materials.map((m) => (
              <Tag key={m} color="blue">{MATERIAL_LABELS[m] ?? m}</Tag>
            ))}
          </Space>
        </Card>
      )}

      {/* ── 核心评审结果（TextReviewPanel） ─────────────────── */}
      <TextReviewPanel result={result} />

      {/* ── PPT 视觉评审区块 ───────────────────────────────── */}
      {result.ppt_visual_review && (
        <div style={{ maxWidth: 960, margin: '0 auto' }}>
          <Card
            title={
              <Space>
                <span>PPT 视觉评审</span>
                <Tag color="purple">视觉维度</Tag>
              </Space>
            }
            style={{ marginBottom: 16 }}
          >
            <Table<PPTVisualDimension>
              rowKey="name"
              columns={visualColumns}
              dataSource={result.ppt_visual_review.dimensions}
              pagination={false}
              size="middle"
              style={{ marginBottom: 16 }}
            />

            {/* 各维度改进建议（仅非优秀维度） */}
            {result.ppt_visual_review.dimensions
              .filter((d) => d.suggestions.length > 0)
              .map((d) => (
                <div key={d.name} style={{ marginBottom: 12 }}>
                  <Text strong>{d.name} — 改进建议：</Text>
                  <List
                    size="small"
                    dataSource={d.suggestions}
                    renderItem={(s) => (
                      <List.Item style={{ padding: '4px 0' }}>
                        <Paragraph style={{ margin: 0 }}>• {s}</Paragraph>
                      </List.Item>
                    )}
                  />
                </div>
              ))}

            {/* 总体评价 */}
            {result.ppt_visual_review.overall_comment && (
              <>
                <Divider style={{ margin: '12px 0' }} />
                <Text strong>总体评价：</Text>
                <Paragraph style={{ marginTop: 4 }}>
                  {result.ppt_visual_review.overall_comment}
                </Paragraph>
              </>
            )}
          </Card>
        </div>
      )}

      {/* ── 路演者评价区块 ─────────────────────────────────── */}
      {result.presenter_evaluation && (
        <div style={{ maxWidth: 960, margin: '0 auto' }}>
          <Card
            title={
              <Space>
                <span>路演表现评价</span>
                <Tag color="cyan">路演者</Tag>
              </Space>
            }
            style={{ marginBottom: 16 }}
          >
            <Descriptions
              column={1}
              bordered
              size="middle"
              labelStyle={{ width: 140, fontWeight: 500 }}
              contentStyle={{ whiteSpace: 'pre-wrap' }}
            >
              <Descriptions.Item label="语言表达">
                {result.presenter_evaluation.language_expression}
              </Descriptions.Item>
              <Descriptions.Item label="节奏控制">
                {result.presenter_evaluation.rhythm_control}
              </Descriptions.Item>
              <Descriptions.Item label="逻辑清晰度">
                {result.presenter_evaluation.logic_clarity}
              </Descriptions.Item>
              <Descriptions.Item label="互动感">
                {result.presenter_evaluation.engagement}
              </Descriptions.Item>
              <Descriptions.Item label="总体评价">
                {result.presenter_evaluation.overall_comment}
              </Descriptions.Item>
            </Descriptions>

            {/* 改进建议 */}
            {result.presenter_evaluation.suggestions.length > 0 && (
              <>
                <Divider style={{ margin: '12px 0' }} />
                <Text strong style={{ display: 'block', marginBottom: 8 }}>改进建议</Text>
                <List
                  size="small"
                  dataSource={result.presenter_evaluation.suggestions}
                  renderItem={(s) => (
                    <List.Item style={{ padding: '6px 0' }}>
                      <Paragraph style={{ margin: 0 }}>• {s}</Paragraph>
                    </List.Item>
                  )}
                />
              </>
            )}
          </Card>
        </div>
      )}
    </div>
  );
}
