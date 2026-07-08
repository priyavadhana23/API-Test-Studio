import { Chip } from '@mui/material';

interface Props { value: number | null | undefined; label?: string }

/** Green/amber/red chip based on a 0-100 pass-percentage or health score. */
export default function StatusChip({ value, label }: Props) {
  if (value === null || value === undefined) return <Chip label="—" size="small" />;
  const pct = value;
  const color = pct >= 80 ? 'success' : pct >= 50 ? 'warning' : 'error';
  return <Chip label={label ?? `${pct.toFixed(1)}%`} color={color} size="small" variant="outlined" />;
}
