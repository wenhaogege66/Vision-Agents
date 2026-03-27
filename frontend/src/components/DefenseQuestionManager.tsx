import { useEffect, useState, useCallback } from 'react';
import { List, Input, Button, Space, Popconfirm, Typography, Empty } from 'antd';
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

  // Inline editing
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editValue, setEditValue] = useState('');

  // Adding new question
  const [adding, setAdding] = useState(false);
  const [newValue, setNewValue] = useState('');

  const notifyChange = useCallback(
    (list: DefenseQuestion[]) => {
      onQuestionsChange?.(list.length);
    },
    [onQuestionsChange],
  );

  const fetchQuestions = useCallback(async () => {
    setLoading(true);
    try {
      const data = await defenseApi.listQuestions(projectId);
      setQuestions(data);
      notifyChange(data);
    } catch {
      msg.error('加载问题列表失败');
    } finally {
      setLoading(false);
    }
  }, [projectId, notifyChange]);

  useEffect(() => {
    fetchQuestions();
  }, [fetchQuestions]);

  // ── Validation ──────────────────────────────────────────────

  const validate = (value: string): string | null => {
    const trimmed = value.trim();
    if (!trimmed) return '问题内容不能为空';
    if ([...trimmed].length > MAX_LEN) return `问题不能超过${MAX_LEN}个字`;
    return null;
  };

  // ── Add ─────────────────────────────────────────────────────

  const handleAdd = async () => {
    const err = validate(newValue);
    if (err) {
      msg.warning(err);
      return;
    }
    try {
      const created = await defenseApi.createQuestion(projectId, newValue.trim());
      const next = [...questions, created];
      setQuestions(next);
      notifyChange(next);
      setNewValue('');
      setAdding(false);
      msg.success('问题已添加');
    } catch {
      msg.error('添加问题失败');
    }
  };

  // ── Edit ────────────────────────────────────────────────────

  const startEdit = (q: DefenseQuestion) => {
    setEditingId(q.id);
    setEditValue(q.content);
  };

  const cancelEdit = () => {
    setEditingId(null);
    setEditValue('');
  };

  const handleSave = async () => {
    if (!editingId) return;
    const err = validate(editValue);
    if (err) {
      msg.warning(err);
      return;
    }
    try {
      const updated = await defenseApi.updateQuestion(projectId, editingId, editValue.trim());
      const next = questions.map((q) => (q.id === editingId ? updated : q));
      setQuestions(next);
      notifyChange(next);
      cancelEdit();
      msg.success('问题已更新');
    } catch {
      msg.error('更新问题失败');
    }
  };

  // ── Delete ──────────────────────────────────────────────────

  const handleDelete = async (id: string) => {
    try {
      await defenseApi.deleteQuestion(projectId, id);
      const next = questions.filter((q) => q.id !== id);
      setQuestions(next);
      notifyChange(next);
      msg.success('问题已删除');
    } catch {
      msg.error('删除问题失败');
    }
  };

  // ── Remaining chars helper ─────────────────────────────────

  const remaining = (value: string) => MAX_LEN - [...value].length;

  // ── Render ──────────────────────────────────────────────────

  return (
    <div>
      <List
        loading={loading}
        dataSource={questions}
        locale={{ emptyText: <Empty description="暂无预定义问题" /> }}
        renderItem={(q, idx) => (
          <List.Item
            actions={
              editingId === q.id
                ? [
                    <Button
                      key="save"
                      type="text"
                      icon={<CheckOutlined />}
                      onClick={handleSave}
                      style={{ color: '#52c41a' }}
                    />,
                    <Button
                      key="cancel"
                      type="text"
                      icon={<CloseOutlined />}
                      onClick={cancelEdit}
                    />,
                  ]
                : [
                    <Button
                      key="edit"
                      type="text"
                      icon={<EditOutlined />}
                      onClick={() => startEdit(q)}
                    />,
                    <Popconfirm
                      key="delete"
                      title="确定删除该问题？"
                      onConfirm={() => handleDelete(q.id)}
                      okText="删除"
                      cancelText="取消"
                    >
                      <Button type="text" danger icon={<DeleteOutlined />} />
                    </Popconfirm>,
                  ]
            }
          >
            {editingId === q.id ? (
              <div style={{ flex: 1, marginRight: 8 }}>
                <Input
                  value={editValue}
                  onChange={(e) => setEditValue(e.target.value)}
                  onPressEnter={handleSave}
                  maxLength={MAX_LEN + 10}
                  suffix={
                    <Text
                      type={remaining(editValue) < 0 ? 'danger' : 'secondary'}
                      style={{ fontSize: 12 }}
                    >
                      {remaining(editValue)}
                    </Text>
                  }
                />
              </div>
            ) : (
              <Text>
                {idx + 1}. {q.content}
              </Text>
            )}
          </List.Item>
        )}
      />

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
              <Text
                type={remaining(newValue) < 0 ? 'danger' : 'secondary'}
                style={{ fontSize: 12 }}
              >
                {remaining(newValue)}
              </Text>
            }
          />
          <Button type="primary" icon={<CheckOutlined />} onClick={handleAdd} />
          <Button
            icon={<CloseOutlined />}
            onClick={() => {
              setAdding(false);
              setNewValue('');
            }}
          />
        </Space.Compact>
      ) : (
        <Button
          type="dashed"
          icon={<PlusOutlined />}
          onClick={() => setAdding(true)}
          style={{ width: '100%', marginTop: 8 }}
        >
          新增问题
        </Button>
      )}
    </div>
  );
}
