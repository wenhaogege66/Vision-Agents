import { useNavigate } from 'react-router-dom';
import { Modal, Card, Typography, Row, Col } from 'antd';
import {
  FileTextOutlined,
  VideoCameraOutlined,
  AppstoreOutlined,
} from '@ant-design/icons';

const { Text, Title } = Typography;

interface ReviewSelectionDialogProps {
  open: boolean;
  onClose: () => void;
  projectId: string;
  textReviewReady: boolean;
  offlineReviewReady: boolean;
}

const cardBodyStyle = { textAlign: 'center' as const, padding: 24 };

export default function ReviewSelectionDialog({
  open,
  onClose,
  projectId,
  textReviewReady,
  offlineReviewReady,
}: ReviewSelectionDialogProps) {
  const navigate = useNavigate();

  const handleSelect = (target: 'text' | 'offline' | 'both') => {
    onClose();
    if (target === 'text') {
      navigate(`/projects/${projectId}/text-review`);
    } else if (target === 'offline') {
      navigate(`/projects/${projectId}/offline-review`);
    } else {
      // "both" – navigate to text review first; user can do offline afterwards
      navigate(`/projects/${projectId}/text-review`);
    }
  };

  return (
    <Modal
      title="选择评审类型"
      open={open}
      onCancel={onClose}
      footer={null}
      width={640}
      destroyOnClose
    >
      <Text type="secondary" style={{ display: 'block', marginBottom: 16 }}>
        当前项目有多种评审类型可用，请选择您要进行的评审：
      </Text>

      <Row gutter={16}>
        <Col span={8}>
          <Card
            hoverable={textReviewReady}
            onClick={() => textReviewReady && handleSelect('text')}
            style={{
              opacity: textReviewReady ? 1 : 0.5,
              cursor: textReviewReady ? 'pointer' : 'not-allowed',
            }}
            styles={{ body: cardBodyStyle }}
          >
            <FileTextOutlined style={{ fontSize: 32, color: '#1890ff', marginBottom: 12 }} />
            <Title level={5} style={{ marginBottom: 4 }}>仅文本评审</Title>
            <Text type="secondary" style={{ fontSize: 12 }}>
              基于BP和PPT进行AI文本评审
            </Text>
          </Card>
        </Col>

        <Col span={8}>
          <Card
            hoverable={offlineReviewReady}
            onClick={() => offlineReviewReady && handleSelect('offline')}
            style={{
              opacity: offlineReviewReady ? 1 : 0.5,
              cursor: offlineReviewReady ? 'pointer' : 'not-allowed',
            }}
            styles={{ body: cardBodyStyle }}
          >
            <VideoCameraOutlined style={{ fontSize: 32, color: '#52c41a', marginBottom: 12 }} />
            <Title level={5} style={{ marginBottom: 4 }}>仅离线路演评审</Title>
            <Text type="secondary" style={{ fontSize: 12 }}>
              基于路演视频进行AI评审
            </Text>
          </Card>
        </Col>

        <Col span={8}>
          <Card
            hoverable={textReviewReady && offlineReviewReady}
            onClick={() =>
              textReviewReady && offlineReviewReady && handleSelect('both')
            }
            style={{
              opacity: textReviewReady && offlineReviewReady ? 1 : 0.5,
              cursor:
                textReviewReady && offlineReviewReady ? 'pointer' : 'not-allowed',
            }}
            styles={{ body: cardBodyStyle }}
          >
            <AppstoreOutlined style={{ fontSize: 32, color: '#722ed1', marginBottom: 12 }} />
            <Title level={5} style={{ marginBottom: 4 }}>两者都评审</Title>
            <Text type="secondary" style={{ fontSize: 12 }}>
              同时进行文本评审和离线路演评审
            </Text>
          </Card>
        </Col>
      </Row>
    </Modal>
  );
}
