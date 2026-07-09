/**
 * TesterSummary — dedicated section for QA engineers.
 * Answers: "Can I sign off? Is the API ready for regression testing?"
 */
import { Box, Grid, Paper, Typography, Divider, Chip } from '@mui/material';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import CancelIcon from '@mui/icons-material/Cancel';
import AssignmentTurnedInIcon from '@mui/icons-material/AssignmentTurnedIn';
import type { RunSummary } from '../types/api';

interface Props {
  run: RunSummary;
  reportCount?: number;
}

function readyForRegression(run: RunSummary): boolean {
  return run.pass_percentage >= 80 && run.errors < run.total_executed * 0.05;
}

export default function TesterSummary({ run, reportCount = 0 }: Props) {
  const ready  = readyForRegression(run);
  const execTime = run.total_execution_time_s != null
    ? `${run.total_execution_time_s.toFixed(1)} s`
    : '—';

  const metrics = [
    { label: 'Endpoints Tested',    value: run.total_endpoints,   color: '#1a73e8' },
    { label: 'Generated Test Cases',value: run.total_test_cases,  color: '#1a73e8' },
    { label: 'Executed Tests',       value: run.total_executed,   color: '#1a73e8' },
    { label: 'Passed',               value: run.passed,            color: '#2e7d32' },
    { label: 'Validation Failures',  value: run.failed,            color: run.failed > 0 ? '#e65100' : '#2e7d32' },
    { label: 'Execution Errors',     value: run.errors,            color: run.errors > 0 ? '#c62828' : '#2e7d32' },
    { label: 'Skipped',              value: run.skipped,           color: '#757575' },
    { label: 'Reports Generated',    value: reportCount,           color: '#1a73e8' },
    { label: 'Execution Duration',   value: execTime,              color: '#546e7a' },
  ];

  return (
    <Paper elevation={0} sx={{ borderRadius: 3, border: '1px solid #e8eaed', overflow: 'hidden', mb: 3 }}>
      {/* Header */}
      <Box sx={{ px: 3, py: 2, bgcolor: '#f8f9fa', borderBottom: '1px solid #e8eaed', display: 'flex', alignItems: 'center', gap: 1.5 }}>
        <AssignmentTurnedInIcon sx={{ color: '#1a73e8' }} />
        <Box sx={{ flex: 1 }}>
          <Typography variant="subtitle1" fontWeight={700}>Tester Summary</Typography>
          <Typography variant="caption" color="text.secondary">Execution metrics and regression readiness</Typography>
        </Box>
        <Box sx={{ textAlign: 'right' }}>
          <Typography variant="caption" color="text.secondary" display="block">Ready for Regression</Typography>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, justifyContent: 'flex-end' }}>
            {ready
              ? <CheckCircleIcon sx={{ color: '#2e7d32', fontSize: 20 }} />
              : <CancelIcon      sx={{ color: '#c62828', fontSize: 20 }} />}
            <Chip
              label={ready ? 'YES' : 'NO'}
              size="small"
              sx={{
                bgcolor: ready ? '#2e7d32' : '#c62828',
                color: '#fff',
                fontWeight: 800,
                fontSize: '0.75rem',
              }}
            />
          </Box>
        </Box>
      </Box>

      {/* Metrics grid */}
      <Box sx={{ p: 2.5 }}>
        <Grid container spacing={1.5}>
          {metrics.map(({ label, value, color }) => (
            <Grid item xs={6} sm={4} md={3} key={label}>
              <Box sx={{ p: 1.5, bgcolor: '#f8f9fa', borderRadius: 2, height: '100%' }}>
                <Typography variant="caption" color="text.secondary" display="block" sx={{ mb: 0.25 }}>
                  {label}
                </Typography>
                <Typography variant="h6" fontWeight={700} sx={{ color }}>
                  {value}
                </Typography>
              </Box>
            </Grid>
          ))}
        </Grid>

        {!ready && (
          <Box sx={{ mt: 2, p: 1.5, bgcolor: '#fff3e0', borderRadius: 2, border: '1px solid #ffe0b2' }}>
            <Typography variant="body2" sx={{ color: '#e65100' }}>
              <strong>Not ready for regression.</strong>{' '}
              {run.pass_percentage < 80
                ? `Pass rate is ${run.pass_percentage.toFixed(1)}% (threshold: 80%).`
                : `${run.errors} execution errors exceed the 5% threshold.`}
              {' '}Investigate and re-run before proceeding.
            </Typography>
          </Box>
        )}
      </Box>
    </Paper>
  );
}
