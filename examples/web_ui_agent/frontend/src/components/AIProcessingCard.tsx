import { useEffect, useState } from 'react';
import { Card, Progress, Typography, Space } from 'antd';
import { LoadingOutlined } from '@ant-design/icons';

const { Text } = Typography;

interface AIProcessingCardProps {
  /** 主标题，如 "正在进行文本评审" */
  title: string;
  /** 预估耗时描述，如 "预计需要 1~3 分钟" */
  estimate?: string;
  /** 分步骤提示，按时间依次展示 */
  steps?: string[];
  /** 每个步骤展示的间隔秒数，默认 8 */
  stepInterval?: number;
  style?: React.CSSProperties;
}

export default function AIProcessingCard({
  title,
  estimate,
  steps = [],
  stepInterval = 8,
  style,
}: AIProcessingCardProps) {
  const [elapsed, setElapsed] = useState(0);
  const [currentStep, setCurrentStep] = useState(0);

  useEffect(() => {
    const timer = setInterval(() => setElapsed((s) => s + 1), 1000);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    if (steps.length <= 1) return;
    const timer = setInterval(() => {
      setCurrentStep((prev) => (prev < steps.length - 1 ? prev + 1 : prev));
    }, stepInterval * 1000);
    return () => clearInterval(timer);
  }, [steps, stepInterval]);

  const minutes = Math.floor(elapsed / 60);
  const seconds = elapsed % 60;
  const timeStr = minutes > 0
    ? `${minutes}分${seconds.toString().padStart(2, '0')}秒`
    : `${seconds}秒`;

  return (
    <Card style={{ textAlign: 'center', ...style }}>
      <Space direction="vertical" size="middle" style={{ width: '100%', maxWidth: 400, margin: '0 auto' }}>
        <LoadingOutlined style={{ fontSize: 36, color: '#1677ff' }} />
        <Text strong style={{ fontSize: 16 }}>{title}</Text>
        {steps.length > 0 && (
          <Text type="secondary">{steps[currentStep]}</Text>
        )}
        <Progress percent={99.9} status="active" showInfo={false} />
        <Space size="large">
          <Text type="secondary">已用时 {timeStr}</Text>
          {estimate && <Text type="secondary">{estimate}</Text>}
        </Space>
      </Space>
    </Card>
  );
}
