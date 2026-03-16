import { useState } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { Form, Input, Button, Typography, message, Space } from 'antd';
import {
  MailOutlined,
  LockOutlined,
  TrophyOutlined,
} from '@ant-design/icons';
import { useAuth } from '@/contexts/AuthContext';
import type { LoginRequest } from '@/types';

const { Title, Text, Paragraph } = Typography;

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [loading, setLoading] = useState(false);

  const from = (location.state as { from?: { pathname: string } })?.from
    ?.pathname ?? '/';

  const onFinish = async (values: LoginRequest) => {
    setLoading(true);
    try {
      await login(values);
      message.success('登录成功');
      navigate(from, { replace: true });
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { message?: string } } })?.response?.data
          ?.message ?? '登录失败，请检查邮箱和密码';
      message.error(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={styles.wrapper}>
      {/* Left branding panel */}
      <div style={styles.brandPanel}>
        <div style={styles.brandContent}>
          <TrophyOutlined style={styles.brandIcon} />
          <Title level={2} style={styles.brandTitle}>
            中国大学生创新大赛
          </Title>
          <Title level={3} style={styles.brandSubtitle}>
            AI 评委系统
          </Title>
          <Paragraph style={styles.brandDesc}>
            基于多模态AI的智能评审平台，为参赛团队提供专业的文本评审、路演模拟与评分反馈服务。
          </Paragraph>
          <Space direction="vertical" size={4} style={{ marginTop: 32 }}>
            <Text style={styles.featureItem}>✦ 多维度智能评分</Text>
            <Text style={styles.featureItem}>✦ 实时路演AI评委</Text>
            <Text style={styles.featureItem}>✦ 多种评委风格可选</Text>
          </Space>
        </div>
      </div>

      {/* Right form panel */}
      <div style={styles.formPanel}>
        <div style={styles.formContainer}>
          <Title level={3} style={styles.formTitle}>
            欢迎回来
          </Title>
          <Text type="secondary" style={{ marginBottom: 32, display: 'block' }}>
            登录您的账户以继续
          </Text>

          <Form
            layout="vertical"
            onFinish={onFinish}
            size="large"
            requiredMark={false}
          >
            <Form.Item
              name="email"
              label="邮箱"
              rules={[
                { required: true, message: '请输入邮箱' },
                { type: 'email', message: '请输入有效的邮箱地址' },
              ]}
            >
              <Input prefix={<MailOutlined />} placeholder="your@email.com" />
            </Form.Item>

            <Form.Item
              name="password"
              label="密码"
              rules={[{ required: true, message: '请输入密码' }]}
            >
              <Input.Password
                prefix={<LockOutlined />}
                placeholder="输入密码"
              />
            </Form.Item>

            <Form.Item style={{ marginTop: 8 }}>
              <Button
                type="primary"
                htmlType="submit"
                loading={loading}
                block
                style={styles.submitBtn}
              >
                登 录
              </Button>
            </Form.Item>
          </Form>

          <div style={{ textAlign: 'center', marginTop: 16 }}>
            <Text type="secondary">还没有账户？</Text>{' '}
            <Link to="/register">立即注册</Link>
          </div>
        </div>
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  wrapper: {
    display: 'flex',
    minHeight: '100vh',
  },
  brandPanel: {
    flex: '0 0 45%',
    background: 'linear-gradient(135deg, #1a365d 0%, #2a4a7f 50%, #1a365d 100%)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    padding: '48px 40px',
    position: 'relative',
    overflow: 'hidden',
  },
  brandContent: {
    position: 'relative',
    zIndex: 1,
    maxWidth: 400,
  },
  brandIcon: {
    fontSize: 56,
    color: 'rgba(255,255,255,0.9)',
    marginBottom: 24,
  },
  brandTitle: {
    color: '#fff',
    margin: '0 0 4px',
    fontWeight: 600,
    letterSpacing: 1,
  },
  brandSubtitle: {
    color: 'rgba(255,255,255,0.85)',
    margin: '0 0 20px',
    fontWeight: 400,
  },
  brandDesc: {
    color: 'rgba(255,255,255,0.7)',
    fontSize: 15,
    lineHeight: 1.8,
  },
  featureItem: {
    color: 'rgba(255,255,255,0.8)',
    fontSize: 14,
  },
  formPanel: {
    flex: 1,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    padding: '48px 40px',
    background: '#f8f7f4',
  },
  formContainer: {
    width: '100%',
    maxWidth: 400,
  },
  formTitle: {
    marginBottom: 4,
    fontWeight: 600,
  },
  submitBtn: {
    height: 44,
    fontWeight: 500,
    letterSpacing: 2,
  },
};
