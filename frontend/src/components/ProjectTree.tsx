import { useEffect, useMemo, useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { Spin, Typography, Tooltip, Empty, theme } from 'antd';
import { FolderOutlined, RightOutlined } from '@ant-design/icons';
import { projectApi, tagApi } from '@/services/api';
import { useLabelResolver } from '@/hooks/useLabelResolver';
import type { ProjectResponse, TagInfo } from '@/types';

const { Text } = Typography;

/** 从完整赛事名中提取简短名称，去掉括号内容和"中国"等前缀 */
function shortenName(name: string): string {
  // 去掉括号及其内容
  let short = name.replace(/[（(][^）)]*[）)]/g, '').trim();
  // 去掉常见冗长前缀
  short = short.replace(/^中国国际/, '').replace(/^中国/, '').replace(/^全国/, '');
  // 如果处理后为空，返回原名前4个字
  if (!short) return name.slice(0, 4);
  return short;
}

export default function ProjectTree() {
  const [projects, setProjects] = useState<ProjectResponse[]>([]);
  const [tagMap, setTagMap] = useState<Record<string, TagInfo[]>>({});
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();
  const location = useLocation();
  const { resolve } = useLabelResolver();
  const { token } = theme.useToken();

  useEffect(() => {
    let cancelled = false;
    projectApi
      .list()
      .then(async (res) => {
        if (cancelled) return;
        const projectList = res.data;
        setProjects(projectList);

        const entries = await Promise.all(
          projectList.map(async (p) => {
            try {
              const tags = await tagApi.getProjectTags(p.id);
              return [p.id, tags] as const;
            } catch {
              return [p.id, []] as const;
            }
          }),
        );
        if (!cancelled) {
          setTagMap(Object.fromEntries(entries));
        }
      })
      .catch(() => {})
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, []);

  // 当前选中的项目 ID
  const activeProjectId = useMemo(() => {
    const match = location.pathname.match(/\/projects\/([^/]+)/);
    return match ? match[1] : null;
  }, [location.pathname]);

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', padding: '20px 0' }}>
        <Spin size="small" />
      </div>
    );
  }

  if (projects.length === 0) {
    return (
      <div style={{ padding: '16px 12px' }}>
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description={<Text type="secondary" style={{ fontSize: 12 }}>暂无项目</Text>}
          imageStyle={{ height: 40 }}
        />
      </div>
    );
  }

  return (
    <div style={{ padding: '4px 0' }}>
      {/* 分区标题 */}
      <div style={{
        padding: '8px 16px 6px',
        display: 'flex',
        alignItems: 'center',
        gap: 6,
      }}>
        <FolderOutlined style={{ fontSize: 12, color: token.colorTextTertiary }} />
        <Text type="secondary" style={{ fontSize: 11, fontWeight: 600, letterSpacing: 0.5, textTransform: 'uppercase' }}>
          项目列表
        </Text>
      </div>

      {/* 项目列表 */}
      {projects.map((p) => {
        const tags = tagMap[p.id] ?? [];
        const isActive = p.id === activeProjectId;
        const compName = shortenName(resolve('competition', p.competition));
        const trackName = resolve('track', p.track);
        const groupName = resolve('group', p.group);
        const subtitle = `${compName} · ${trackName} · ${groupName}`;

        return (
          <Tooltip
            key={p.id}
            title={`${resolve('competition', p.competition)} / ${trackName} / ${groupName}`}
            placement="right"
            mouseEnterDelay={0.5}
          >
            <div
              onClick={() => navigate(`/projects/${p.id}`)}
              style={{
                padding: '8px 16px',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                borderRadius: 6,
                margin: '1px 8px',
                transition: 'all 0.2s',
                background: isActive ? token.colorPrimaryBg : 'transparent',
                borderLeft: isActive ? `3px solid ${token.colorPrimary}` : '3px solid transparent',
              }}
              onMouseEnter={(e) => {
                if (!isActive) e.currentTarget.style.background = token.colorFillTertiary;
              }}
              onMouseLeave={(e) => {
                if (!isActive) e.currentTarget.style.background = 'transparent';
              }}
            >
              {/* 项目信息 */}
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 4,
                }}>
                  <span style={{
                    fontSize: 13,
                    fontWeight: isActive ? 600 : 400,
                    color: isActive ? token.colorPrimary : token.colorText,
                    whiteSpace: 'nowrap',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    lineHeight: '20px',
                  }}>
                    {p.name}
                  </span>
                  {tags.map((t) => (
                    <span
                      key={t.id}
                      style={{
                        width: 6,
                        height: 6,
                        borderRadius: '50%',
                        background: t.color,
                        display: 'inline-block',
                        flexShrink: 0,
                      }}
                    />
                  ))}
                </div>
                <div style={{
                  fontSize: 11,
                  color: token.colorTextQuaternary,
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  lineHeight: '16px',
                }}>
                  {subtitle}
                </div>
              </div>

              {/* 箭头指示 */}
              <RightOutlined style={{
                fontSize: 10,
                color: isActive ? token.colorPrimary : token.colorTextQuaternary,
                flexShrink: 0,
                opacity: isActive ? 1 : 0,
                transition: 'opacity 0.2s',
              }} />
            </div>
          </Tooltip>
        );
      })}
    </div>
  );
}
