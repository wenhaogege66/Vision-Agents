import { Card, Collapse, List, Tag, Typography, Divider } from 'antd';
import RadarChart from './RadarChart';
import type { ReviewResult } from '@/types';

const { Title, Text, Paragraph } = Typography;

interface Props {
  result: ReviewResult;
}

export default function TextReviewPanel({ result }: Props) {
  return (
    <div>
      <Card style={{ marginBottom: 16 }}>
        <Title level={4}>
          总分：{result.total_score}
          <Tag color="blue" style={{ marginLeft: 12 }}>
            {result.review_type === 'text_review' ? '文本评审' : '路演评审'}
          </Tag>
        </Title>
        <RadarChart dimensions={result.dimensions} />
      </Card>

      <Collapse
        defaultActiveKey={result.dimensions.map((_, i) => String(i))}
        items={result.dimensions.map((dim, i) => ({
          key: String(i),
          label: (
            <span>
              {dim.dimension}
              <Tag style={{ marginLeft: 8 }}>{dim.score} / {dim.max_score}</Tag>
            </span>
          ),
          children: (
            <div>
              {dim.sub_items.length > 0 && (
                <>
                  <Text strong>子项评价：</Text>
                  <List
                    size="small"
                    dataSource={dim.sub_items}
                    renderItem={(item) => (
                      <List.Item>
                        <Text strong>{item.name}：</Text>
                        <Text>{item.comment}</Text>
                      </List.Item>
                    )}
                    style={{ marginBottom: 12 }}
                  />
                </>
              )}
              {dim.suggestions.length > 0 && (
                <>
                  <Text strong>改进建议：</Text>
                  <List
                    size="small"
                    dataSource={dim.suggestions}
                    renderItem={(s) => <List.Item>{s}</List.Item>}
                  />
                </>
              )}
            </div>
          ),
        }))}
      />

      {result.overall_suggestions.length > 0 && (
        <>
          <Divider />
          <Title level={5}>总体改进建议</Title>
          {result.overall_suggestions.map((s, i) => (
            <Paragraph key={i}>• {s}</Paragraph>
          ))}
        </>
      )}
    </div>
  );
}
