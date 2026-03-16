import { useEffect, useState } from 'react';
import { Select, Typography, Divider, Spin, Tag } from 'antd';
import { SoundOutlined } from '@ant-design/icons';
import { voiceApi } from '@/services/api';
import type { PresetVoiceInfo, CustomVoiceInfo } from '@/types';

const { Text } = Typography;

interface Props {
  value?: string;
  voiceType?: string;
  onChange?: (voiceId: string, voiceType: 'preset' | 'custom') => void;
}

export default function VoiceSelector({ value = 'Cherry', voiceType = 'preset', onChange }: Props) {
  const [presets, setPresets] = useState<PresetVoiceInfo[]>([]);
  const [customs, setCustoms] = useState<CustomVoiceInfo[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([voiceApi.presets(), voiceApi.customList()])
      .then(([p, c]) => {
        setPresets(p.data);
        setCustoms(c.data);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <Spin size="small" />;

  const currentValue = `${voiceType}:${value}`;

  return (
    <Select
      value={currentValue}
      onChange={(v: string) => {
        const [type, id] = v.split(':');
        onChange?.(id, type as 'preset' | 'custom');
      }}
      style={{ width: 280 }}
      placeholder="选择AI评委音色"
      optionLabelProp="label"
    >
      <Select.OptGroup label="预设音色">
        {presets.map((p) => (
          <Select.Option key={`preset:${p.voice}`} value={`preset:${p.voice}`} label={`${p.name} (${p.voice})`}>
            <SoundOutlined /> {p.name}（{p.voice}）
            <Text type="secondary" style={{ marginLeft: 8, fontSize: 12 }}>{p.description}</Text>
          </Select.Option>
        ))}
      </Select.OptGroup>
      {customs.length > 0 && (
        <Select.OptGroup label="自定义音色">
          {customs.map((c) => (
            <Select.Option key={`custom:${c.id}`} value={`custom:${c.id}`} label={c.preferred_name}>
              <SoundOutlined /> {c.preferred_name}
              <Tag color="orange" style={{ marginLeft: 8 }}>TTS模式·延迟较高</Tag>
            </Select.Option>
          ))}
        </Select.OptGroup>
      )}
    </Select>
  );
}
