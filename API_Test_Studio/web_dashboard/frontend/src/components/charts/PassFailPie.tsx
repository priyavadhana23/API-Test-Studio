import Plot from 'react-plotly.js';

interface Props { passed: number; failed: number; skipped: number; errors: number }

export default function PassFailPie({ passed, failed, skipped, errors }: Props) {
  const values = [passed, failed, skipped, errors].filter((_, i) =>
    [passed, failed, skipped, errors][i] > 0,
  );
  const labels = (['Passed', 'Failed', 'Skipped', 'Errors'] as const).filter(
    (_, i) => [passed, failed, skipped, errors][i] > 0,
  );
  return (
    <Plot
      data={[{
        type: 'pie',
        values,
        labels,
        hole: 0.45,
        marker: { colors: ['#34a853', '#ea4335', '#fbbc04', '#9e9e9e'] },
        textinfo: 'percent',
        hoverinfo: 'label+value+percent',
      }]}
      layout={{
        margin: { t: 10, b: 10, l: 10, r: 10 },
        showlegend: true,
        legend: { orientation: 'h', y: -0.15 },
        height: 260,
        paper_bgcolor: 'transparent',
        plot_bgcolor: 'transparent',
      }}
      config={{ displayModeBar: false, responsive: true }}
      style={{ width: '100%' }}
    />
  );
}
