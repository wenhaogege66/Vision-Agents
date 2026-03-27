import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import BackButton from '@/components/BackButton';
import { Table, Tag, Typography, Spin, Space, Button } from 'antd';
import { RobotOutlined, SyncOutlined, FileTextOutlined, VideoCameraOutlined } from '@ant-design/icons';
import { msg } from '@/utils/messageHolder';
import { reviewApi } from '@/services/api';
import type { ReviewResult } from '@/types';

const { Title } = Typography;

const TYPE_LABELS: Record<string, { text: string; color: string }> = {
  text_review: { text: '文本评审', color: 'blue' },
  live_presentation: { text: '现场路演', color: 'green' },
  offline_presentation: { text: '离线路演', color: 'orange' },
};

const MATERIAL_LABELS: Record<string, string> = {
  text_ppt: '文本PPT',
  bp: 'BP',
  presentation_ppt: '路演PPT',
  presentation_video: '路演视频',
  presentation_audio: '路演音频',
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

  if (loading) return <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: 400, width: '100%' }}><Spin size="large" description="加载中…" /></div>;

  return (
    <div style={{ padding: 24 }}>
      <BackButton to={`/projects/${projectId}`} label="返回项目仪表盘" />
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Title level={3} style={{ margin: 0 }}>评审历史</Title>
        <Space>
          <Button
            icon={<FileTextOutlined />}
            onClick={() => navigate(`/projects/${projectId}/text-review`)}
          >
            文本评审
          </Button>
          <Button
            icon={<VideoCameraOutlined />}
            onClick={() => navigate(`/projects/${projectId}/offline-review`)}
          >
            离线路演
          </Button>
        </Space>
      </div>
      <Table
        dataSource={reviews}
        rowKey="id"
        onRow={(record) => ({
          onClick: () => {
            if (record.status !== 'pending') {
              navigate(`/projects/${projectId}/reviews/${record.id}`);
            }
          },
          style: { cursor: record.status === 'pending' ? 'default' : 'pointer' },
        })}
        columns={[
          {
            title: '类型',
            dataIndex: 'review_type',
            width: 160,
            render: (t: string, record: ReviewResult) => {
              const cfg = TYPE_LABELS[t] ?? { text: t, color: 'default' };
              return (
                <Space size={4}>
                  <Tag color={cfg.color}>{cfg.text}</Tag>
                  {record.auto_triggered && (
                    <Tag icon={<RobotOutlined />} color="geekblue">自动</Tag>
                  )}
                </Space>
              );
            },
          },
          {
            title: '所选材料',
            dataIndex: 'selected_materials',
            width: 200,
            render: (materials: string[] | null | undefined) => {
              if (!materials || materials.length === 0) return '—';
              return materials.map((m) => (
                <Tag key={m}>{MATERIAL_LABELS[m] ?? m}</Tag>
              ));
            },
          },
          {
            title: '总分',
            dataIndex: 'total_score',
            width: 100,
            render: (s: number, record: ReviewResult) => {
              if (record.status === 'pending') return '—';
              return s?.toFixed(1) ?? '-';
            },
          },
          {
            title: '状态',
            dataIndex: 'status',
            width: 120,
            render: (s: string) => {
              if (s === 'completed') return <Tag color="success">已完成</Tag>;
              if (s === 'failed') return <Tag color="error">失败</Tag>;
              if (s === 'pending') return <Tag icon={<SyncOutlined spin />} color="processing">进行中</Tag>;
              return <Tag color="default">{s}</Tag>;
            },
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
