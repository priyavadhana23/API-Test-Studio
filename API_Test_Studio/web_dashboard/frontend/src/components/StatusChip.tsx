import { Chip } from '@mui/material';

interface Props {
  value: number | null | undefined;
  label?: string;
  /** Override automatic colour selection */
  forceColor?: 'success' | 'warning' | 'error' | 'default';
}

/**
 * Colour-coded chip.
 * ≥ 80 %  → green (success)
 * 50–79 % → amber (warning)
 * < 50 %  → red   (error)
 */
export default function StatusChip({ value, label, forceColor }: Props) {
  if (value === null || value === undefined) return <Chip label="—" size="small" />;
  const pct = value;
  const color: 'success' | 'warning' | 'error' =
    forceColor === 'success' ? 'success' :
    forceColor === 'warning' ? 'warning' :
    forceColor === 'error'   ? 'error'   :
    pct >= 80                ? 'success' :
    pct >= 50                ? 'warning' : 'error';
  return (
    <Chip
      label={label ?? `${pct.toFixed(1)}%`}
      color={color}
      size="small"
      variant="outlined"
      sx={{ fontWeight: 600 }}
    />
  );
}
