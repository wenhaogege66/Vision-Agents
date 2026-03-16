import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Card,
  Typography,
  Tag,
  Space,
  Row,
  Col,
  Spin,
  Steps,
  Button,
  message,
} from 'antd';
import {
  ArrowLeftOutlined,
  TrophyOutlined,
  FileTextOutlined,
  VideoCameraOutlined,
  HistoryOutlined,
  CloudUploadOutlined,
  AudioOutlined,
} from '@ant-design/icons';
import { projectApi } from '@/services/api';
import type { ProjectResponse, CompetitionStage } from '@/types';
import { STAGE_LABELS } from '@/types';

const { Title, Text } = Typography;

const STAGES: CompetitionStage[] = [
  'school_text',
  'school_presentation',
  'province_text',
  'province_presentation',
  'national_text',
  'national_presentation',
];

interface ActionCard {
  title: string;
  desc: string;
  icon: React.ReactNode;
  path: string;
  color: string;
}

export default function ProjectDashboard() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [project, setProject] = useState<ProjectResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!id) return;
    projectApi
      .get(id)
      .then((res) => setProject(res.data))
      .catch(() => {
        message.error('项目不存在');
        navigate('/projects');
      })
      .finally(() => setLoading(false));
  }, [id, navigate]);

  if (loading || !project) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', paddingTop: 120 }}>
        <Spin size="large" />
      </div>
    );
  }

  const currentStageIdx = STAGES.indexOf(project.current_stage as CompetitionStage);

  const actions: ActionCard[] = [
    {
      title: '材料中心',
      desc: '上传和管理项目核心材料',
      icon: <CloudUploadOutlined style={{ fontSize: 28 }} />,
      path: `/projects/${id}/materials`,
      color: '#1a365d',
    },
    {
      title: '文本评审',
      desc: 'AI多维度智能评分',
      icon: <FileTextOutlined style={{ fontSize: 28 }} />,
      path: `/projects/${id}/text-review`,
      color: '#2a4a7f',
    },
    {
      title: '现场路演',
      desc: '实时音视频AI评委互动',
      icon: <AudioOutlined style={{ fontSize: 28 }} />,
      path: `/projects/${id}/live`,
      color: '#0e7490',
    },
    {
      title: '离线评审',
      desc: '上传视频获取AI评审反馈',
      icon: <VideoCameraOutlined style={{ fontSize: 28 }} />,
      path: `/projects/${id}/offline-review`,
      color: '#6d28d9',
    },
    {
      title: '评审历史',
      desc: '查看所有历史评审记录',
      icon: <HistoryOutlined style={{ fontSize: 28 }} />,
      path: `/projects/${id}/reviews`,
      color: '#b45309',
    },
  ];

  return (
    <div style={{ maxWidth: 960, margin: '0 auto', padding: '32px 24px' }}>
      <Button
        type="text"
        icon={<ArrowLeftOutlined />}
        onClick={() => navigate('/projects')}
        style={{ marginBottom: 16 }}
      >
        返回项目列表
      </Button>

      {/* Project header */}
      <Card style={{ borderRadius: 12, marginBottom: 24 }} styles={{ body: { padding: 24 } }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div>
            <Title level={4} style={{ margin: '0 0 8px', color: '#1a365d' }}>
              {project.name}
            </Title>
            <Space size={6} wrap>
              <Tag icon={<TrophyOutlined />} color="blue">{project.competition}</Tag>
              <Tag color="cyan">{project.track}</Tag>
              <Tag color="geekblue">{project.group}</Tag>
            </Space>
          </div>
          <Text type="secondary" style={{ fontSize: 13 }}>
            创建于 {new Date(project.created_at).toLocaleDateString('zh-CN')}
          </Text>
        </div>
      </Card>

      {/* Stage progress */}
      <Card
        title="比赛进度"
        style={{ borderRadius: 12, marginBottom: 24 }}
        styles={{ body: { padding: '20px 24px' } }}
      >
        <Steps
          current={currentStageIdx >= 0 ? currentStageIdx : 0}
          size="small"
          items={STAGES.map((s) => ({ title: STAGE_LABELS[s] }))}
          style={{ marginBottom: 8 }}
        />
      </Card>

      {/* Quick actions */}
      <Title level={5} style={{ color: '#1a365d', marginBottom: 16 }}>
        快捷操作
      </Title>
      <Row gutter={[16, 16]}>
        {actions.map((a) => (
          <Col xs={24} sm={12} md={8} key={a.title}>
            <Card
              hoverable
              onClick={() => navigate(a.path)}
              style={{ borderRadius: 12, height: '100%' }}
              styles={{ body: { padding: 20 } }}
            >
              <div
                style={{
                  width: 48,
                  height: 48,
                  borderRadius: 12,
                  background: `${a.color}14`,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: a.color,
                  marginBottom: 12,
                }}
              >
                {a.icon}
              </div>
              <Title level={5} style={{ margin: '0 0 4px' }}>{a.title}</Title>
              <Text type="secondary" style={{ fontSize: 13 }}>{a.desc}</Text>
            </Card>
          </Col>
        ))}
      </Row>
    </div>
  );
}
