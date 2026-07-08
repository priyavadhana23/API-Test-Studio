import Plot from 'react-plotly.js';
import type { TrendPoint } from '../../types/api';

interface Props { points: TrendPoint[]; movingAvg: number[] }

export default function ResponseTimeTrend({ points, movingAvg }: Props) {
  const labels = points.map(p => p.label);
  const values = points.map(p => p.value);
  return (
    <Plot
      data={[
        {
          type: 'scatter',
          mode: 'lines+markers',
          name: 'Value',
          x: labels,
          y: values,
          line: { color: '#1a73e8', width: 2 },
          marker: { size: 6 },
        },
        movingAvg.length > 0
          ? {
              type: 'scatter',
              mode: 'lines',
              name: 'Moving Avg',
              x: labels.slice(-movingAvg.length),
              y: movingAvg,
              line: { color: '#34a853', width: 2, dash: 'dot' },
            }
          : null,
      ].filter(Boolean) as Plotly.Data[]}
      layout={{
        margin: { t: 10, b: 40, l: 55, r: 20 },
        xaxis: { automargin: true },
        yaxis: { title: 'Value' },
        legend: { orientation: 'h', y: -0.25 },
        height: 260,
        paper_bgcolor: 'transparent',
        plot_bgcolor: 'transparent',
      }}
      config={{ displayModeBar: false, responsive: true }}
      style={{ width: '100%' }}
    />
  );
}
