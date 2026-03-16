import { useState } from 'react';
import { useParams } from 'react-router-dom';
import { Button, Card, message, Space, Typography, Divider, Row, Col } from 'antd';
import { PlayCircleOutlined, StopOutlined } from '@ant-design/icons';
import ModeSwitch from '@/components/ModeSwitch';
import VoiceSelector from '@/components/VoiceSelector';
import VoiceClonePanel from '@/components/VoiceClonePanel';
import JudgeStyleSelector from '@/components/JudgeStyleSelector';
import { liveApi } from '@/services/api';

const { Title, Text } = Typography;

export default function LivePresentation() {
  const { projectId } = useParams<{ projectId: string }>();
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [mode, setMode] = useState('question');
  const [style, setStyle] = useState('strict');
  const [voice, setVoice] = useState('Cherry');
  const [voiceType, setVoiceType] = useState<'preset' | 'custom'>('preset');
  const [starting, setStarting] = useState(false);
  const [ending, setEnding] = useState(false);
  const [switching, setSwitching] = useState(false);

  const handleStart = async () => {
    if (!projectId) return;
    setStarting(true);
    try {
      const res = await liveApi.start(projectId, { mode, style, voice, voice_type: voiceType });
      setSessionId(res.data.session_id);
      message.success('路演会话已创建');
    } catch (err: any) {
      message.error(err.response?.data?.message ?? '创建路演会话失败');
    } finally {
      setStarting(false);
    }
  };

  const handleModeSwitch = async (newMode: string) => {
    if (!projectId || !sessionId) return;
    setSwitching(true);
    try {
      await liveApi.switchMode(projectId, { session_id: sessionId, mode: newMode });
      setMode(newMode);
    } catch {
      message.error('模式切换失败');
    } finally {
      setSwitching(false);
    }
  };

  const handleEnd = async () => {
    if (!projectId || !sessionId) return;
    setEnding(true);
    try {
      await liveApi.end(projectId, sessionId);
      message.success('路演已结束，评审总结已生成');
      setSessionId(null);
    } catch {
      message.error('结束路演失败');
    } finally {
      setEnding(false);
    }
  };

  return (
    <div style={{ padding: 24 }}>
      <Title level={3}>现场路演</Title>
      <Text type="secondary" style={{ display: 'block', marginBottom: 24 }}>
        通过实时音视频与AI评委进行路演互动，模拟真实答辩场景。
      </Text>

      {!sessionId ? (
        <Row gutter={[16, 16]}>
          <Col xs={24} md={16}>
            <Card title="路演设置">
              <Space direction="vertical" size="middle" style={{ width: '100%' }}>
                <div>
                  <Text strong style={{ display: 'block', marginBottom: 8 }}>评委风格</Text>
                  <JudgeStyleSelector value={style} onChange={setStyle} />
                </div>
                <div>
                  <Text strong style={{ display: 'block', marginBottom: 8 }}>AI评委音色</Text>
                  <VoiceSelector
                    value={voice}
                    voiceType={voiceType}
                    onChange={(v, t) => { setVoice(v); setVoiceType(t); }}
                  />
                </div>
                <div>
                  <Text strong style={{ display: 'block', marginBottom: 8 }}>初始交互模式</Text>
                  <ModeSwitch value={mode} onChange={setMode} />
                </div>
                <Divider />
                <Button
                  type="primary"
                  size="large"
                  icon={<PlayCircleOutlined />}
                  onClick={handleStart}
                  loading={starting}
                  block
                >
                  开始路演
                </Button>
              </Space>
            </Card>
          </Col>
          <Col xs={24} md={8}>
            <VoiceClonePanel />
          </Col>
        </Row>
      ) : (
        <Card title="路演进行中">
          <Space direction="vertical" size="large" style={{ width: '100%' }} align="center">
            <div
              style={{
                width: '100%',
                height: 400,
                background: '#000',
                borderRadius: 8,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <Text style={{ color: '#fff', fontSize: 18 }}>
                GetStream 视频通话区域（会话 ID: {sessionId}）
              </Text>
            </div>
            <ModeSwitch value={mode} onChange={handleModeSwitch} disabled={switching} />
            <Button
              danger
              size="large"
              icon={<StopOutlined />}
              onClick={handleEnd}
              loading={ending}
            >
              结束路演
            </Button>
          </Space>
        </Card>
      )}
    </div>
  );
}
