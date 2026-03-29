import { Card, Typography } from 'antd';

const { Text } = Typography;

interface QuestionItem {
  content: string;
  sort_order: number;
}

interface Props {
  questions: QuestionItem[];
}

export default function QuestionPanel({ questions }: Props) {
  return (
    <Card title="评委问题" size="small">
      {questions.map((q, idx) => (
        <div
          key={idx}
          style={{
            padding: '8px 12px',
            marginBottom: idx < questions.length - 1 ? 8 : 0,
            background: '#fafafa',
            borderRadius: 6,
          }}
        >
          <Text strong style={{ marginRight: 8 }}>问题{idx + 1}</Text>
          <Text>{q.content}</Text>
        </div>
      ))}
    </Card>
  );
}
