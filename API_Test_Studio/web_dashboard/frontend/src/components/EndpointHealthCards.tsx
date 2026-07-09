/**
 * EndpointHealthCards
 * Modern card-per-endpoint view replacing the simple table.
 * Each card shows health badge, counts, avg RT, failure rate, and likely root cause.
 */
import { useState } from 'react';
import {
  Box, Grid, Typography, Chip, Paper, LinearProgress,
  Collapse, IconButton, Tooltip,
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import SpeedIcon from '@mui/icons-material/Speed';
import type { EndpointStats } from '../types/api';
import { passRateColor } from '../utils/colors';
import StatusChip from './StatusChip';

interface Props {
  stats: EndpointStats[];
}

function methodColor(method: string): string {
  switch (method.toUpperCase()) {
    case 'GET':    return '#1a73e8';
    case 'POST':   return '#34a853';
    case 'PUT':    return '#f57c00';
    case 'PATCH':  return '#ab47bc';
    case 'DELETE': return '#e53935';
    default:       return '#546e7a';
  }
}

function likelyRootCause(s: EndpointStats): string {
  if (s.total_executions === 0) return 'No tests executed';
  if (s.errors > s.failed)      return 'Connectivity or authentication failure';
  if (s.pass_rate === 0)        return 'Endpoint may not be implemented';
  if (s.pass_rate < 30)         return 'Schema mismatch or incorrect implementation';
  if (s.pass_rate < 60)         return 'Partial implementation — some test categories failing';
  if (s.pass_rate < 80)         return 'Minor validation failures — review negative test cases';
  return 'Expected behaviour — minimal issues';
}

function healthBadgeColor(passRate: number): 'success' | 'warning' | 'error' {
  if (passRate >= 80) return 'success';
  if (passRate >= 50) return 'warning';
  return 'error';
}

interface CardProps { stat: EndpointStats }

function EndpointCard({ stat }: CardProps) {
  const [expanded, setExpanded] = useState(false);
  const failRate    = stat.total_executions > 0
    ? ((stat.failed + stat.errors) / stat.total_executions * 100)
    : 0;
  const pColor      = passRateColor(stat.pass_rate);
  const mColor      = methodColor(stat.method);
  const rootCause   = likelyRootCause(stat);
  const badgeColor  = healthBadgeColor(stat.pass_rate);

  return (
    <Paper
      elevation={0}
      sx={{
        borderRadius: 2.5,
        border: '1px solid #e8eaed',
        borderTop: `3px solid ${pColor}`,
        overflow: 'hidden',
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      {/* Card header */}
      <Box sx={{ px: 2, pt: 2, pb: 1 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
          <Chip
            label={stat.method}
            size="small"
            sx={{ bgcolor: mColor, color: '#fff', fontWeight: 700, fontSize: '0.7rem', fontFamily: 'monospace' }}
          />
          <Typography
            variant="body2"
            fontWeight={600}
            sx={{ fontFamily: 'monospace', fontSize: '0.85rem', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
            title={stat.endpoint}
          >
            {stat.endpoint}
          </Typography>
          <StatusChip value={stat.pass_rate} />
        </Box>

        {/* Pass rate bar */}
        <LinearProgress
          variant="determinate"
          value={stat.pass_rate}
          sx={{
            height: 5, borderRadius: 3, mb: 1.5,
            bgcolor: '#f0f0f0',
            '& .MuiLinearProgress-bar': { bgcolor: pColor, borderRadius: 3 },
          }}
        />

        {/* Metric grid */}
        <Grid container spacing={1}>
          {[
            { label: 'Tests',    value: stat.total_executions, color: 'text.primary' },
            { label: 'Passed',   value: stat.passed,   color: '#2e7d32' },
            { label: 'Failures', value: stat.failed,   color: stat.failed > 0 ? '#e65100' : 'text.secondary' },
            { label: 'Errors',   value: stat.errors,   color: stat.errors > 0 ? '#c62828' : 'text.secondary' },
          ].map(({ label, value, color }) => (
            <Grid item xs={3} key={label}>
              <Box sx={{ textAlign: 'center', p: 0.75, bgcolor: '#f8f9fa', borderRadius: 1 }}>
                <Typography variant="caption" color="text.secondary" display="block" sx={{ fontSize: '0.65rem' }}>{label}</Typography>
                <Typography variant="body2" fontWeight={700} sx={{ color, fontSize: '0.9rem' }}>{value}</Typography>
              </Box>
            </Grid>
          ))}
        </Grid>
      </Box>

      {/* Footer */}
      <Box sx={{ px: 2, pb: 1.5, mt: 'auto' }}>
        {stat.avg_response_time_ms != null && (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mb: 0.75 }}>
            <SpeedIcon sx={{ fontSize: 14, color: 'text.disabled' }} />
            <Typography variant="caption" color="text.secondary">
              Avg {stat.avg_response_time_ms.toFixed(0)} ms
              {stat.p95_response_time_ms != null && ` · P95 ${stat.p95_response_time_ms.toFixed(0)} ms`}
            </Typography>
          </Box>
        )}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mb: 0.75 }}>
          <Chip
            label={`Failure Rate ${failRate.toFixed(0)}%`}
            size="small"
            color={badgeColor}
            variant="outlined"
            sx={{ fontSize: '0.68rem', height: 20 }}
          />
        </Box>
        <Typography variant="caption" sx={{ color: pColor, fontSize: '0.72rem', fontStyle: 'italic' }}>
          {rootCause}
        </Typography>

        {/* Expand toggle */}
        <Box sx={{ display: 'flex', justifyContent: 'flex-end', mt: 0.5 }}>
          <Tooltip title={expanded ? 'Collapse' : 'Show details'}>
            <IconButton size="small" onClick={() => setExpanded(!expanded)} sx={{ p: 0.25 }}>
              {expanded ? <ExpandLessIcon fontSize="small" /> : <ExpandMoreIcon fontSize="small" />}
            </IconButton>
          </Tooltip>
        </Box>
      </Box>

      {/* Expandable detail */}
      <Collapse in={expanded}>
        <Box sx={{ px: 2, pb: 2, pt: 0, borderTop: '1px solid #f0f0f0', bgcolor: '#fafafa' }}>
          <Typography variant="caption" color="text.secondary" fontWeight={700} display="block" sx={{ mt: 1, mb: 1 }}>
            ENDPOINT DETAILS
          </Typography>
          {[
            ['Min RT',      stat.min_response_time_ms != null ? `${stat.min_response_time_ms.toFixed(0)} ms` : '—'],
            ['Max RT',      stat.max_response_time_ms != null ? `${stat.max_response_time_ms.toFixed(0)} ms` : '—'],
            ['P95 RT',      stat.p95_response_time_ms != null ? `${stat.p95_response_time_ms.toFixed(0)} ms` : '—'],
            ['Pass Rate',   `${stat.pass_rate.toFixed(1)}%`],
            ['Likely Cause', rootCause],
          ].map(([label, val]) => (
            <Box key={String(label)} sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.25 }}>
              <Typography variant="caption" color="text.secondary">{label}</Typography>
              <Typography variant="caption" fontWeight={600}>{val}</Typography>
            </Box>
          ))}
        </Box>
      </Collapse>
    </Paper>
  );
}

export default function EndpointHealthCards({ stats }: Props) {
  // Sort: worst first
  const sorted = [...stats].sort((a, b) => a.pass_rate - b.pass_rate);

  return (
    <Grid container spacing={2}>
      {sorted.map((s) => (
        <Grid item xs={12} sm={6} lg={4} key={`${s.method}-${s.endpoint}`}>
          <EndpointCard stat={s} />
        </Grid>
      ))}
    </Grid>
  );
}
