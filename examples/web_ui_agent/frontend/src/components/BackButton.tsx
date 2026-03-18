import { useNavigate } from 'react-router-dom';
import { Button } from 'antd';
import { ArrowLeftOutlined } from '@ant-design/icons';

interface BackButtonProps {
  to: string;
  label: string;
}

export default function BackButton({ to, label }: BackButtonProps) {
  const navigate = useNavigate();

  return (
    <Button
      type="text"
      icon={<ArrowLeftOutlined />}
      onClick={() => navigate(to)}
      style={{ marginBottom: 16 }}
    >
      {label}
    </Button>
  );
}
