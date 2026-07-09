// Centralised colour system for the enterprise QA dashboard.
// All status colours live here so every component stays consistent.

export const HEALTH_COLORS = {
  excellent:       '#1b5e20',   // dark green
  good:            '#2e7d32',   // green
  needsAttention:  '#e65100',   // orange
  critical:        '#b71c1c',   // dark red
  unknown:         '#546e7a',
} as const;

export const HEALTH_BG = {
  excellent:       '#f0fdf4',
  good:            '#e8f5e9',
  needsAttention:  '#fff3e0',
  critical:        '#fce4e4',
  unknown:         '#f5f5f5',
} as const;

export const STATUS_COLORS = {
  passed:   '#2e7d32',
  failed:   '#e65100',   // amber/orange — validation failures
  errors:   '#c62828',   // red          — execution errors
  skipped:  '#757575',
  warning:  '#f57c00',
} as const;

export const PRIORITY_COLORS = {
  critical: '#b71c1c',
  high:     '#e65100',
  medium:   '#f57c00',
  low:      '#1a73e8',
} as const;

export type HealthRating = 'excellent' | 'good' | 'needs attention' | 'needsattention' | 'critical';

export function healthColorByRating(rating: string): string {
  const r = rating.toLowerCase().replace(' ', '') as string;
  if (r === 'excellent')                       return HEALTH_COLORS.excellent;
  if (r === 'good')                            return HEALTH_COLORS.good;
  if (r === 'needsattention' || r === 'needs attention') return HEALTH_COLORS.needsAttention;
  if (r === 'critical')                        return HEALTH_COLORS.critical;
  return HEALTH_COLORS.unknown;
}

export function healthBgByRating(rating: string): string {
  const r = rating.toLowerCase().replace(' ', '') as string;
  if (r === 'excellent')                       return HEALTH_BG.excellent;
  if (r === 'good')                            return HEALTH_BG.good;
  if (r === 'needsattention' || r === 'needs attention') return HEALTH_BG.needsAttention;
  if (r === 'critical')                        return HEALTH_BG.critical;
  return HEALTH_BG.unknown;
}

export function passRateColor(pct: number): string {
  if (pct >= 80) return HEALTH_COLORS.excellent;
  if (pct >= 60) return HEALTH_COLORS.good;
  if (pct >= 40) return HEALTH_COLORS.needsAttention;
  return HEALTH_COLORS.critical;
}

export function priorityColor(priority: string): string {
  switch (priority.toLowerCase()) {
    case 'critical': return PRIORITY_COLORS.critical;
    case 'high':     return PRIORITY_COLORS.high;
    case 'medium':   return PRIORITY_COLORS.medium;
    default:         return PRIORITY_COLORS.low;
  }
}
