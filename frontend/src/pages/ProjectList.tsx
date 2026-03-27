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
  Modal,
} from 'antd';
import { msg } from '@/utils/messageHolder';
import {
  PlusOutlined,
  TrophyOutlined,
  CheckCircleFilled,
  CloseCircleFilled,
  LogoutOutlined,
  DeleteOutlined,
} from '@ant-design/icons';
import { projectApi, tagApi } from '@/services/api';
import { useAuth } from '@/contexts/AuthContext';
import { useLabelResolver } from '@/hooks/useLabelResolver';
import { triggerSidebarRefresh } from '@/components/AppLayout';
import type { ProjectResponse, CompetitionStage, TagInfo } from '@/types';
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
  const { resolve } = useLabelResolver();
  const [projects, setProjects] = useState<ProjectResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [allTags, setAllTags] = useState<TagInfo[]>([]);
  const [selectedTagId, setSelectedTagId] = useState<string | null>(null);
  const [projectTagMap, setProjectTagMap] = useState<Record<string, string[]>>({});

  useEffect(() => {
    projectApi
      .list()
      .then(async (res) => {
        const projectList = res.data;
        setProjects(projectList);

        // Fetch all user tags
        try {
          const tags = await tagApi.list();
          setAllTags(tags);
        } catch {
          // silently ignore — tags are optional
        }

        // Build project → tag_ids map
        const tagMap: Record<string, string[]> = {};
        await Promise.all(
          projectList.map(async (p) => {
            try {
              const tags = await tagApi.getProjectTags(p.id);
              tagMap[p.id] = tags.map((t) => t.id);
            } catch {
              tagMap[p.id] = [];
            }
          }),
        );
        setProjectTagMap(tagMap);
      })
      .catch(() => msg.error('加载项目列表失败'))
      .finally(() => setLoading(false));
  }, []);

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const handleDelete = (e: React.MouseEvent, project: ProjectResponse) => {
    e.stopPropagation();
    Modal.confirm({
      title: '确认删除',
      content: `确定要删除项目「${project.name}」吗？删除后不可恢复。`,
      okText: '删除',
      okType: 'danger',
      cancelText: '取消',
      onOk: async () => {
        try {
          await projectApi.delete(project.id);
          setProjects((prev) => prev.filter((p) => p.id !== project.id));
          msg.success('项目已删除');
          triggerSidebarRefresh();
        } catch {
          // global interceptor handles error
        }
      },
    });
  };

  const filteredProjects = selectedTagId
    ? projects.filter((p) => projectTagMap[p.id]?.includes(selectedTagId))
    : projects;

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

      {/* Tag filter chips */}
      {allTags.length > 0 && (
        <div style={{ marginBottom: 16 }}>
          <Space size={[8, 8]} wrap>
            <Tag
              color={selectedTagId === null ? 'blue' : undefined}
              style={{ cursor: 'pointer' }}
              onClick={() => setSelectedTagId(null)}
            >
              全部
            </Tag>
            {allTags.map((tag) => (
              <Tag
                key={tag.id}
                color={selectedTagId === tag.id ? tag.color : undefined}
                style={{
                  cursor: 'pointer',
                  borderColor: selectedTagId !== tag.id ? tag.color : undefined,
                  color: selectedTagId !== tag.id ? tag.color : undefined,
                }}
                onClick={() =>
                  setSelectedTagId(selectedTagId === tag.id ? null : tag.id)
                }
              >
                {tag.name}
              </Tag>
            ))}
          </Space>
        </div>
      )}

      {/* Content */}
      {loading ? (
        <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: 300, width: '100%' }}>
          <Spin size="large" description="加载中…" />
        </div>
      ) : projects.length === 0 ? (
        <Card style={{ borderRadius: 12, textAlign: 'center', padding: '48px 0' }}>
          <Empty
            description="还没有项目，点击上方按钮创建第一个项目"
            image={Empty.PRESENTED_IMAGE_SIMPLE}
          />
        </Card>
      ) : filteredProjects.length === 0 ? (
        <Card style={{ borderRadius: 12, textAlign: 'center', padding: '48px 0' }}>
          <Empty
            description="没有匹配该标签的项目"
            image={Empty.PRESENTED_IMAGE_SIMPLE}
          />
        </Card>
      ) : (
        <Row gutter={[16, 16]}>
          {filteredProjects.map((p) => (
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
                    {resolve('competition', p.competition)}
                  </Tag>
                  <Tag color="cyan">{resolve('track', p.track)}</Tag>
                  <Tag color="geekblue">{resolve('group', p.group)}</Tag>
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

                <div style={{ marginTop: 10, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <Text type="secondary" style={{ fontSize: 11 }}>
                    创建于 {new Date(p.created_at).toLocaleDateString('zh-CN')}
                  </Text>
                  <Button
                    type="text"
                    danger
                    size="small"
                    icon={<DeleteOutlined />}
                    onClick={(e) => handleDelete(e, p)}
                  />
                </div>
              </Card>
            </Col>
          ))}
        </Row>
      )}
    </div>
  );
}
