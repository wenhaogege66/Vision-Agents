import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { Button, Spin, Typography, message } from 'antd';
import { DownloadOutlined } from '@ant-design/icons';
import TextReviewPanel from '@/components/TextReviewPanel';
import { reviewApi } from '@/services/api';
import type { ReviewResult } from '@/types';

const { Title } = Typography;

export default function ReviewDetail() {
  const { projectId, reviewId } = useParams<{ projectId: string; reviewId: string }>();
  const [result, setResult] = useState<ReviewResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);

  useEffect(() => {
    if (!projectId || !reviewId) return;
    reviewApi.get(projectId, reviewId).then((res) => {
      setResult(res.data);
      setLoading(false);
    }).catch(() => {
      message.error('获取评审详情失败');
      setLoading(false);
    });
  }, [projectId, reviewId]);

  const handleExport = async () => {
    if (!projectId || !reviewId) return;
    setExporting(true);
    try {
      const res = await reviewApi.exportPdf(projectId, reviewId);
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const a = document.createElement('a');
      a.href = url;
      a.download = `review_${reviewId}.pdf`;
      a.click();
      window.URL.revokeObjectURL(url);
    } catch {
      message.error('导出失败');
    } finally {
      setExporting(false);
    }
  };

  if (loading) return <Spin size="large" style={{ display: 'block', margin: '100px auto' }} />;
  if (!result) return <Title level={4}>评审记录不存在</Title>;

  return (
    <div style={{ padding: 24 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Title level={3} style={{ margin: 0 }}>评审详情</Title>
        <Button icon={<DownloadOutlined />} onClick={handleExport} loading={exporting}>
          导出PDF
        </Button>
      </div>
      <TextReviewPanel result={result} />
    </div>
  );
}
