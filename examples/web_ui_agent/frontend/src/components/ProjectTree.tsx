import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Tree, Spin } from 'antd';
import type { DataNode } from 'antd/es/tree';
import { projectApi, tagApi } from '@/services/api';
import { useLabelResolver } from '@/hooks/useLabelResolver';
import type { ProjectResponse, TagInfo } from '@/types';

/**
 * Build a hierarchical tree: competition → track → group → project.
 * Empty intermediate nodes (no descendant projects) are omitted.
 */
export function buildProjectTree(
  projects: ProjectResponse[],
  resolve: (type: 'competition' | 'track' | 'group', id: string) => string,
  tagMap: Record<string, TagInfo[]> = {},
): DataNode[] {
  // Group: competition → track → group → projects[]
  const compMap = new Map<string, Map<string, Map<string, ProjectResponse[]>>>();

  for (const p of projects) {
    if (!compMap.has(p.competition)) compMap.set(p.competition, new Map());
    const trackMap = compMap.get(p.competition)!;
    if (!trackMap.has(p.track)) trackMap.set(p.track, new Map());
    const groupMap = trackMap.get(p.track)!;
    if (!groupMap.has(p.group)) groupMap.set(p.group, []);
    groupMap.get(p.group)!.push(p);
  }

  const tree: DataNode[] = [];

  for (const [comp, trackMap] of compMap) {
    const compChildren: DataNode[] = [];

    for (const [track, groupMap] of trackMap) {
      const trackChildren: DataNode[] = [];

      for (const [group, groupProjects] of groupMap) {
        if (groupProjects.length === 0) continue;

        const projectNodes: DataNode[] = groupProjects.map((p) => {
          const tags = tagMap[p.id] ?? [];
          return {
            key: `project-${p.id}`,
            title: (
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                {p.name}
                {tags.map((t) => (
                  <span
                    key={t.id}
                    style={{
                      width: 8,
                      height: 8,
                      borderRadius: '50%',
                      background: t.color,
                      display: 'inline-block',
                    }}
                  />
                ))}
              </span>
            ),
            isLeaf: true,
          };
        });

        trackChildren.push({
          key: `group-${comp}-${track}-${group}`,
          title: resolve('group', group),
          children: projectNodes,
        });
      }

      if (trackChildren.length === 0) continue;

      compChildren.push({
        key: `track-${comp}-${track}`,
        title: resolve('track', track),
        children: trackChildren,
      });
    }

    if (compChildren.length === 0) continue;

    tree.push({
      key: `comp-${comp}`,
      title: resolve('competition', comp),
      children: compChildren,
    });
  }

  return tree;
}

export default function ProjectTree() {
  const [projects, setProjects] = useState<ProjectResponse[]>([]);
  const [tagMap, setTagMap] = useState<Record<string, TagInfo[]>>({});
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();
  const { resolve } = useLabelResolver();

  useEffect(() => {
    let cancelled = false;
    projectApi
      .list()
      .then(async (res) => {
        if (cancelled) return;
        const projectList = res.data;
        setProjects(projectList);

        // Fetch tags for each project in parallel
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
      .catch(() => {
        // silently fail — tree simply stays empty
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, []);

  const treeData = useMemo(
    () => buildProjectTree(projects, resolve, tagMap),
    [projects, resolve, tagMap],
  );

  if (loading) {
    return <Spin size="small" style={{ display: 'block', padding: '16px 0', textAlign: 'center' }} />;
  }

  if (treeData.length === 0) return null;

  return (
    <Tree
      treeData={treeData}
      defaultExpandAll={false}
      blockNode
      onSelect={(_, info) => {
        const nodeKey = String(info.node.key);
        if (nodeKey.startsWith('project-')) {
          const projectId = nodeKey.replace('project-', '');
          navigate(`/projects/${projectId}`);
        }
      }}
      style={{ padding: '8px 0' }}
    />
  );
}
