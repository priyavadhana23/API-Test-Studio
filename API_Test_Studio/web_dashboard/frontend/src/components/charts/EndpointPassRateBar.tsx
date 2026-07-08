import Plot from 'react-plotly.js';
import type { EndpointStats } from '../../types/api';

interface Props { stats: EndpointStats[] }

export default function EndpointPassRateBar({ stats }: Props) {
  const sorted = [...stats].sort((a, b) => a.pass_rate - b.pass_rate);
  const labels = sorted.map(s => `${s.method} ${s.endpoint}`);
  const values = sorted.map(s => s.pass_rate);
  const colors = values.map(v => v >= 80 ? '#34a853' : v >= 50 ? '#fbbc04' : '#ea4335');

  return (
    <Plot
      data={[{
        type: 'bar',
        orientation: 'h',
        x: values,
        y: labels,
        marker: { color: colors },
        text: values.map(v => `${v.toFixed(1)}%`),
        textposition: 'outside',
        hovertemplate: '%{y}: %{x:.1f}%<extra></extra>',
      }]}
      layout={{
        margin: { t: 10, b: 40, l: 200, r: 60 },
        xaxis: { range: [0, 110], title: 'Pass Rate (%)', ticksuffix: '%' },
        yaxis: { automargin: true },
        height: Math.max(240, sorted.length * 32 + 60),
        paper_bgcolor: 'transparent',
        plot_bgcolor: 'transparent',
      }}
      config={{ displayModeBar: false, responsive: true }}
      style={{ width: '100%' }}
    />
  );
}
