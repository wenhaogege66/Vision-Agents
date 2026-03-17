import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Table, Tag, Typography, Spin } from 'antd';
import { msg } from '@/utils/messageHolder';
import { reviewApi } from '@/services/api';
import type { ReviewResult } from '@/types';

const { Title } = Typography;

const TYPE_LABELS: Record<string, { text: string; color: string }> = {
  text_review: { text: '文本评审', color: 'blue' },
  live_presentation: { text: '现场路演', color: 'green' },
  offline_presentation: { text: '离线路演', color: 'orange' },
};

export default function ReviewHistory() {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const [reviews, setReviews] = useState<ReviewResult[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!projectId) return;
    reviewApi.list(projectId).then((res) => {
      setReviews(res.data);
      setLoading(false);
    }).catch(() => {
      msg.error('获取评审记录失败');
      setLoading(false);
    });
  }, [projectId]);

  if (loading) return <Spin size="large" style={{ display: 'block', margin: '100px auto' }} />;

  return (
    <div style={{ padding: 24 }}>
      <Title level={3}>评审历史</Title>
      <Table
        dataSource={reviews}
        rowKey="id"
        onRow={(record) => ({
          onClick: () => navigate(`/projects/${projectId}/reviews/${record.id}`),
          style: { cursor: 'pointer' },
        })}
        columns={[
          {
            title: '类型',
            dataIndex: 'review_type',
            width: 120,
            render: (t: string) => {
              const cfg = TYPE_LABELS[t] ?? { text: t, color: 'default' };
              return <Tag color={cfg.color}>{cfg.text}</Tag>;
            },
          },
          {
            title: '总分',
            dataIndex: 'total_score',
            width: 100,
            render: (s: number) => s?.toFixed(1) ?? '-',
          },
          {
            title: '状态',
            dataIndex: 'status',
            width: 100,
            render: (s: string) => (
              <Tag color={s === 'completed' ? 'success' : s === 'failed' ? 'error' : 'processing'}>
                {s === 'completed' ? '已完成' : s === 'failed' ? '失败' : '处理中'}
              </Tag>
            ),
          },
          {
            title: '时间',
            dataIndex: 'created_at',
            render: (t: string) => new Date(t).toLocaleString(),
          },
        ]}
      />
    </div>
  );
}
