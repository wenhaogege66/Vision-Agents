import { useState } from 'react';
import { Card, Upload, Button, Input, Alert, Space } from 'antd';
import { msg } from '@/utils/messageHolder';
import { AudioOutlined, UploadOutlined } from '@ant-design/icons';
import { voiceApi } from '@/services/api';

interface Props {
  onCloned?: () => void;
}

export default function VoiceClonePanel({ onCloned }: Props) {
  const [file, setFile] = useState<File | null>(null);
  const [name, setName] = useState('');
  const [loading, setLoading] = useState(false);

  const handleClone = async () => {
    if (!file) { msg.warning('请先上传音频文件'); return; }
    if (!name.trim()) { msg.warning('请输入音色名称'); return; }
    setLoading(true);
    try {
      await voiceApi.clone(file, name.trim());
      msg.success('声音复刻成功');
      setFile(null);
      setName('');
      onCloned?.();
    } catch (err: unknown) {
      const errMsg =
        (err as { response?: { data?: { message?: string } } })?.response?.data
          ?.message ?? '声音复刻失败';
      msg.error(errMsg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card title={<><AudioOutlined /> 声音复刻</>} size="small">
      <Alert
        type="info"
        showIcon
        message="录音指南"
        description="请上传10~20秒清晰的语音音频（WAV/MP3/M4A，≥24kHz采样率，单声道），避免背景噪音。"
        style={{ marginBottom: 12 }}
      />
      <Space orientation="vertical" style={{ width: '100%' }}>
        <Upload
          beforeUpload={(f) => { setFile(f); return false; }}
          accept=".wav,.mp3,.m4a"
          maxCount={1}
          fileList={file ? [{ uid: '1', name: file.name, status: 'done' }] : []}
          onRemove={() => setFile(null)}
        >
          <Button icon={<UploadOutlined />}>选择音频文件</Button>
        </Upload>
        <Input
          placeholder="为音色命名"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <Button type="primary" onClick={handleClone} loading={loading} block>
          开始复刻
        </Button>
      </Space>
    </Card>
  );
}
