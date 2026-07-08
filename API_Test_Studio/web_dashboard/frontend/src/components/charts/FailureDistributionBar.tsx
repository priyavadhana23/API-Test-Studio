import Plot from 'react-plotly.js';
import type { FailureEntry } from '../../types/api';

interface Props { distribution: FailureEntry[] }

export default function FailureDistributionBar({ distribution }: Props) {
  const sorted = [...distribution].sort((a, b) => b.count - a.count).slice(0, 10);
  return (
    <Plot
      data={[{
        type: 'bar',
        x: sorted.map(e => e.category),
        y: sorted.map(e => e.count),
        marker: { color: '#ea4335' },
        text: sorted.map(e => `${e.percentage.toFixed(1)}%`),
        textposition: 'outside',
        hovertemplate: '%{x}: %{y} failures<extra></extra>',
      }]}
      layout={{
        margin: { t: 10, b: 80, l: 50, r: 20 },
        xaxis: { tickangle: -30, automargin: true },
        yaxis: { title: 'Count' },
        height: 280,
        paper_bgcolor: 'transparent',
        plot_bgcolor: 'transparent',
      }}
      config={{ displayModeBar: false, responsive: true }}
      style={{ width: '100%' }}
    />
  );
}
