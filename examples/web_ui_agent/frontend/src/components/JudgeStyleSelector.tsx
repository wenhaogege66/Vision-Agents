import { useEffect, useState } from 'react';
import { Radio, Space, Spin, Typography } from 'antd';
import { judgeStyleApi } from '@/services/api';
import type { JudgeStyleInfo } from '@/types';

const { Text } = Typography;

interface Props {
  value?: string;
  onChange?: (value: string) => void;
}

export default function JudgeStyleSelector({ value = 'strict', onChange }: Props) {
  const [styles, setStyles] = useState<JudgeStyleInfo[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    judgeStyleApi.list().then((res) => {
      setStyles(res.data);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  if (loading) return <Spin size="small" />;

  return (
    <Radio.Group value={value} onChange={(e) => onChange?.(e.target.value)}>
      <Space direction="vertical">
        {styles.map((s) => (
          <Radio key={s.id} value={s.id}>
            <Text strong>{s.name}</Text>
            <Text type="secondary" style={{ marginLeft: 8 }}>{s.description}</Text>
          </Radio>
        ))}
      </Space>
    </Radio.Group>
  );
}
