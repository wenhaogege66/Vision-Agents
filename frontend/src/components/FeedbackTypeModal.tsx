import { Modal, Card, Typography, Flex } from 'antd';
import { FileTextOutlined, VideoCameraOutlined } from '@ant-design/icons';

const { Text, Title } = Typography;

interface FeedbackTypeModalProps {
  open: boolean;
  onSelect: (type: 'text' | 'video') => void;
}

const cardBodyStyle = { textAlign: 'center' as const, padding: 24 };

export default function FeedbackTypeModal({ open, onSelect }: FeedbackTypeModalProps) {
  return (
    <Modal
      title="选择反馈方式"
      open={open}
      footer={null}
      closable={false}
      maskClosable={false}
      width={520}
      destroyOnHidden
    >
      <Flex gap={16}>
        <Card
          hoverable
          onClick={() => onSelect('text')}
          style={{ flex: 1, cursor: 'pointer' }}
          styles={{ body: cardBodyStyle }}
        >
          <FileTextOutlined style={{ fontSize: 36, color: '#1890ff', marginBottom: 12 }} />
          <Title level={5} style={{ marginBottom: 4 }}>文本反馈</Title>
          <Text type="secondary" style={{ fontSize: 12 }}>
            直接显示AI评委的文字反馈，速度快
          </Text>
        </Card>

        <Card
          hoverable
          onClick={() => onSelect('video')}
          style={{ flex: 1, cursor: 'pointer' }}
          styles={{ body: cardBodyStyle }}
        >
          <VideoCameraOutlined style={{ fontSize: 36, color: '#52c41a', marginBottom: 12 }} />
          <Title level={5} style={{ marginBottom: 4 }}>视频反馈</Title>
          <Text type="secondary" style={{ fontSize: 12 }}>
            生成数字人评委视频反馈，需等待1-2分钟
          </Text>
        </Card>
      </Flex>
    </Modal>
  );
}
