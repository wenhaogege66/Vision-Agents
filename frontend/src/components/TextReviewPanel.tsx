import {
  Card,
  Descriptions,
  Table,
  Tag,
  Typography,
  Divider,
  Space,
  Grid,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import RadarChart from './RadarChart';
import type { ReviewResult, DimensionScore, PPTVisualDimension } from '@/types';

const { Title, Text, Paragraph } = Typography;
const { useBreakpoint } = Grid;

/* ── rating → tag color mapping ─────────────────────────────── */
const RATING_COLORS: Record<string, string> = {
  优秀: 'green',
  良好: 'blue',
  一般: 'orange',
  较差: 'red',
};

interface Props {
  result: ReviewResult;
}

export default function TextReviewPanel({ result }: Props) {
  const screens = useBreakpoint();
  const isCompact = !screens.md; // < 768 px

  /* ── dimension score table columns ────────────────────────── */
  const dimensionColumns: ColumnsType<DimensionScore> = [
    {
      title: '评审维度',
      dataIndex: 'dimension',
      key: 'dimension',
      width: isCompact ? 100 : 160,
      fixed: isCompact ? 'left' : undefined,
    },
    {
      title: '得分',
      dataIndex: 'score',
      key: 'score',
      width: 80,
      align: 'center',
      render: (score: number) => <Text strong>{score}</Text>,
    },
    {
      title: '满分',
      dataIndex: 'max_score',
      key: 'max_score',
      width: 80,
      align: 'center',
      render: (v: number) => <Text type="secondary">{v}</Text>,
    },
    {
      title: '得分率',
      key: 'rate',
      width: 100,
      align: 'center',
      render: (_: unknown, row: DimensionScore) => {
        const pct = row.max_score > 0 ? Math.round((row.score / row.max_score) * 100) : 0;
        const color = pct >= 80 ? 'green' : pct >= 60 ? 'blue' : 'orange';
        return <Tag color={color}>{pct}%</Tag>;
      },
    },
  ];

  /* ── PPT visual review table columns ──────────────────────── */
  const visualColumns: ColumnsType<PPTVisualDimension> = [
    {
      title: '评审维度',
      dataIndex: 'name',
      key: 'name',
      width: isCompact ? 90 : 120,
      fixed: isCompact ? 'left' : undefined,
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
      render: (text: string) => (
        <Text style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>{text}</Text>
      ),
    },
  ];

  return (
    <div style={{ maxWidth: 960, margin: '0 auto' }}>
      {/* ── 总分 + 雷达图 ──────────────────────────────────── */}
      <Card style={{ marginBottom: 16 }}>
        <Title level={4}>
          总分：{result.total_score}
          <Tag color="blue" style={{ marginLeft: 12 }}>
            {result.review_type === 'text_review' ? '文本评审' : '路演评审'}
          </Tag>
        </Title>
        <RadarChart dimensions={result.dimensions} />
      </Card>

      {/* ── 评分维度表格 ───────────────────────────────────── */}
      <Card title="评分维度" style={{ marginBottom: 16 }}>
        <Table<DimensionScore>
          rowKey="dimension"
          columns={dimensionColumns}
          dataSource={result.dimensions}
          pagination={false}
          size={isCompact ? 'small' : 'middle'}
          scroll={isCompact ? { x: 460 } : undefined}
        />
      </Card>

      {/* ── 各维度子项评价 + 改进建议 ──────────────────────── */}
      {result.dimensions.map((dim) => (
        <Card
          key={dim.dimension}
          title={
            <Space>
              <span>{dim.dimension}</span>
              <Tag>{dim.score} / {dim.max_score}</Tag>
            </Space>
          }
          style={{ marginBottom: 16 }}
        >
          {/* 子项评价 */}
          {dim.sub_items.length > 0 && (
            <>
              <Descriptions
                title="子项评价"
                column={1}
                size={isCompact ? 'small' : 'large'}
                bordered={!isCompact}
                styles={{
                  label: { width: isCompact ? 80 : 140, fontWeight: 500 },
                  content: { whiteSpace: 'pre-wrap' },
                }}
              >
                {dim.sub_items.map((item) => (
                  <Descriptions.Item key={item.name} label={item.name}>
                    {item.comment}
                  </Descriptions.Item>
                ))}
              </Descriptions>
              {dim.suggestions.length > 0 && <Divider style={{ margin: '12px 0' }} />}
            </>
          )}

          {/* 改进建议 */}
          {dim.suggestions.length > 0 && (
            <div>
              <Text strong style={{ display: 'block', marginBottom: 8 }}>改进建议</Text>
              <div>
                {dim.suggestions.map((s, i) => (
                  <div key={i} style={{ padding: '6px 0' }}>
                    <Paragraph style={{ margin: 0 }}>• {s}</Paragraph>
                  </div>
                ))}
              </div>
            </div>
          )}
        </Card>
      ))}

      {/* ── 总体改进建议 ───────────────────────────────────── */}
      {result.overall_suggestions.length > 0 && (
        <Card title="总体改进建议" style={{ marginBottom: 16 }}>
          <div>
            {result.overall_suggestions.map((s, i) => (
              <div key={i} style={{ padding: '6px 0' }}>
                <Paragraph style={{ margin: 0 }}>• {s}</Paragraph>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* ── PPT 视觉评审 ──────────────────────────────────── */}
      {result.ppt_visual_review && (
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
            size={isCompact ? 'small' : 'middle'}
            scroll={isCompact ? { x: 400 } : undefined}
            style={{ marginBottom: 16 }}
          />

          {/* 各维度改进建议（仅非优秀维度） */}
          {result.ppt_visual_review.dimensions
            .filter((d) => d.suggestions.length > 0)
            .map((d) => (
              <div key={d.name} style={{ marginBottom: 12 }}>
                <Text strong>{d.name} — 改进建议：</Text>
                <div>
                  {d.suggestions.map((s, i) => (
                    <div key={i} style={{ padding: '4px 0' }}>
                      <Paragraph style={{ margin: 0 }}>• {s}</Paragraph>
                    </div>
                  ))}
                </div>
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
      )}
    </div>
  );
}
