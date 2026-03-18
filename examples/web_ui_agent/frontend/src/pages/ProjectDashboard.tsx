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
  Tooltip,
  Descriptions,
  Input,
  Popover,
  Divider,
} from 'antd';
import { msg } from '@/utils/messageHolder';
import {
  ArrowLeftOutlined,
  TrophyOutlined,
  FileTextOutlined,
  VideoCameraOutlined,
  HistoryOutlined,
  CloudUploadOutlined,
  AudioOutlined,
  EditOutlined,
  RobotOutlined,
  UserOutlined,
  SyncOutlined,
  PlusOutlined,
  TagOutlined,
  DownloadOutlined,
} from '@ant-design/icons';
import api, { projectApi, profileApi, tagApi } from '@/services/api';
import { useReadinessChecker } from '@/hooks/useReadinessChecker';
import { useLabelResolver } from '@/hooks/useLabelResolver';
import ReviewSelectionDialog from '@/components/ReviewSelectionDialog';
import type { ProjectResponse, ProjectProfile, CompetitionStage, StageConfig, TagInfo } from '@/types';
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
  const { projectId: id } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const [project, setProject] = useState<ProjectResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [reviewDialogOpen, setReviewDialogOpen] = useState(false);
  const [stageDates, setStageDates] = useState<Record<string, string | null>>({});

  const [profile, setProfile] = useState<ProjectProfile | null>(null);
  const [profileNotFound, setProfileNotFound] = useState(false);
  const [profileEditing, setProfileEditing] = useState(false);
  const [profileDraft, setProfileDraft] = useState<Partial<ProjectProfile>>({});
  const [extracting, setExtracting] = useState(false);
  const [exporting, setExporting] = useState(false);

  const { status: materialStatus, loading: statusLoading } = useReadinessChecker(id ?? '');
  const { resolve } = useLabelResolver();

  // Tag management state
  const PRESET_COLORS = ['#f5222d', '#fa8c16', '#fadb14', '#52c41a', '#13c2c2', '#1677ff', '#722ed1', '#eb2f96'];
  const [projectTags, setProjectTags] = useState<TagInfo[]>([]);
  const [allTags, setAllTags] = useState<TagInfo[]>([]);
  const [tagPopoverOpen, setTagPopoverOpen] = useState(false);
  const [creatingTag, setCreatingTag] = useState(false);
  const [newTagName, setNewTagName] = useState('');
  const [newTagColor, setNewTagColor] = useState(PRESET_COLORS[0]);

  useEffect(() => {
    if (!id) return;
    projectApi
      .get(id)
      .then((res) => setProject(res.data))
      .catch(() => {
        msg.error('项目不存在');
        navigate('/projects');
      })
      .finally(() => setLoading(false));
    projectApi
      .stageDates(id)
      .then((configs) => {
        const map: Record<string, string | null> = {};
        configs.forEach((c: StageConfig) => { map[c.stage] = c.stage_date; });
        setStageDates(map);
      })
      .catch(() => { /* stage dates are optional */ });
  }, [id, navigate]);

  // Fetch project profile
  useEffect(() => {
    if (!id) return;
    profileApi.get(id)
      .then((data) => {
        setProfile(data);
        setProfileNotFound(false);
      })
      .catch((err) => {
        if (err.response?.status === 404) {
          setProfileNotFound(true);
        }
      });
  }, [id]);

  // Fetch project tags and all user tags
  useEffect(() => {
    if (!id) return;
    tagApi.getProjectTags(id).then(setProjectTags).catch(() => {});
    tagApi.list().then(setAllTags).catch(() => {});
  }, [id]);

  const handleAddTagToProject = async (tagId: string) => {
    if (!id) return;
    try {
      const added = await tagApi.addToProject(id, tagId);
      setProjectTags((prev) => [...prev, added]);
      setTagPopoverOpen(false);
    } catch {
      msg.error('添加标签失败');
    }
  };

  const handleRemoveTagFromProject = async (tagId: string) => {
    if (!id) return;
    try {
      await tagApi.removeFromProject(id, tagId);
      setProjectTags((prev) => prev.filter((t) => t.id !== tagId));
    } catch {
      msg.error('移除标签失败');
    }
  };

  const handleCreateTag = async () => {
    if (!newTagName.trim()) return;
    try {
      const created = await tagApi.create({ name: newTagName.trim(), color: newTagColor });
      setAllTags((prev) => [...prev, created]);
      if (id) {
        const added = await tagApi.addToProject(id, created.id);
        setProjectTags((prev) => [...prev, added]);
      }
      setNewTagName('');
      setNewTagColor(PRESET_COLORS[0]);
      setCreatingTag(false);
      setTagPopoverOpen(false);
    } catch {
      msg.error('创建标签失败');
    }
  };

  if (loading || !project) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', paddingTop: 120 }}>
        <Spin size="large" />
      </div>
    );
  }

  const currentStageIdx = STAGES.indexOf(project.current_stage as CompetitionStage);

  const textReviewReady = materialStatus?.any_text_material_ready ?? false;
  const offlineReviewReady = materialStatus?.offline_review_ready ?? false;

  /** Build a tooltip string for a not-ready review card. */
  const getNotReadyTooltip = (type: 'text' | 'offline'): string => {
    if (statusLoading) return '正在检查材料状态…';
    if (!materialStatus) return '材料状态未知';
    if (type === 'text') {
      return '请先上传至少一种评审材料（BP、文本PPT或路演PPT）';
    }
    return materialStatus.offline_review_reasons.length > 0
      ? materialStatus.offline_review_reasons.join('；')
      : '请先上传路演视频';
  };

  /** Handle click on a review-type action card. */
  const handleReviewCardClick = () => {
    if (textReviewReady && offlineReviewReady) {
      setReviewDialogOpen(true);
    } else if (textReviewReady) {
      navigate(`/projects/${id}/text-review`);
    } else if (offlineReviewReady) {
      navigate(`/projects/${id}/offline-review`);
    } else {
      msg.info('请先前往材料中心上传所需材料');
    }
  };

  /** Render a readiness tag for review cards. */
  const renderReadinessTag = (ready: boolean) =>
    ready ? (
      <Tag color="success" style={{ marginLeft: 8 }}>就绪</Tag>
    ) : (
      <Tag color="default" style={{ marginLeft: 8 }}>材料未备齐</Tag>
    );

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

  /** Determine if a card is a review card and whether it's ready. */
  const getCardReadiness = (title: string): { isReview: boolean; ready: boolean } => {
    if (title === '文本评审') return { isReview: true, ready: textReviewReady };
    if (title === '离线评审') return { isReview: true, ready: offlineReviewReady };
    return { isReview: false, ready: true };
  };

  const handleExtractProfile = async () => {
    if (!id) return;
    setExtracting(true);
    try {
      const data = await profileApi.extract(id);
      setProfile(data);
      setProfileNotFound(false);
      msg.success('项目简介提取成功');
    } catch {
      msg.error('AI提取失败，请稍后重试或手动填写');
    } finally {
      setExtracting(false);
    }
  };

  const handleSaveProfile = async () => {
    if (!id) return;
    try {
      const data = await profileApi.update(id, profileDraft);
      setProfile(data);
      setProfileEditing(false);
      msg.success('项目简介已保存');
    } catch {
      msg.error('保存失败');
    }
  };

  const handleStartEdit = () => {
    if (profile) {
      setProfileDraft({
        team_intro: profile.team_intro ?? '',
        domain: profile.domain ?? '',
        startup_status: profile.startup_status ?? '',
        achievements: profile.achievements ?? '',
        product_links: profile.product_links ?? '',
        next_goals: profile.next_goals ?? '',
      });
    }
    setProfileEditing(true);
  };

  const handleCancelEdit = () => {
    setProfileEditing(false);
    setProfileDraft({});
  };

  const handleExport = async () => {
    if (!id) return;
    setExporting(true);
    try {
      const res = await api.get(`/projects/${id}/export`, { responseType: 'blob' });
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const link = document.createElement('a');
      link.href = url;
      link.download = `report_${id}.pdf`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch {
      msg.error('导出报告失败');
    } finally {
      setExporting(false);
    }
  };

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
              <Tag icon={<TrophyOutlined />} color="blue">{resolve('competition', project.competition)}</Tag>
              <Tag color="cyan">{resolve('track', project.track)}</Tag>
              <Tag color="geekblue">{resolve('group', project.group)}</Tag>
            </Space>
            {/* Project custom tags */}
            <Space size={6} wrap style={{ marginTop: 8 }}>
              {projectTags.map((t) => (
                <Tag
                  key={t.id}
                  color={t.color}
                  closable
                  onClose={(e) => { e.preventDefault(); handleRemoveTagFromProject(t.id); }}
                >
                  {t.name}
                </Tag>
              ))}
              <Popover
                open={tagPopoverOpen}
                onOpenChange={setTagPopoverOpen}
                trigger="click"
                placement="bottomLeft"
                content={
                  <div style={{ width: 220 }}>
                    {/* Existing tags not yet associated */}
                    {allTags
                      .filter((t) => !projectTags.some((pt) => pt.id === t.id))
                      .map((t) => (
                        <div
                          key={t.id}
                          style={{ padding: '4px 0', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6 }}
                          onClick={() => handleAddTagToProject(t.id)}
                        >
                          <span style={{ width: 12, height: 12, borderRadius: '50%', background: t.color, display: 'inline-block', flexShrink: 0 }} />
                          <span style={{ fontSize: 13 }}>{t.name}</span>
                        </div>
                      ))}
                    <Divider style={{ margin: '8px 0' }} />
                    {creatingTag ? (
                      <div>
                        <Input
                          size="small"
                          placeholder="标签名称"
                          value={newTagName}
                          onChange={(e) => setNewTagName(e.target.value)}
                          onPressEnter={handleCreateTag}
                          style={{ marginBottom: 8 }}
                        />
                        <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', marginBottom: 8 }}>
                          {PRESET_COLORS.map((c) => (
                            <span
                              key={c}
                              onClick={() => setNewTagColor(c)}
                              style={{
                                width: 20,
                                height: 20,
                                borderRadius: '50%',
                                background: c,
                                cursor: 'pointer',
                                border: newTagColor === c ? '2px solid #333' : '2px solid transparent',
                              }}
                            />
                          ))}
                        </div>
                        <Space size={4}>
                          <Button size="small" type="primary" onClick={handleCreateTag}>确定</Button>
                          <Button size="small" onClick={() => { setCreatingTag(false); setNewTagName(''); }}>取消</Button>
                        </Space>
                      </div>
                    ) : (
                      <div
                        style={{ padding: '4px 0', cursor: 'pointer', color: '#1677ff', fontSize: 13 }}
                        onClick={() => setCreatingTag(true)}
                      >
                        <PlusOutlined style={{ marginRight: 4 }} />新建标签
                      </div>
                    )}
                  </div>
                }
              >
                <Tag
                  icon={<TagOutlined />}
                  style={{ cursor: 'pointer', borderStyle: 'dashed' }}
                >
                  添加标签
                </Tag>
              </Popover>
            </Space>
          </div>
          <Space direction="vertical" align="end" size={8}>
            <Text type="secondary" style={{ fontSize: 13 }}>
              创建于 {new Date(project.created_at).toLocaleDateString('zh-CN')}
            </Text>
            <Button
              icon={<DownloadOutlined />}
              loading={exporting}
              onClick={handleExport}
              size="small"
            >
              导出项目报告
            </Button>
          </Space>
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
          items={STAGES.map((s) => ({
            title: STAGE_LABELS[s],
            description: stageDates[s] ?? '待定',
          }))}
          style={{ marginBottom: 8 }}
        />
      </Card>

      {/* Project profile card */}
      <Card
        title="项目简介"
        style={{ borderRadius: 12, marginBottom: 24 }}
        styles={{ body: { padding: '20px 24px' } }}
        extra={
          profile && !profileEditing ? (
            <Space>
              <Tag
                icon={profile.is_ai_generated ? <RobotOutlined /> : <UserOutlined />}
                color={profile.is_ai_generated ? 'blue' : 'green'}
              >
                {profile.is_ai_generated ? 'AI生成' : '用户编辑'}
              </Tag>
              <Button size="small" icon={<EditOutlined />} onClick={handleStartEdit}>编辑</Button>
              <Button size="small" icon={<SyncOutlined />} loading={extracting} onClick={handleExtractProfile}>重新提取</Button>
            </Space>
          ) : undefined
        }
      >
        {profileNotFound && !profile ? (
          <div style={{ textAlign: 'center', padding: '24px 0' }}>
            <Text type="secondary" style={{ display: 'block', marginBottom: 12 }}>
              暂无项目简介，可通过AI从BP和文本PPT中自动提取
            </Text>
            <Button type="primary" icon={<RobotOutlined />} loading={extracting} onClick={handleExtractProfile}>
              AI提取简介
            </Button>
          </div>
        ) : profile && profileEditing ? (
          <>
            <Descriptions column={1} bordered size="small">
              <Descriptions.Item label="团队介绍">
                <Input.TextArea
                  rows={2}
                  value={profileDraft.team_intro ?? ''}
                  onChange={(e) => setProfileDraft((d) => ({ ...d, team_intro: e.target.value }))}
                />
              </Descriptions.Item>
              <Descriptions.Item label="所属领域">
                <Input
                  value={profileDraft.domain ?? ''}
                  onChange={(e) => setProfileDraft((d) => ({ ...d, domain: e.target.value }))}
                />
              </Descriptions.Item>
              <Descriptions.Item label="创业状态">
                <Input
                  value={profileDraft.startup_status ?? ''}
                  onChange={(e) => setProfileDraft((d) => ({ ...d, startup_status: e.target.value }))}
                />
              </Descriptions.Item>
              <Descriptions.Item label="已有成果">
                <Input.TextArea
                  rows={2}
                  value={profileDraft.achievements ?? ''}
                  onChange={(e) => setProfileDraft((d) => ({ ...d, achievements: e.target.value }))}
                />
              </Descriptions.Item>
              <Descriptions.Item label="产品链接">
                <Input
                  value={profileDraft.product_links ?? ''}
                  onChange={(e) => setProfileDraft((d) => ({ ...d, product_links: e.target.value }))}
                />
              </Descriptions.Item>
              <Descriptions.Item label="下一步目标">
                <Input.TextArea
                  rows={2}
                  value={profileDraft.next_goals ?? ''}
                  onChange={(e) => setProfileDraft((d) => ({ ...d, next_goals: e.target.value }))}
                />
              </Descriptions.Item>
            </Descriptions>
            <div style={{ marginTop: 12, textAlign: 'right' }}>
              <Space>
                <Button onClick={handleCancelEdit}>取消</Button>
                <Button type="primary" onClick={handleSaveProfile}>保存</Button>
              </Space>
            </div>
          </>
        ) : profile ? (
          <Descriptions column={1} bordered size="small">
            <Descriptions.Item label="团队介绍">{profile.team_intro || '-'}</Descriptions.Item>
            <Descriptions.Item label="所属领域">{profile.domain || '-'}</Descriptions.Item>
            <Descriptions.Item label="创业状态">{profile.startup_status || '-'}</Descriptions.Item>
            <Descriptions.Item label="已有成果">{profile.achievements || '-'}</Descriptions.Item>
            <Descriptions.Item label="产品链接">{profile.product_links || '-'}</Descriptions.Item>
            <Descriptions.Item label="下一步目标">{profile.next_goals || '-'}</Descriptions.Item>
          </Descriptions>
        ) : null}
      </Card>

      {/* Quick actions */}
      <Title level={5} style={{ color: '#1a365d', marginBottom: 16 }}>
        快捷操作
      </Title>
      <Row gutter={[16, 16]}>
        {actions.map((a) => {
          const { isReview, ready } = getCardReadiness(a.title);
          const greyedOut = isReview && !ready;
          const tooltipType = a.title === '文本评审' ? 'text' : 'offline';

          const cardContent = (
            <Card
              hoverable={!greyedOut}
              onClick={() => {
                if (isReview) {
                  handleReviewCardClick();
                } else {
                  navigate(a.path);
                }
              }}
              style={{
                borderRadius: 12,
                height: '100%',
                opacity: greyedOut ? 0.55 : 1,
                cursor: greyedOut ? 'default' : 'pointer',
              }}
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
                  color: greyedOut ? '#999' : a.color,
                  marginBottom: 12,
                }}
              >
                {a.icon}
              </div>
              <div style={{ display: 'flex', alignItems: 'center', marginBottom: 4 }}>
                <Title level={5} style={{ margin: 0 }}>{a.title}</Title>
                {isReview && !statusLoading && renderReadinessTag(ready)}
              </div>
              <Text type="secondary" style={{ fontSize: 13 }}>
                {greyedOut ? getNotReadyTooltip(tooltipType) : a.desc}
              </Text>
            </Card>
          );

          return (
            <Col xs={24} sm={12} md={8} key={a.title}>
              {greyedOut ? (
                <Tooltip title={getNotReadyTooltip(tooltipType)}>
                  {cardContent}
                </Tooltip>
              ) : (
                cardContent
              )}
            </Col>
          );
        })}
      </Row>

      {/* Review selection dialog */}
      <ReviewSelectionDialog
        open={reviewDialogOpen}
        onClose={() => setReviewDialogOpen(false)}
        projectId={id ?? ''}
        textReviewReady={textReviewReady}
        offlineReviewReady={offlineReviewReady}
      />
    </div>
  );
}
