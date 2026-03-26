import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, Form, Input, Button, Typography, Space } from 'antd';
import { msg } from '@/utils/messageHolder';
import { ArrowLeftOutlined, ProjectOutlined } from '@ant-design/icons';
import CompetitionSelector, {
  type CompetitionSelection,
} from '@/components/CompetitionSelector';
import { projectApi } from '@/services/api';

const { Title, Text } = Typography;

export default function ProjectCreate() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [selection, setSelection] = useState<CompetitionSelection | null>(null);
  const [form] = Form.useForm();

  const onFinish = async (values: { name: string }) => {
    if (!selection) {
      msg.warning('请完成赛事、赛道和组别的选择');
      return;
    }
    setLoading(true);
    try {
      const res = await projectApi.create({
        name: values.name,
        ...selection,
      });
      msg.success('项目创建成功');
      navigate(`/projects/${res.data.id}`);
    } catch (err: unknown) {
      const errMsg =
        (err as { response?: { data?: { message?: string } } })?.response?.data
          ?.message ?? '创建失败，请稍后重试';
      msg.error(errMsg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ maxWidth: 640, margin: '0 auto', padding: '32px 24px' }}>
      <Space style={{ marginBottom: 24 }}>
        <Button
          type="text"
          icon={<ArrowLeftOutlined />}
          onClick={() => navigate('/projects')}
        >
          返回项目列表
        </Button>
      </Space>

      <Card style={{ borderRadius: 12 }} styles={{ body: { padding: 32 } }}>
        <Title level={4} style={{ color: '#1a365d', marginBottom: 4 }}>
          <ProjectOutlined style={{ marginRight: 8 }} />
          创建参赛项目
        </Title>
        <Text type="secondary" style={{ display: 'block', marginBottom: 28 }}>
          填写项目信息并选择参赛类别
        </Text>

        <Form
          form={form}
          layout="vertical"
          onFinish={onFinish}
          size="large"
          requiredMark={false}
        >
          <Form.Item
            name="name"
            label="项目名称"
            rules={[{ required: true, message: '请输入项目名称' }]}
          >
            <Input placeholder="输入您的参赛项目名称" maxLength={100} />
          </Form.Item>

          <Form.Item label="赛事选择" required>
            <CompetitionSelector onChange={setSelection} />
          </Form.Item>

          <Form.Item style={{ marginTop: 12 }}>
            <Button
              type="primary"
              htmlType="submit"
              loading={loading}
              block
              disabled={!selection}
              style={{ height: 44, fontWeight: 500 }}
            >
              创建项目
            </Button>
          </Form.Item>
        </Form>
      </Card>
    </div>
  );
}
