/**
 * ExecutionSummaryCard
 * A prominent plain-English summary shown at the top of every run detail view.
 * Reads only from the RunSummary and HealthScore objects — no new API calls.
 */
import { Box, Paper, Typography, Grid, Divider, Chip } from '@mui/material';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline';
import type { RunSummary, HealthScore } from '../types/api';

interface Props {
  run: RunSummary;
  health?: HealthScore | null;
}

function healthColor(rating: string): string {
  switch (rating.toLowerCase()) {
    case 'excellent':      return '#1b5e20';  // dark green
    case 'good':           return '#2e7d32';  // green
    case 'needs attention':return '#e65100';  // orange
    case 'critical':       return '#b71c1c';  // dark red
    default:               return '#555';
  }
}

function healthBgColor(rating: string): string {
  switch (rating.toLowerCase()) {
    case 'excellent':      return '#f1f8f1';
    case 'good':           return '#e8f5e9';
    case 'needs attention':return '#fff3e0';
    case 'critical':       return '#fce4e4';
    default:               return '#f5f5f5';
  }
}

function plainEnglishSummary(run: RunSummary): string {
  const { pass_percentage, errors, failed, total_executed } = run;
  const errorPct = total_executed > 0 ? (errors / total_executed) * 100 : 0;
  const failPct  = total_executed > 0 ? (failed / total_executed) * 100 : 0;

  if (pass_percentage >= 80) {
    return 'This execution completed successfully — the API is responding as expected across the majority of generated test cases.';
  }
  if (errorPct > 30) {
    return 'A high number of execution errors occurred. This typically indicates connectivity, authentication, timeout, or configuration problems rather than API logic failures.';
  }
  if (failPct > 50 && pass_percentage < 30) {
    return 'This execution completed, but many generated negative and boundary-condition test cases failed validation. Review whether this matches the expected API behaviour.';
  }
  if (pass_percentage >= 50) {
    return 'Execution completed with mixed results. Some endpoints are behaving as expected while others have validation failures worth investigating.';
  }
  return 'Execution completed, but the overall pass rate is low. Review the failure distribution and validator breakdown below to identify the root cause.';
}

export default function ExecutionSummaryCard({ run, health }: Props) {
  const summary = plainEnglishSummary(run);
  const rating  = health?.rating ?? '';
  const bgColor = rating ? healthBgColor(rating) : '#fafafa';
  const fgColor = rating ? healthColor(rating) : '#555';

  const StatusIcon = run.pass_percentage >= 80
    ? CheckCircleIcon
    : run.pass_percentage >= 50
      ? WarningAmberIcon
      : ErrorOutlineIcon;

  const iconColor = run.pass_percentage >= 80
    ? '#34a853'
    : run.pass_percentage >= 50
      ? '#f57c00'
      : '#c62828';

  const rows: Array<{ label: string; value: string | number; highlight?: string }> = [
    { label: 'API',                    value: run.api_name },
    { label: 'Endpoints Tested',       value: run.total_endpoints },
    { label: 'Generated Test Cases',   value: run.total_test_cases },
    { label: 'Successfully Executed',  value: run.total_executed },
    { label: 'Passed Test Cases',      value: run.passed,  highlight: '#2e7d32' },
    { label: 'Validation Failures',    value: run.failed,  highlight: run.failed > 0 ? '#e65100' : undefined },
    { label: 'Execution Errors',       value: run.errors,  highlight: run.errors > 0 ? '#c62828' : undefined },
    { label: 'Overall Pass Rate',      value: `${run.pass_percentage.toFixed(1)}%` },
    ...(rating ? [{ label: 'Health', value: rating }] : []),
  ];

  return (
    <Paper
      elevation={0}
      sx={{
        mb: 3,
        borderRadius: 3,
        border: '1px solid #e8eaed',
        overflow: 'hidden',
      }}
    >
      {/* Header bar */}
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          gap: 1.5,
          px: 3,
          py: 2,
          bgcolor: bgColor,
          borderBottom: '1px solid #e8eaed',
        }}
      >
        <StatusIcon sx={{ color: iconColor, fontSize: 28 }} />
        <Box sx={{ flex: 1 }}>
          <Typography variant="subtitle1" fontWeight={700}>
            Execution Summary
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 0.25 }}>
            {summary}
          </Typography>
        </Box>
        {rating && (
          <Chip
            label={rating}
            size="small"
            sx={{
              fontWeight: 700,
              bgcolor: fgColor,
              color: '#fff',
              fontSize: '0.75rem',
              flexShrink: 0,
            }}
          />
        )}
      </Box>

      {/* Metrics grid */}
      <Box sx={{ px: 3, py: 2 }}>
        <Grid container spacing={0}>
          {rows.map(({ label, value, highlight }, i) => (
            <Grid item xs={12} sm={6} md={4} key={label}>
              <Box
                sx={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  py: 0.75,
                  borderBottom: i < rows.length - 1 ? '1px solid #f1f1f1' : 'none',
                  pr: { sm: 3 },
                }}
              >
                <Typography variant="body2" color="text.secondary">{label}</Typography>
                <Typography
                  variant="body2"
                  fontWeight={700}
                  sx={{ color: highlight ?? 'text.primary' }}
                >
                  {value}
                </Typography>
              </Box>
            </Grid>
          ))}
        </Grid>
      </Box>
    </Paper>
  );
}
