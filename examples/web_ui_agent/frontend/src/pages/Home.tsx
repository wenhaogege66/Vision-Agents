import { useNavigate } from 'react-router-dom';
import { Typography, Row, Col, Card, theme } from 'antd';
import {
  FileTextOutlined,
  VideoCameraOutlined,
  ProjectOutlined,
  TrophyOutlined,
} from '@ant-design/icons';

const { Title, Paragraph } = Typography;

const FEATURES = [
  {
    icon: <FileTextOutlined style={{ fontSize: 40 }} />,
    title: 'AI文本评审',
    desc: '上传PPT和商业计划书，AI按照官方评审标准进行多维度评分与建议',
    color: '#1677ff',
    path: '/projects',
  },
  {
    icon: <VideoCameraOutlined style={{ fontSize: 40 }} />,
    title: '现场路演模拟',
    desc: '实时音视频与AI评委互动，模拟真实答辩场景，支持提问和建议模式',
    color: '#52c41a',
    path: '/projects',
  },
  {
    icon: <ProjectOutlined style={{ fontSize: 40 }} />,
    title: '项目管理',
    desc: '管理多个参赛项目，追踪从校赛到国赛的完整比赛时间线',
    color: '#fa8c16',
    path: '/projects',
  },
  {
    icon: <TrophyOutlined style={{ fontSize: 40 }} />,
    title: '多赛事支持',
    desc: '覆盖国创赛、大挑、小挑，自动匹配赛道和组别的评审规则',
    color: '#eb2f96',
    path: '/projects',
  },
];

export default function Home() {
  const navigate = useNavigate();
  const { token } = theme.useToken();

  return (
    <div style={{ padding: '48px 24px', maxWidth: 960, margin: '0 auto' }}>
      <div style={{ textAlign: 'center', marginBottom: 56 }}>
        <div style={{ fontSize: 56, marginBottom: 16 }}>🏆</div>
        <Title level={2} style={{ marginBottom: 8, fontSize: 28, letterSpacing: -0.5 }}>
          中国大学生创新大赛 AI 评委系统
        </Title>
        <Paragraph
          style={{
            fontSize: 16,
            color: token.colorTextSecondary,
            maxWidth: 520,
            margin: '0 auto',
          }}
        >
          基于多模态AI的智能评审平台，助你在国创赛、大挑、小挑中脱颖而出
        </Paragraph>
      </div>

      <Row gutter={[20, 20]}>
        {FEATURES.map((f) => (
          <Col xs={24} sm={12} key={f.title}>
            <Card
              hoverable
              onClick={() => navigate(f.path)}
              style={{
                borderRadius: 12,
                height: '100%',
                borderColor: token.colorBorderSecondary,
                transition: 'box-shadow 0.25s, border-color 0.25s',
              }}
              styles={{
                body: { padding: 28 },
              }}
            >
              <div
                style={{
                  width: 64,
                  height: 64,
                  borderRadius: 14,
                  background: `${f.color}10`,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: f.color,
                  marginBottom: 20,
                }}
              >
                {f.icon}
              </div>
              <Title level={4} style={{ marginBottom: 8 }}>
                {f.title}
              </Title>
              <Paragraph style={{ color: token.colorTextSecondary, marginBottom: 0 }}>
                {f.desc}
              </Paragraph>
            </Card>
          </Col>
        ))}
      </Row>
    </div>
  );
}
