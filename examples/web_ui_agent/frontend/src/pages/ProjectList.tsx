import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Card,
  Typography,
  Button,
  Tag,
  Space,
  Spin,
  Empty,
  Row,
  Col,
  message,
} from 'antd';
import {
  PlusOutlined,
  TrophyOutlined,
  CheckCircleFilled,
  CloseCircleFilled,
  LogoutOutlined,
} from '@ant-design/icons';
import { projectApi } from '@/services/api';
import { useAuth } from '@/contexts/AuthContext';
import type { ProjectResponse, CompetitionStage } from '@/types';
import { STAGE_LABELS } from '@/types';

const { Title, Text } = Typography;

const MATERIAL_LABELS: Record<string, string> = {
  bp: '商业计划书',
  text_ppt: '文本PPT',
  presentation_ppt: '路演PPT',
  presentation_video: '路演视频',
};

export default function ProjectList() {
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const [projects, setProjects] = useState<ProjectResponse[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    projectApi
      .list()
      .then((res) => setProjects(res.data))
      .catch(() => message.error('加载项目列表失败'))
      .finally(() => setLoading(false));
  }, []);

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <div style={{ maxWidth: 960, margin: '0 auto', padding: '32px 24px' }}>
      {/* Header */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: 28,
        }}
      >
        <div>
          <Title level={3} style={{ margin: 0, color: '#1a365d' }}>
            我的项目
          </Title>
          {user && (
            <Text type="secondary" style={{ fontSize: 13 }}>
              {user.display_name ?? user.email}
            </Text>
          )}
        </div>
        <Space>
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => navigate('/projects/create')}
          >
            创建项目
          </Button>
          <Button icon={<LogoutOutlined />} onClick={handleLogout}>
            退出
          </Button>
        </Space>
      </div>

      {/* Content */}
      {loading ? (
        <div style={{ display: 'flex', justifyContent: 'center', paddingTop: 80 }}>
          <Spin size="large" />
        </div>
      ) : projects.length === 0 ? (
        <Card style={{ borderRadius: 12, textAlign: 'center', padding: '48px 0' }}>
          <Empty
            description="还没有项目，点击上方按钮创建第一个项目"
            image={Empty.PRESENTED_IMAGE_SIMPLE}
          />
        </Card>
      ) : (
        <Row gutter={[16, 16]}>
          {projects.map((p) => (
            <Col xs={24} sm={12} key={p.id}>
              <Card
                hoverable
                onClick={() => navigate(`/projects/${p.id}`)}
                style={{ borderRadius: 12, height: '100%' }}
                styles={{ body: { padding: 20 } }}
              >
                <Title level={5} style={{ margin: '0 0 8px', color: '#1a365d' }}>
                  {p.name}
                </Title>

                <Space size={6} wrap style={{ marginBottom: 12 }}>
                  <Tag icon={<TrophyOutlined />} color="blue">
                    {p.competition}
                  </Tag>
                  <Tag color="cyan">{p.track}</Tag>
                  <Tag color="geekblue">{p.group}</Tag>
                </Space>

                <div style={{ marginBottom: 10 }}>
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    当前阶段：
                  </Text>
                  <Tag color="orange" style={{ fontSize: 12 }}>
                    {STAGE_LABELS[p.current_stage as CompetitionStage] ?? p.current_stage}
                  </Tag>
                </div>

                {/* Material status */}
                <Space size={4} wrap>
                  {Object.entries(MATERIAL_LABELS).map(([key, label]) => {
                    const uploaded = p.materials_status?.[key];
                    return (
                      <Tag
                        key={key}
                        icon={
                          uploaded ? (
                            <CheckCircleFilled style={{ color: '#52c41a' }} />
                          ) : (
                            <CloseCircleFilled style={{ color: '#d9d9d9' }} />
                          )
                        }
                        style={{ fontSize: 11, color: uploaded ? '#389e0d' : '#bfbfbf' }}
                      >
                        {label}
                      </Tag>
                    );
                  })}
                </Space>

                <div style={{ marginTop: 10 }}>
                  <Text type="secondary" style={{ fontSize: 11 }}>
                    创建于 {new Date(p.created_at).toLocaleDateString('zh-CN')}
                  </Text>
                </div>
              </Card>
            </Col>
          ))}
        </Row>
      )}
    </div>
  );
}
