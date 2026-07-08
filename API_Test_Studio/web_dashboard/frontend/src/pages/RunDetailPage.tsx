import { useParams, useNavigate } from 'react-router-dom';
import {
  Box, Grid, Typography, Button, Divider, Chip, LinearProgress,
  Table, TableBody, TableCell, TableRow, TableHead, TableContainer, Paper,
  Alert,
} from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import SectionCard from '../components/SectionCard';
import StatCard from '../components/StatCard';
import StatusChip from '../components/StatusChip';
import PageState from '../components/PageState';
import PassFailPie from '../components/charts/PassFailPie';
import EndpointPassRateBar from '../components/charts/EndpointPassRateBar';
import FailureDistributionBar from '../components/charts/FailureDistributionBar';
import HealthGauge from '../components/charts/HealthGauge';
import { useAsync } from '../hooks/useAsync';
import runsService from '../services/runsService';
import analyticsService from '../services/analyticsService';

function fmt(ts: string | null) {
  if (!ts) return '—';
  return new Date(ts).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' });
}

function ms(v: number | null | undefined) {
  if (v == null) return '—';
  return `${v.toFixed(0)} ms`;
}

export default function RunDetailPage() {
  const { runId } = useParams<{ runId: string }>();
  const navigate = useNavigate();

  const {
    data: runDetail, loading: runLoading, error: runError, refetch: refetchRun,
  } = useAsync(() => runsService.getRun(runId!), [runId]);

  const {
    data: analytics, loading: analLoading, error: analError,
  } = useAsync(() => analyticsService.getForRun(runId!), [runId]);

  const loading = runLoading || analLoading;
  const error = runError ?? analError;

  if (loading || (error && !runDetail)) {
    return <PageState loading={loading} error={error ?? undefined} onRetry={refetchRun} />;
  }
  if (!runDetail) return <PageState empty emptyMessage="Run not found." />;

  const { run, validation_summary } = runDetail;
  const health = analytics?.health;
  const rt = analytics?.response_time;
  const ea = analytics?.endpoint_analysis;
  const fa = analytics?.failure_analysis;

  return (
    <Box>
      {/* Header */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 3 }}>
        <Button startIcon={<ArrowBackIcon />} onClick={() => navigate('/runs')} size="small">
          Runs
        </Button>
        <Typography variant="h5" sx={{ flex: 1 }}>
          {run.api_name}
          {run.api_version && (
            <Chip label={`v${run.api_version}`} size="small" sx={{ ml: 1 }} />
          )}
        </Typography>
        <StatusChip value={run.pass_percentage} />
      </Box>

      {analError && (
        <Alert severity="warning" sx={{ mb: 2 }}>
          Analytics unavailable: {analError}
        </Alert>
      )}

      {/* Execution summary cards */}
      <Grid container spacing={2.5} sx={{ mb: 3 }}>
        {[
          { title: 'Total Tests',  value: run.total_executed },
          { title: 'Passed',       value: run.passed,  color: '#34a853' },
          { title: 'Failed',       value: run.failed,  color: '#ea4335' },
          { title: 'Errors',       value: run.errors,  color: '#ff9800' },
          { title: 'Skipped',      value: run.skipped, color: '#9e9e9e' },
          { title: 'Endpoints',    value: run.total_endpoints },
        ].map(({ title, value, color }) => (
          <Grid item xs={6} sm={4} md={2} key={title}>
            <StatCard title={title} value={value} color={color} />
          </Grid>
        ))}
      </Grid>

      {/* Pass % progress */}
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

      {/* Two-column: run details + analytics highlights */}
      <Grid container spacing={2.5} sx={{ mb: 3 }}>
        <Grid item xs={12} md={6}>
          <SectionCard title="Execution Details">
            <Table size="small">
              <TableBody>
                {[
                  ['Run ID', <Typography sx={{ fontFamily: 'monospace', fontSize: '0.78rem' }}>{run.run_id}</Typography>],
                  ['API Name', run.api_name],
                  ['Environment', run.environment ?? '—'],
                  ['Date', fmt(run.execution_timestamp)],
                  ['Total Time', run.total_execution_time_s != null ? `${run.total_execution_time_s.toFixed(1)} s` : '—'],
                  ['Avg Response', ms(run.avg_response_time_ms)],
                  ['Spec File', run.specification_file ?? '—'],
                  ['Framework', run.framework_version ?? '—'],
                ].map(([label, val]) => (
                  <TableRow key={String(label)}>
                    <TableCell sx={{ color: 'text.secondary', width: '40%', border: 0 }}>{label}</TableCell>
                    <TableCell sx={{ fontWeight: 500, border: 0 }}>{val}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </SectionCard>
        </Grid>

        <Grid item xs={12} md={6}>
          <SectionCard title="Analytics Highlights">
            {!analytics ? (
              <Typography color="text.secondary" variant="body2">Analytics not available.</Typography>
            ) : (
              <Table size="small">
                <TableBody>
                  {[
                    ['Health Score', health ? `${health.score.toFixed(1)} / 100` : '—'],
                    ['Health Rating', health?.rating ?? '—'],
                    ['Mean RT', ms(rt?.mean_ms)],
                    ['Median RT', ms(rt?.median_ms)],
                    ['P95 RT', ms(rt?.p95_ms)],
                    ['P99 RT', ms(rt?.p99_ms)],
                    ['SLA Compliance', rt ? `${rt.sla_compliance_pct.toFixed(1)}%` : '—'],
                    ['Most Failed', ea?.most_failed ?? '—'],
                    ['Fastest', ea?.fastest ?? '—'],
                    ['Slowest', ea?.slowest ?? '—'],
                  ].map(([label, val]) => (
                    <TableRow key={String(label)}>
                      <TableCell sx={{ color: 'text.secondary', width: '40%', border: 0 }}>{label}</TableCell>
                      <TableCell sx={{ fontWeight: 500, border: 0 }}>{val}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </SectionCard>
        </Grid>
      </Grid>

      {/* Charts row */}
      <Grid container spacing={2.5} sx={{ mb: 3 }}>
        <Grid item xs={12} sm={6} md={4}>
          <SectionCard title="Pass vs Fail">
            <PassFailPie
              passed={run.passed}
              failed={run.failed}
              skipped={run.skipped}
              errors={run.errors}
            />
          </SectionCard>
        </Grid>

        {health && (
          <Grid item xs={12} sm={6} md={4}>
            <SectionCard title="Health Score">
              <HealthGauge score={health.score} rating={health.rating} />
            </SectionCard>
          </Grid>
        )}

        {fa && fa.distribution.length > 0 && (
          <Grid item xs={12} md={health ? 4 : 8}>
            <SectionCard title="Failure Distribution">
              <FailureDistributionBar distribution={fa.distribution} />
            </SectionCard>
          </Grid>
        )}
      </Grid>

      {/* Endpoint pass rates */}
      {ea && ea.all_stats.length > 0 && (
        <Box sx={{ mb: 3 }}>
          <SectionCard title="Endpoint Pass Rate" subheader={`${ea.all_stats.length} endpoint(s)`}>
            <EndpointPassRateBar stats={ea.all_stats} />
          </SectionCard>
        </Box>
      )}

      {/* Validator breakdown */}
      {validation_summary && (
        <Box sx={{ mb: 3 }}>
          <SectionCard title="Validator Breakdown">
            <TableContainer>
              <Table size="small">
                <TableHead>
                  <TableRow sx={{ '& th': { fontWeight: 600, bgcolor: '#f8f9fa' } }}>
                    <TableCell>Validator</TableCell>
                    <TableCell align="right">Total</TableCell>
                    <TableCell align="right">Passed</TableCell>
                    <TableCell align="right">Failed</TableCell>
                    <TableCell align="center">Pass Rate</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {validation_summary.validators.map((v) => (
                    <TableRow key={v.validator_name}>
                      <TableCell sx={{ fontFamily: 'monospace', fontSize: '0.8rem' }}>
                        {v.validator_name}
                      </TableCell>
                      <TableCell align="right">{v.total}</TableCell>
                      <TableCell align="right" sx={{ color: '#34a853', fontWeight: 600 }}>{v.passed}</TableCell>
                      <TableCell align="right" sx={{ color: '#ea4335', fontWeight: 600 }}>{v.failed}</TableCell>
                      <TableCell align="center"><StatusChip value={v.pass_rate} /></TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          </SectionCard>
        </Box>
      )}

      {/* Health recommendations */}
      {health && health.recommendations.length > 0 && (
        <Box sx={{ mb: 3 }}>
          <SectionCard title="Recommendations">
            <Box component="ul" sx={{ m: 0, pl: 2.5 }}>
              {health.recommendations.map((rec, i) => (
                <li key={i}>
                  <Typography variant="body2" color="text.secondary">{rec}</Typography>
                </li>
              ))}
            </Box>
          </SectionCard>
        </Box>
      )}
    </Box>
  );
}
