import {
  Radar,
  RadarChart as RechartsRadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  ResponsiveContainer,
  Tooltip,
} from 'recharts';
import type { DimensionScore } from '@/types';

interface Props {
  dimensions: DimensionScore[];
}

export default function RadarChart({ dimensions }: Props) {
  const data = dimensions.map((d) => ({
    dimension: d.dimension,
    score: d.score,
    fullMark: d.max_score,
  }));

  return (
    <ResponsiveContainer width="100%" height={300}>
      <RechartsRadarChart data={data}>
        <PolarGrid />
        <PolarAngleAxis dataKey="dimension" />
        <PolarRadiusAxis angle={90} domain={[0, 'auto']} />
        <Tooltip
          formatter={(val: number, _name: string, entry: { payload: { fullMark: number } }) =>
            [`${val} / ${entry.payload.fullMark}`, '得分']
          }
        />
        <Radar
          name="评分"
          dataKey="score"
          stroke="#1677ff"
          fill="#1677ff"
          fillOpacity={0.3}
        />
      </RechartsRadarChart>
    </ResponsiveContainer>
  );
}
