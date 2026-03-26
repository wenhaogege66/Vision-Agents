import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Form, Input, Button, Typography, Space } from 'antd';
import { msg } from '@/utils/messageHolder';
import {
  MailOutlined,
  LockOutlined,
  UserOutlined,
  TrophyOutlined,
} from '@ant-design/icons';
import { useAuth } from '@/contexts/AuthContext';
import type { RegisterRequest } from '@/types';

const { Title, Text, Paragraph } = Typography;

export default function Register() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);

  const onFinish = async (values: RegisterRequest) => {
    setLoading(true);
    try {
      await register(values);
      msg.success('注册成功');
      navigate('/', { replace: true });
    } catch (err: unknown) {
      if ((err as { emailConfirmationRequired?: boolean })?.emailConfirmationRequired) {
        msg.success('注册成功！请前往邮箱点击确认链接后再登录');
        navigate('/login', { replace: true });
        return;
      }
      const errMsg =
        (err as { response?: { data?: { message?: string } } })?.response?.data
          ?.message ?? '注册失败，请稍后重试';
      msg.error(errMsg);
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
            注册账户后，您可以创建参赛项目、上传材料并获取AI评委的专业评审反馈。
          </Paragraph>
          <Space orientation="vertical" size={4} style={{ marginTop: 32 }}>
            <Text style={styles.featureItem}>✦ 支持国创赛 / 大挑 / 小挑</Text>
            <Text style={styles.featureItem}>✦ 校赛到国赛全流程覆盖</Text>
            <Text style={styles.featureItem}>✦ 评审历史记录与对比</Text>
          </Space>
        </div>
      </div>

      {/* Right form panel */}
      <div style={styles.formPanel}>
        <div style={styles.formContainer}>
          <Title level={3} style={styles.formTitle}>
            创建账户
          </Title>
          <Text type="secondary" style={{ marginBottom: 32, display: 'block' }}>
            填写以下信息完成注册
          </Text>

          <Form
            layout="vertical"
            onFinish={onFinish}
            size="large"
            requiredMark={false}
          >
            <Form.Item
              name="display_name"
              label="姓名"
              rules={[{ required: true, message: '请输入您的姓名' }]}
            >
              <Input prefix={<UserOutlined />} placeholder="您的姓名" />
            </Form.Item>

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
              rules={[
                { required: true, message: '请输入密码' },
                { min: 6, message: '密码至少6个字符' },
              ]}
            >
              <Input.Password
                prefix={<LockOutlined />}
                placeholder="至少6个字符"
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
                注 册
              </Button>
            </Form.Item>
          </Form>

          <div style={{ textAlign: 'center', marginTop: 16 }}>
            <Text type="secondary">已有账户？</Text>{' '}
            <Link to="/login">返回登录</Link>
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
