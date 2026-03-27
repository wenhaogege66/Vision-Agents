import { useEffect, useState, useCallback } from 'react';
import { Input, Button, Space, Popconfirm, Typography, Empty, Spin } from 'antd';
import {
  EditOutlined,
  DeleteOutlined,
  PlusOutlined,
  CheckOutlined,
  CloseOutlined,
} from '@ant-design/icons';
import { defenseApi } from '@/services/api';
import type { DefenseQuestion } from '@/types';
import { msg } from '@/utils/messageHolder';

const { Text } = Typography;

const MAX_LEN = 40;

interface Props {
  projectId: string;
  onQuestionsChange?: (count: number) => void;
}

export default function DefenseQuestionManager({ projectId, onQuestionsChange }: Props) {
  const [questions, setQuestions] = useState<DefenseQuestion[]>([]);
  const [loading, setLoading] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editValue, setEditValue] = useState('');
  const [adding, setAdding] = useState(false);
  const [newValue, setNewValue] = useState('');

  const notifyChange = useCallback(
    (list: DefenseQuestion[]) => { onQuestionsChange?.(list.length); },
    [onQuestionsChange],
  );

  const fetchQuestions = useCallback(async () => {
    setLoading(true);
    try {
      const data = await defenseApi.listQuestions(projectId);
      setQuestions(data);
      notifyChange(data);
    } catch { msg.error('加载问题列表失败'); }
    finally { setLoading(false); }
  }, [projectId, notifyChange]);

  useEffect(() => { fetchQuestions(); }, [fetchQuestions]);

  const validate = (value: string): string | null => {
    const trimmed = value.trim();
    if (!trimmed) return '问题内容不能为空';
    if ([...trimmed].length > MAX_LEN) return `问题不能超过${MAX_LEN}个字`;
    return null;
  };

  const handleAdd = async () => {
    const err = validate(newValue);
    if (err) { msg.warning(err); return; }
    try {
      const created = await defenseApi.createQuestion(projectId, newValue.trim());
      const next = [...questions, created];
      setQuestions(next);
      notifyChange(next);
      setNewValue(''); setAdding(false);
      msg.success('问题已添加');
    } catch { msg.error('添加问题失败'); }
  };

  const startEdit = (q: DefenseQuestion) => { setEditingId(q.id); setEditValue(q.content); };
  const cancelEdit = () => { setEditingId(null); setEditValue(''); };

  const handleSave = async () => {
    if (!editingId) return;
    const err = validate(editValue);
    if (err) { msg.warning(err); return; }
    try {
      const updated = await defenseApi.updateQuestion(projectId, editingId, editValue.trim());
      const next = questions.map((q) => (q.id === editingId ? updated : q));
      setQuestions(next); notifyChange(next); cancelEdit();
      msg.success('问题已更新');
    } catch { msg.error('更新问题失败'); }
  };

  const handleDelete = async (id: string) => {
    try {
      await defenseApi.deleteQuestion(projectId, id);
      const next = questions.filter((q) => q.id !== id);
      setQuestions(next); notifyChange(next);
      msg.success('问题已删除');
    } catch { msg.error('删除问题失败'); }
  };

  const remaining = (value: string) => MAX_LEN - [...value].length;

  return (
    <div>
      {loading ? (
        <div style={{ textAlign: 'center', padding: 24 }}><Spin /></div>
      ) : questions.length === 0 ? (
        <Empty description="暂无预定义问题" image={Empty.PRESENTED_IMAGE_SIMPLE} />
      ) : (
        <div>
          {questions.map((q, idx) => (
            <div
              key={q.id}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '10px 0',
                borderBottom: idx < questions.length - 1 ? '1px solid #f0f0f0' : undefined,
              }}
            >
              {editingId === q.id ? (
                <div style={{ flex: 1, marginRight: 8 }}>
                  <Input
                    value={editValue}
                    onChange={(e) => setEditValue(e.target.value)}
                    onPressEnter={handleSave}
                    maxLength={MAX_LEN + 10}
                    suffix={
                      <Text type={remaining(editValue) < 0 ? 'danger' : 'secondary'} style={{ fontSize: 12 }}>
                        {remaining(editValue)}
                      </Text>
                    }
                  />
                </div>
              ) : (
                <Text style={{ flex: 1 }}>{idx + 1}. {q.content}</Text>
              )}
              <Space size={4}>
                {editingId === q.id ? (
                  <>
                    <Button type="text" icon={<CheckOutlined />} onClick={handleSave} style={{ color: '#52c41a' }} />
                    <Button type="text" icon={<CloseOutlined />} onClick={cancelEdit} />
                  </>
                ) : (
                  <>
                    <Button type="text" icon={<EditOutlined />} onClick={() => startEdit(q)} />
                    <Popconfirm title="确定删除该问题？" onConfirm={() => handleDelete(q.id)} okText="删除" cancelText="取消">
                      <Button type="text" danger icon={<DeleteOutlined />} />
                    </Popconfirm>
                  </>
                )}
              </Space>
            </div>
          ))}
        </div>
      )}

      {adding ? (
        <Space.Compact style={{ width: '100%', marginTop: 8 }}>
          <Input
            autoFocus
            placeholder="请输入问题内容"
            value={newValue}
            onChange={(e) => setNewValue(e.target.value)}
            onPressEnter={handleAdd}
            maxLength={MAX_LEN + 10}
            suffix={
              <Text type={remaining(newValue) < 0 ? 'danger' : 'secondary'} style={{ fontSize: 12 }}>
                {remaining(newValue)}
              </Text>
            }
          />
          <Button type="primary" icon={<CheckOutlined />} onClick={handleAdd} />
          <Button icon={<CloseOutlined />} onClick={() => { setAdding(false); setNewValue(''); }} />
        </Space.Compact>
      ) : (
        <Button type="dashed" icon={<PlusOutlined />} onClick={() => setAdding(true)} style={{ width: '100%', marginTop: 8 }}>
          新增问题
        </Button>
      )}
    </div>
  );
}
