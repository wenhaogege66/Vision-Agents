import { useState, useEffect, useCallback } from 'react';
import { useParams } from 'react-router-dom';
import BackButton from '@/components/BackButton';
import {
  Card,
  Upload,
  Button,
  Table,
  Tag,
  Space,
  Typography,
  Modal,
  Spin,
  Row,
  Col,
} from 'antd';
import { msg } from '@/utils/messageHolder';
import {
  UploadOutlined,
  DownloadOutlined,
  FileWordOutlined,
  FilePptOutlined,
  VideoCameraOutlined,
  HistoryOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
} from '@ant-design/icons';
import type { UploadProps } from 'antd';
import { materialApi } from '@/services/api';
import type { MaterialUploadResponse, MaterialType } from '@/types';

const { Title, Text } = Typography;

interface MaterialConfig {
  key: MaterialType;
  label: string;
  icon: React.ReactNode;
  accept: string;
  extensions: string[];
  maxSizeMB: number;
}

const MATERIAL_CONFIGS: MaterialConfig[] = [
  {
    key: 'bp',
    label: '文本BP（商业计划书）',
    icon: <FileWordOutlined style={{ fontSize: 24 }} />,
    accept: '.docx,.pdf',
    extensions: ['.docx', '.pdf'],
    maxSizeMB: 50,
  },
  {
    key: 'text_ppt',
    label: '文本PPT',
    icon: <FilePptOutlined style={{ fontSize: 24 }} />,
    accept: '.pptx,.pdf',
    extensions: ['.pptx', '.pdf'],
    maxSizeMB: 50,
  },
  {
    key: 'presentation_ppt',
    label: '路演PPT',
    icon: <FilePptOutlined style={{ fontSize: 24, color: '#fa8c16' }} />,
    accept: '.pptx,.pdf',
    extensions: ['.pptx', '.pdf'],
    maxSizeMB: 50,
  },
  {
    key: 'presentation_video',
    label: '路演视频',
    icon: <VideoCameraOutlined style={{ fontSize: 24 }} />,
    accept: '.mp4,.webm',
    extensions: ['.mp4', '.webm'],
    maxSizeMB: 500,
  },
];

export default function MaterialCenter() {
  const { projectId } = useParams<{ projectId: string }>();
  const [materials, setMaterials] = useState<Record<string, MaterialUploadResponse | null>>({});
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState<string | null>(null);
  const [versionModal, setVersionModal] = useState<{ open: boolean; type: MaterialType | null; versions: MaterialUploadResponse[] }>({
    open: false,
    type: null,
    versions: [],
  });
  const [downloading, setDownloading] = useState<string | null>(null);

  const fetchMaterials = useCallback(async () => {
    if (!projectId) return;
    try {
      const res = await materialApi.list(projectId);
      const map: Record<string, MaterialUploadResponse | null> = {};
      for (const cfg of MATERIAL_CONFIGS) {
        const latest = res.data.find(
          (m) => m.material_type === cfg.key,
        );
        map[cfg.key] = latest ?? null;
      }
      setMaterials(map);
    } catch {
      msg.error('获取材料列表失败');
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    fetchMaterials();
  }, [fetchMaterials]);

  const validateFile = (file: File, config: MaterialConfig): string | null => {
    const ext = '.' + file.name.split('.').pop()?.toLowerCase();
    if (!config.extensions.includes(ext)) {
      return `仅支持 ${config.extensions.join('、')} 格式`;
    }
    const sizeMB = file.size / (1024 * 1024);
    if (sizeMB > config.maxSizeMB) {
      return `文件大小不能超过 ${config.maxSizeMB}MB（当前 ${sizeMB.toFixed(1)}MB）`;
    }
    return null;
  };

  const handleUpload = async (file: File, config: MaterialConfig) => {
    const error = validateFile(file, config);
    if (error) {
      msg.error(error);
      return false;
    }
    if (!projectId) return false;
    setUploading(config.key);
    try {
      await materialApi.upload(projectId, config.key, file);
      msg.success(`${config.label} 上传成功`);
      await fetchMaterials();
    } catch {
      msg.error(`${config.label} 上传失败`);
    } finally {
      setUploading(null);
    }
    return false;
  };

  const showVersionHistory = async (type: MaterialType) => {
    if (!projectId) return;
    try {
      const res = await materialApi.versions(projectId, type);
      setVersionModal({ open: true, type, versions: res.data });
    } catch {
      msg.error('获取版本历史失败');
    }
  };

  const handleDownload = async (material: MaterialUploadResponse) => {
    if (!projectId) return;
    setDownloading(material.id);
    try {
      const { download_url } = await materialApi.download(projectId, material.id);
      window.open(download_url, '_blank');
    } catch (err: unknown) {
      const status = (err as { response?: { status?: number } })?.response?.status;
      if (status === 404) {
        msg.error('文件不可用');
      }
    } finally {
      setDownloading(null);
    }
  };

  if (loading) {
    return <Spin size="large" style={{ display: 'block', margin: '100px auto' }} />;
  }

  return (
    <div style={{ padding: 24 }}>
      <BackButton to={`/projects/${projectId}`} label="返回项目仪表盘" />
      <Title level={3}>材料中心</Title>
      <Text type="secondary" style={{ marginBottom: 24, display: 'block' }}>
        管理项目的四大核心材料。文本PPT和路演PPT为必需材料。
      </Text>

      <Row gutter={[16, 16]}>
        {MATERIAL_CONFIGS.map((config) => {
          const mat = materials[config.key];
          const uploadProps: UploadProps = {
            beforeUpload: (file) => handleUpload(file, config),
            showUploadList: false,
            accept: config.accept,
          };

          return (
            <Col xs={24} sm={12} key={config.key}>
              <Card
                title={
                  <Space style={{ width: '100%', flexWrap: 'nowrap' }}>
                    {config.icon}
                    <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', minWidth: 0 }}>{config.label}</span>
                    {mat ? (
                      <Tag icon={<CheckCircleOutlined />} color="success" style={{ flexShrink: 0 }}>已上传</Tag>
                    ) : (
                      <Tag icon={<CloseCircleOutlined />} color="default" style={{ flexShrink: 0 }}>未上传</Tag>
                    )}
                  </Space>
                }
                extra={
                  mat && (
                    <Button
                      size="small"
                      icon={<HistoryOutlined />}
                      onClick={() => showVersionHistory(config.key)}
                    >
                      版本历史
                    </Button>
                  )
                }
              >
                {mat && (
                  <div style={{ marginBottom: 12 }}>
                    <Text>文件名：{mat.file_name}</Text>
                    <br />
                    <Text type="secondary">
                      版本 {mat.version} · {new Date(mat.created_at).toLocaleString()}
                    </Text>
                  </div>
                )}
                <Upload {...uploadProps}>
                  <Button
                    icon={<UploadOutlined />}
                    loading={uploading === config.key}
                  >
                    {mat ? '更新材料' : '上传材料'}
                  </Button>
                </Upload>
                <Text type="secondary" style={{ display: 'block', marginTop: 8, fontSize: 12 }}>
                  支持 {config.extensions.join('、')} 格式，最大 {config.maxSizeMB}MB
                </Text>
              </Card>
            </Col>
          );
        })}
      </Row>

      <Modal
        title={`版本历史 - ${MATERIAL_CONFIGS.find((c) => c.key === versionModal.type)?.label ?? ''}`}
        open={versionModal.open}
        onCancel={() => setVersionModal({ open: false, type: null, versions: [] })}
        footer={null}
        width={600}
      >
        <Table
          dataSource={versionModal.versions}
          rowKey="id"
          pagination={false}
          columns={[
            { title: '版本', dataIndex: 'version', width: 80, render: (v: number) => `v${v}` },
            { title: '文件名', dataIndex: 'file_name', ellipsis: true },
            {
              title: '上传时间',
              dataIndex: 'created_at',
              width: 180,
              render: (t: string) => new Date(t).toLocaleString(),
            },
            {
              title: '操作',
              width: 100,
              render: (_: unknown, record: MaterialUploadResponse) => (
                <Button
                  type="link"
                  size="small"
                  icon={<DownloadOutlined />}
                  loading={downloading === record.id}
                  onClick={() => handleDownload(record)}
                >
                  下载
                </Button>
              ),
            },
          ]}
        />
      </Modal>
    </div>
  );
}
