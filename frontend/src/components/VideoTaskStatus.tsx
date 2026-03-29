import { Tag } from 'antd';
import {
  SyncOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  WarningOutlined,
} from '@ant-design/icons';

interface VideoTaskStatusProps {
  status: 'pending' | 'processing' | 'completed' | 'failed' | 'outdated' | null | undefined;
  persistentUrl?: string | null;
  compact?: boolean;
}

export default function VideoTaskStatus({ status, persistentUrl, compact }: VideoTaskStatusProps) {
  if (!status) return null;

  if (status === 'pending' || status === 'processing') {
    return (
      <Tag icon={<SyncOutlined spin />} color="blue">
        生成中
      </Tag>
    );
  }

  if (status === 'completed') {
    if (persistentUrl) {
      return (
        <Tag icon={<CheckCircleOutlined />} color="green">
          已就绪
        </Tag>
      );
    }
    return (
      <Tag icon={<WarningOutlined />} color="orange">
        视频不可用
      </Tag>
    );
  }

  if (status === 'failed') {
    return (
      <Tag icon={<CloseCircleOutlined />} color="red">
        视频生成失败
      </Tag>
    );
  }

  if (status === 'outdated') {
    return (
      <Tag icon={<WarningOutlined />} color="orange">
        已过期
      </Tag>
    );
  }

  return null;
}
