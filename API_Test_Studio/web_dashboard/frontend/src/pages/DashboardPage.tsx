import { useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box, Grid, Typography, Paper, Table, TableBody, TableCell,
  TableContainer, TableHead, TableRow, Tooltip,
} from '@mui/material';
import AssessmentIcon from '@mui/icons-material/Assessment';
import SpeedIcon from '@mui/icons-material/Speed';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import FavoriteIcon from '@mui/icons-material/Favorite';
import StatCard from '../components/StatCard';
import StatusChip from '../components/StatusChip';
import PageState from '../components/PageState';
import { useAsync } from '../hooks/useAsync';
import runsService from '../services/runsService';
import type { RunSummary } from '../types/api';

function fmt(ts: string | null) {
  if (!ts) return '—';
  return new Date(ts).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' });
}

function shortId(id: string) {
  return id.slice(0, 13) + '…';
}

export default function DashboardPage() {
  const navigate = useNavigate();
  const { data, loading, error, refetch } = useAsync(
    () => runsService.listRuns({ page: 1, page_size: 50 }),
    [],
  );

  const stats = useMemo(() => {
    if (!data?.runs.length) return null;
    const runs = data.runs;
    const total = data.total;
    const avgPass = runs.reduce((s, r) => s + r.pass_percentage, 0) / runs.length;
    const rtRuns = runs.filter(r => r.avg_response_time_ms != null);
    const avgRt = rtRuns.length
      ? rtRuns.reduce((s, r) => s + r.avg_response_time_ms!, 0) / rtRuns.length
      : null;
    const hsRuns = runs.filter(r => r.health_score != null);
    const avgHs = hsRuns.length
      ? hsRuns.reduce((s, r) => s + r.health_score!, 0) / hsRuns.length
      : null;
    return { total, avgPass, avgRt, avgHs };
  }, [data]);

  if (loading || error || !data?.runs.length) {
    return (
      <>
        <Typography variant="h5" gutterBottom>Dashboard</Typography>
        <PageState
          loading={loading}
          error={error}
          empty={!loading && !error}
          emptyMessage="No execution runs found. Run a test suite to see results here."
          onRetry={refetch}
        />
      </>
    );
  }

  const recent = data.runs.slice(0, 10);

  return (
    <Box>
      <Typography variant="h5" gutterBottom>Dashboard</Typography>

      {/* Summary cards */}
      <Grid container spacing={2.5} sx={{ mb: 3 }}>
        <Grid item xs={12} sm={6} md={3}>
          <StatCard
            title="Total Runs"
            value={stats?.total}
            icon={<AssessmentIcon />}
            color="#1a73e8"
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <StatCard
            title="Avg Pass Rate"
            value={stats ? `${stats.avgPass.toFixed(1)}%` : null}
            icon={<CheckCircleIcon />}
            color="#34a853"
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <StatCard
            title="Avg Response Time"
            value={stats?.avgRt != null ? `${stats.avgRt.toFixed(0)} ms` : '—'}
            icon={<SpeedIcon />}
            color="#fbbc04"
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <StatCard
            title="Avg Health Score"
            value={stats?.avgHs != null ? `${stats.avgHs.toFixed(1)}` : '—'}
            subtitle="out of 100"
            icon={<FavoriteIcon />}
            color="#ea4335"
          />
        </Grid>
      </Grid>

      {/* Recent runs table */}
      <Typography variant="subtitle1" gutterBottom>Recent Runs</Typography>
      <TableContainer component={Paper} sx={{ borderRadius: 2 }}>
        <Table size="small">
          <TableHead>
            <TableRow sx={{ '& th': { fontWeight: 600, bgcolor: '#f8f9fa' } }}>
              <TableCell>Run ID</TableCell>
              <TableCell>Date</TableCell>
              <TableCell>API Name</TableCell>
              <TableCell align="right">Tests</TableCell>
              <TableCell align="center">Pass %</TableCell>
              <TableCell align="center">Health</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {recent.map((run: RunSummary) => (
              <TableRow
                key={run.run_id}
                hover
                onClick={() => navigate(`/runs/${run.run_id}`)}
                sx={{ cursor: 'pointer' }}
              >
                <TableCell>
                  <Tooltip title={run.run_id}>
                    <Typography variant="body2" sx={{ fontFamily: 'monospace', fontSize: '0.78rem' }}>
                      {shortId(run.run_id)}
                    </Typography>
                  </Tooltip>
                </TableCell>
                <TableCell sx={{ whiteSpace: 'nowrap' }}>{fmt(run.execution_timestamp)}</TableCell>
                <TableCell>{run.api_name}</TableCell>
                <TableCell align="right">{run.total_executed}</TableCell>
                <TableCell align="center">
                  <StatusChip value={run.pass_percentage} />
                </TableCell>
                <TableCell align="center">
                  {run.health_score != null
                    ? <StatusChip value={run.health_score} label={`${run.health_score.toFixed(0)}`} />
                    : '—'}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
    </Box>
  );
}
