// src/components/ExecutionCompleteScreen.tsx
// Shown after the job reaches status === 'completed'.
import { useNavigate } from 'react-router-dom';
import {
  Box, Typography, Paper, Button, Grid, Divider, LinearProgress, Chip,
} from '@mui/material';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import BarChartIcon from '@mui/icons-material/BarChart';
import ReplayIcon from '@mui/icons-material/Replay';
import type { JobStatusResponse } from '../types/upload';
import type { RunSummary } from '../types/api';

interface Props {
  job: JobStatusResponse;
  run: RunSummary | null;
  onRunAnother: () => void;
}

function ms(v: number | null | undefined) {
  if (v == null) return '—';
  return `${v.toFixed(0)} ms`;
}

export default function ExecutionCompleteScreen({ job, run, onRunAnother }: Props) {
  const navigate = useNavigate();
  const runId = job.run_id!;

  return (
    <Box sx={{ maxWidth: 680, mx: 'auto', mt: 4 }}>
      <Paper sx={{ p: 4, borderRadius: 3 }}>
        {/* Success header */}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 3 }}>
          <CheckCircleIcon sx={{ color: 'success.main', fontSize: 40 }} />
          <Box>
            <Typography variant="h6">Execution Complete</Typography>
            <Typography variant="body2" color="text.secondary">
              {run?.api_name ?? job.spec_filename} — {job.environment}
            </Typography>
          </Box>
          {run && (
            <Chip
              label={`${run.pass_percentage.toFixed(1)}% passed`}
              color={run.pass_percentage >= 80 ? 'success' : run.pass_percentage >= 50 ? 'warning' : 'error'}
              sx={{ ml: 'auto', fontWeight: 700 }}
            />
          )}
        </Box>

        {/* Pass rate bar */}
        {run && (
          <Box sx={{ mb: 3 }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
              <Typography variant="body2" color="text.secondary">Pass Rate</Typography>
              <Typography variant="body2" fontWeight={600}>{run.pass_percentage.toFixed(1)}%</Typography>
            </Box>
            <LinearProgress
              variant="determinate"
              value={run.pass_percentage}
              color={run.pass_percentage >= 80 ? 'success' : run.pass_percentage >= 50 ? 'warning' : 'error'}
              sx={{ height: 8, borderRadius: 4 }}
            />
          </Box>
        )}

        {/* Stats grid */}
        {run && (
          <Grid container spacing={2} sx={{ mb: 3 }}>
            {[
              { label: 'Run ID',       value: run.run_id.slice(0, 18) + '…', mono: true },
              { label: 'API Name',     value: run.api_name },
              { label: 'Environment',  value: run.environment ?? '—' },
              { label: 'Total Tests',  value: run.total_executed },
              { label: 'Passed',       value: run.passed,  color: '#34a853' },
              { label: 'Failed',       value: run.failed,  color: '#ea4335' },
              { label: 'Errors',       value: run.errors,  color: '#ff9800' },
              { label: 'Skipped',      value: run.skipped, color: '#9e9e9e' },
              { label: 'Avg RT',       value: ms(run.avg_response_time_ms) },
              { label: 'Exec Time',    value: run.total_execution_time_s != null ? `${run.total_execution_time_s.toFixed(1)} s` : (job.elapsed_s != null ? `${job.elapsed_s.toFixed(1)} s` : '—') },
            ].map(({ label, value, color, mono }) => (
              <Grid item xs={6} sm={4} key={label}>
                <Box sx={{ p: 1.5, bgcolor: '#f8f9fa', borderRadius: 1.5 }}>
                  <Typography variant="caption" color="text.secondary" display="block">{label}</Typography>
                  <Typography
                    variant="subtitle2"
                    fontWeight={700}
                    sx={{ color: color ?? 'text.primary', fontFamily: mono ? 'monospace' : undefined, fontSize: mono ? '0.75rem' : undefined }}
                  >
                    {String(value)}
                  </Typography>
                </Box>
              </Grid>
            ))}
          </Grid>
        )}

        <Divider sx={{ mb: 3 }} />

        {/* Action buttons */}
        <Box sx={{ display: 'flex', gap: 1.5, flexWrap: 'wrap' }}>
          <Button
            variant="contained"
            startIcon={<OpenInNewIcon />}
            onClick={() => navigate(`/runs/${runId}`)}
          >
            View Run
          </Button>
          <Button
            variant="outlined"
            startIcon={<BarChartIcon />}
            onClick={() => navigate(`/analytics?run=${runId}`)}
          >
            View Analytics
          </Button>
          <Button
            variant="text"
            startIcon={<ReplayIcon />}
            onClick={onRunAnother}
            sx={{ ml: 'auto' }}
          >
            Run Another
          </Button>
        </Box>
      </Paper>
    </Box>
  );
}
