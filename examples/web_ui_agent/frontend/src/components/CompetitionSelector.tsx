import { useState, useEffect, useCallback } from 'react';
import { Select, Space, Tag, Typography } from 'antd';
import {
  TrophyOutlined,
  BranchesOutlined,
  TeamOutlined,
  CheckCircleFilled,
} from '@ant-design/icons';
import { competitionApi } from '@/services/api';
import type { CompetitionInfo, TrackInfo, GroupInfo } from '@/types';

const { Text } = Typography;

export interface CompetitionSelection {
  competition: string;
  track: string;
  group: string;
}

interface CompetitionSelectorProps {
  value?: Partial<CompetitionSelection>;
  onChange?: (value: CompetitionSelection) => void;
  /** Vertical or horizontal layout */
  layout?: 'vertical' | 'horizontal';
}

export default function CompetitionSelector({
  value,
  onChange,
  layout = 'vertical',
}: CompetitionSelectorProps) {
  const [competitions, setCompetitions] = useState<CompetitionInfo[]>([]);
  const [tracks, setTracks] = useState<TrackInfo[]>([]);
  const [groups, setGroups] = useState<GroupInfo[]>([]);

  const [selectedCompetition, setSelectedCompetition] = useState<string | undefined>(
    value?.competition,
  );
  const [selectedTrack, setSelectedTrack] = useState<string | undefined>(value?.track);
  const [selectedGroup, setSelectedGroup] = useState<string | undefined>(value?.group);

  const [loadingCompetitions, setLoadingCompetitions] = useState(false);
  const [loadingTracks, setLoadingTracks] = useState(false);
  const [loadingGroups, setLoadingGroups] = useState(false);

  // Fetch competitions on mount
  useEffect(() => {
    setLoadingCompetitions(true);
    competitionApi
      .list()
      .then((res) => setCompetitions(res.data))
      .catch(() => setCompetitions([]))
      .finally(() => setLoadingCompetitions(false));
  }, []);

  // Fetch tracks when competition changes
  useEffect(() => {
    if (!selectedCompetition) {
      setTracks([]);
      return;
    }
    setLoadingTracks(true);
    competitionApi
      .tracks(selectedCompetition)
      .then((res) => setTracks(res.data))
      .catch(() => setTracks([]))
      .finally(() => setLoadingTracks(false));
  }, [selectedCompetition]);

  // Fetch groups when track changes
  useEffect(() => {
    if (!selectedCompetition || !selectedTrack) {
      setGroups([]);
      return;
    }
    setLoadingGroups(true);
    competitionApi
      .groups(selectedCompetition, selectedTrack)
      .then((res) => setGroups(res.data))
      .catch(() => setGroups([]))
      .finally(() => setLoadingGroups(false));
  }, [selectedCompetition, selectedTrack]);

  const handleCompetitionChange = useCallback(
    (val: string) => {
      setSelectedCompetition(val);
      setSelectedTrack(undefined);
      setSelectedGroup(undefined);
      setTracks([]);
      setGroups([]);
    },
    [],
  );

  const handleTrackChange = useCallback(
    (val: string) => {
      setSelectedTrack(val);
      setSelectedGroup(undefined);
      setGroups([]);
    },
    [],
  );

  const handleGroupChange = useCallback(
    (val: string) => {
      setSelectedGroup(val);
      if (selectedCompetition && selectedTrack) {
        onChange?.({ competition: selectedCompetition, track: selectedTrack, group: val });
      }
    },
    [selectedCompetition, selectedTrack, onChange],
  );

  const isHorizontal = layout === 'horizontal';

  const selectStyle: React.CSSProperties = {
    width: isHorizontal ? 200 : '100%',
  };

  return (
    <Space
      orientation={isHorizontal ? 'horizontal' : 'vertical'}
      size={isHorizontal ? 16 : 12}
      style={{ width: isHorizontal ? undefined : '100%' }}
    >
      {/* Competition type */}
      <div style={{ width: isHorizontal ? 200 : '100%' }}>
        {!isHorizontal && (
          <Text
            strong
            style={{ display: 'block', marginBottom: 6, fontSize: 13, color: '#1a365d' }}
          >
            <TrophyOutlined style={{ marginRight: 6 }} />
            赛事类型
          </Text>
        )}
        <Select
          placeholder="选择赛事类型"
          value={selectedCompetition}
          onChange={handleCompetitionChange}
          loading={loadingCompetitions}
          style={selectStyle}
          suffixIcon={<TrophyOutlined style={{ color: '#1a365d' }} />}
          options={competitions.map((c) => ({ label: c.name, value: c.id }))}
          allowClear
          onClear={() => handleCompetitionChange('')}
        />
      </div>

      {/* Track */}
      <div style={{ width: isHorizontal ? 200 : '100%' }}>
        {!isHorizontal && (
          <Text
            strong
            style={{ display: 'block', marginBottom: 6, fontSize: 13, color: '#1a365d' }}
          >
            <BranchesOutlined style={{ marginRight: 6 }} />
            赛道
          </Text>
        )}
        <Select
          placeholder="选择赛道"
          value={selectedTrack}
          onChange={handleTrackChange}
          loading={loadingTracks}
          disabled={!selectedCompetition}
          style={selectStyle}
          suffixIcon={<BranchesOutlined style={{ color: '#2a4a7f' }} />}
          options={tracks.map((t) => ({ label: t.name, value: t.id }))}
          allowClear
          onClear={() => handleTrackChange('')}
        />
      </div>

      {/* Group */}
      <div style={{ width: isHorizontal ? 220 : '100%' }}>
        {!isHorizontal && (
          <Text
            strong
            style={{ display: 'block', marginBottom: 6, fontSize: 13, color: '#1a365d' }}
          >
            <TeamOutlined style={{ marginRight: 6 }} />
            组别
          </Text>
        )}
        <Select
          placeholder="选择组别"
          value={selectedGroup}
          onChange={handleGroupChange}
          loading={loadingGroups}
          disabled={!selectedTrack}
          style={selectStyle}
          suffixIcon={<TeamOutlined style={{ color: '#2a4a7f' }} />}
          options={groups.map((g) => ({
            label: (
              <span>
                {g.name}
                {g.has_rules && (
                  <Tag
                    color="success"
                    icon={<CheckCircleFilled />}
                    style={{ marginLeft: 8, fontSize: 11 }}
                  >
                    已配置规则
                  </Tag>
                )}
              </span>
            ),
            value: g.id,
          }))}
          allowClear
          onClear={() => handleGroupChange('')}
        />
      </div>
    </Space>
  );
}
