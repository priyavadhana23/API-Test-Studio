import Plot from 'react-plotly.js';

interface Props { score: number; rating: string }

export default function HealthGauge({ score, rating }: Props) {
  const color = score >= 80 ? '#34a853' : score >= 60 ? '#fbbc04' : score >= 40 ? '#ff9800' : '#ea4335';
  return (
    <Plot
      data={[{
        type: 'indicator',
        mode: 'gauge+number+delta',
        value: score,
        title: { text: `<b>${rating}</b>`, font: { size: 14 } },
        gauge: {
          axis: { range: [0, 100], tickwidth: 1, tickcolor: '#666' },
          bar: { color },
          bgcolor: 'white',
          borderwidth: 2,
          bordercolor: '#e8eaed',
          steps: [
            { range: [0, 40],  color: '#fce8e6' },
            { range: [40, 60], color: '#fef3e2' },
            { range: [60, 80], color: '#e6f4ea' },
            { range: [80, 100], color: '#e6f4ea' },
          ],
          threshold: { line: { color: color, width: 4 }, thickness: 0.75, value: score },
        },
      }]}
      layout={{
        margin: { t: 40, b: 20, l: 30, r: 30 },
        height: 240,
        paper_bgcolor: 'transparent',
        font: { color: '#333' },
      }}
      config={{ displayModeBar: false, responsive: true }}
      style={{ width: '100%' }}
    />
  );
}
