import { useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box, Grid, Typography, Paper, Table, TableBody, TableCell,
  TableContainer, TableHead, TableRow, Tooltip, Chip, Button, Divider,
} from '@mui/material';
import AssessmentIcon     from '@mui/icons-material/Assessment';
import SpeedIcon          from '@mui/icons-material/Speed';
import CheckCircleIcon    from '@mui/icons-material/CheckCircle';
import FavoriteIcon       from '@mui/icons-material/Favorite';
import CloudUploadIcon    from '@mui/icons-material/CloudUpload';
import BarChartIcon       from '@mui/icons-material/BarChart';
import PlaylistPlayIcon   from '@mui/icons-material/PlaylistPlay';
import TrendingUpIcon     from '@mui/icons-material/TrendingUp';
import TrendingDownIcon   from '@mui/icons-material/TrendingDown';
import StatCard           from '../components/StatCard';
import StatusChip         from '../components/StatusChip';
import PageState          from '../components/PageState';
import { useAsync }       from '../hooks/useAsync';
import runsService        from '../services/runsService';
import type { RunSummary } from '../types/api';
import { healthColorByRating, healthBgByRating } from '../utils/colors';

function fmt(ts: string | null) {
  if (!ts) return '—';
  return new Date(ts).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' });
}
function shortId(id: string) { return id.slice(0, 12) + '…'; }

function healthRatingColor(rating: string | null | undefined): 'success' | 'warning' | 'error' | 'default' {
  if (!rating) return 'default';
  const r = rating.toLowerCase();
  if (r === 'excellent' || r === 'good')      return 'success';
  if (r.includes('attention'))                 return 'warning';
  if (r === 'critical')                        return 'error';
  return 'default';
}

export default function DashboardPage() {
  const navigate = useNavigate();
  const { data, loading, error, refetch } = useAsync(
    () => runsService.listRuns({ page: 1, page_size: 50 }),
    [],
  );

  const stats = useMemo(() => {
    if (!data?.runs.length) return null;
    const runs   = data.runs;
    const total  = data.total;
    const latest = runs[0];
    const prev   = runs[1];
    const avgPass = runs.reduce((s, r) => s + r.pass_percentage, 0) / runs.length;
    const rtRuns  = runs.filter(r => r.avg_response_time_ms != null);
    const avgRt   = rtRuns.length
      ? rtRuns.reduce((s, r) => s + r.avg_response_time_ms!, 0) / rtRuns.length
      : null;
    const hsRuns  = runs.filter(r => r.health_score != null);
    const avgHs   = hsRuns.length
      ? hsRuns.reduce((s, r) => s + r.health_score!, 0) / hsRuns.length
      : null;
    const trend = prev
      ? (latest.pass_percentage - prev.pass_percentage)
      : null;
    return { total, avgPass, avgRt, avgHs, latest, trend };
  }, [data]);

  if (loading || error || !data?.runs.length) {
    return (
      <>
        <Typography variant="h5" gutterBottom>Dashboard</Typography>
        <PageState
          loading={loading}
          loadingMessage="Loading execution history…"
          error={error}
          empty={!loading && !error}
          emptyMessage="No API executions found. Upload an OpenAPI specification to begin automated testing."
          onRetry={refetch}
        />
      </>
    );
  }

  const recent = data.runs.slice(0, 10);

  return (
    <Box>
      <Box sx={{ display: 'flex', alignItems: 'baseline', gap: 1.5, mb: 3 }}>
        <Typography variant="h5" fontWeight={700}>Dashboard</Typography>
        <Typography variant="caption" color="text.secondary">
          Last updated: {fmt(data.runs[0]?.execution_timestamp ?? null)}
        </Typography>
      </Box>

      {/* ── Top KPI cards ─────────────────────────────────────────── */}
      <Grid container spacing={2.5} sx={{ mb: 3 }}>
        <Grid item xs={12} sm={6} md={3}>
          <StatCard
            title="Total Runs"
            value={stats?.total}
            icon={<AssessmentIcon />}
            color="#1a73e8"
            tooltip="Total number of API test execution runs stored in history."
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <StatCard
            title="Latest Pass Rate"
            value={stats?.latest ? `${stats.latest.pass_percentage.toFixed(1)}%` : null}
            subtitle={
              stats?.trend != null
                ? (stats.trend >= 0 ? `▲ +${stats.trend.toFixed(1)}% vs previous` : `▼ ${stats.trend.toFixed(1)}% vs previous`)
                : undefined
            }
            icon={<CheckCircleIcon />}
            color={stats?.latest ? (stats.latest.pass_percentage >= 80 ? '#2e7d32' : stats.latest.pass_percentage >= 50 ? '#e65100' : '#c62828') : '#2e7d32'}
            tooltip="Pass rate of the most recent execution run."
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <StatCard
            title="Overall Health"
            value={stats?.latest?.health_rating ?? (stats?.avgHs != null ? `${stats.avgHs.toFixed(0)} / 100` : '—')}
            subtitle={stats?.latest?.health_score != null ? `Score: ${stats.latest.health_score.toFixed(0)}` : undefined}
            icon={<FavoriteIcon />}
            color={stats?.latest?.health_rating ? healthColorByRating(stats.latest.health_rating) : '#c62828'}
            tooltip="Health rating of the most recent run, derived from pass rate, response time, stability, and availability."
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <StatCard
            title="Avg Response Time"
            value={stats?.avgRt != null ? `${stats.avgRt.toFixed(0)} ms` : '—'}
            icon={<SpeedIcon />}
            color="#e65100"
            tooltip="Average HTTP response time across all executed requests in recent runs."
          />
        </Grid>
      </Grid>

      {/* ── Quick Actions ─────────────────────────────────────────── */}
      <Box sx={{ mb: 3 }}>
        <Typography variant="subtitle2" color="text.secondary" fontWeight={600} sx={{ mb: 1.5 }}>
          QUICK ACTIONS
        </Typography>
        <Box sx={{ display: 'flex', gap: 1.5, flexWrap: 'wrap' }}>
          {[
            { label: 'Upload Specification', icon: <CloudUploadIcon fontSize="small" />, path: '/upload',    variant: 'contained' as const },
            { label: 'View All Runs',         icon: <PlaylistPlayIcon fontSize="small" />, path: '/runs',      variant: 'outlined'  as const },
            { label: 'Analytics',             icon: <BarChartIcon fontSize="small" />,     path: '/analytics', variant: 'outlined'  as const },
          ].map(({ label, icon, path, variant }) => (
            <Button
              key={label}
              variant={variant}
              startIcon={icon}
              size="small"
              onClick={() => navigate(path)}
              sx={{ borderRadius: 2 }}
            >
              {label}
            </Button>
          ))}
        </Box>
      </Box>

      <Divider sx={{ mb: 3 }} />

      {/* ── Recent Runs table ─────────────────────────────────────── */}
      <Box sx={{ display: 'flex', alignItems: 'baseline', gap: 1, mb: 1.5 }}>
        <Typography variant="subtitle1" fontWeight={700}>Recent Runs</Typography>
        <Typography variant="caption" color="text.secondary">Click a row to view full results</Typography>
      </Box>

      <TableContainer component={Paper} sx={{ borderRadius: 2 }}>
        <Table size="small">
          <TableHead>
            <TableRow sx={{ '& th': { fontWeight: 700, bgcolor: '#f8f9fa', fontSize: '0.75rem' } }}>
              <TableCell>Run ID</TableCell>
              <TableCell>Execution Date</TableCell>
              <TableCell>API Name</TableCell>
              <TableCell align="right">Tests</TableCell>
              <TableCell align="center">Pass Rate</TableCell>
              <TableCell align="center">Health Score</TableCell>
              <TableCell align="center">Status</TableCell>
              <TableCell align="right">Avg RT</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {recent.map((run: RunSummary, idx) => {
              const isLatest   = idx === 0;
              const ratingColor = healthColorByRating(run.health_rating ?? '');
              const ratingBg    = healthBgByRating(run.health_rating ?? '');

              return (
                <TableRow
                  key={run.run_id}
                  hover
                  onClick={() => navigate(`/runs/${run.run_id}`)}
                  sx={{
                    cursor: 'pointer',
                    bgcolor: isLatest ? '#f8fff8' : 'transparent',
                    '&:hover': { bgcolor: '#f5f9ff' },
                  }}
                >
                  <TableCell>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                      <Tooltip title={run.run_id}>
                        <Typography variant="body2" sx={{ fontFamily: 'monospace', fontSize: '0.75rem' }}>
                          {shortId(run.run_id)}
                        </Typography>
                      </Tooltip>
                      {isLatest && (
                        <Chip label="Latest" size="small" color="primary" sx={{ height: 16, fontSize: '0.6rem' }} />
                      )}
                    </Box>
                  </TableCell>
                  <TableCell sx={{ whiteSpace: 'nowrap', fontSize: '0.8rem' }}>
                    {fmt(run.execution_timestamp)}
                  </TableCell>
                  <TableCell sx={{ fontWeight: 500, fontSize: '0.85rem' }}>{run.api_name}</TableCell>
                  <TableCell align="right" sx={{ fontSize: '0.82rem' }}>{run.total_executed}</TableCell>
                  <TableCell align="center">
                    <StatusChip value={run.pass_percentage} />
                  </TableCell>
                  <TableCell align="center">
                    {run.health_score != null
                      ? <StatusChip value={run.health_score} label={`${run.health_score.toFixed(0)}`} />
                      : <Typography variant="caption" color="text.disabled">—</Typography>}
                  </TableCell>
                  <TableCell align="center">
                    {run.health_rating ? (
                      <Chip
                        label={run.health_rating}
                        size="small"
                        sx={{
                          fontWeight: 700,
                          fontSize: '0.68rem',
                          bgcolor: ratingBg,
                          color: ratingColor,
                          border: `1px solid ${ratingColor}44`,
                        }}
                      />
                    ) : (
                      <Chip
                        label={run.pass_percentage >= 80 ? 'Passing' : run.pass_percentage >= 50 ? 'Warning' : 'Failing'}
                        size="small"
                        color={run.pass_percentage >= 80 ? 'success' : run.pass_percentage >= 50 ? 'warning' : 'error'}
                        variant="outlined"
                        sx={{ fontWeight: 600, fontSize: '0.68rem' }}
                      />
                    )}
                  </TableCell>
                  <TableCell align="right" sx={{ fontSize: '0.82rem' }}>
                    {run.avg_response_time_ms != null ? `${run.avg_response_time_ms.toFixed(0)} ms` : '—'}
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </TableContainer>

      {data.total > 10 && (
        <Box sx={{ mt: 1.5, textAlign: 'center' }}>
          <Button variant="text" size="small" onClick={() => navigate('/runs')}>
            View all {data.total} runs →
          </Button>
        </Box>
      )}
    </Box>
  );
}
