import { Radio, Tag, Space } from 'antd';
import { QuestionCircleOutlined, BulbOutlined } from '@ant-design/icons';

interface Props {
  value: string;
  onChange: (mode: string) => void;
  disabled?: boolean;
}

export default function ModeSwitch({ value, onChange, disabled }: Props) {
  return (
    <Space orientation="vertical" align="center">
      <Tag color={value === 'question' ? 'blue' : 'green'} style={{ fontSize: 14, padding: '4px 12px' }}>
        当前模式：{value === 'question' ? '提问模式' : '建议模式'}
      </Tag>
      <Radio.Group
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
        buttonStyle="solid"
      >
        <Radio.Button value="question">
          <QuestionCircleOutlined /> 提问模式
        </Radio.Button>
        <Radio.Button value="suggestion">
          <BulbOutlined /> 建议模式
        </Radio.Button>
      </Radio.Group>
    </Space>
  );
}
