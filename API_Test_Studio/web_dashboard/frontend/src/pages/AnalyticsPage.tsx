import { useState } from 'react';
import {
  Box, Grid, Typography, MenuItem, Select, FormControl,
  InputLabel, Table, TableBody, TableCell, TableHead, TableRow,
  TableContainer, Paper, Chip, Alert,
} from '@mui/material';
import SectionCard from '../components/SectionCard';
import StatCard from '../components/StatCard';
import PageState from '../components/PageState';
import StatusChip from '../components/StatusChip';
import HealthGauge from '../components/charts/HealthGauge';
import EndpointPassRateBar from '../components/charts/EndpointPassRateBar';
import FailureDistributionBar from '../components/charts/FailureDistributionBar';
import ResponseTimeTrend from '../components/charts/ResponseTimeTrend';
import { useAsync } from '../hooks/useAsync';
import runsService from '../services/runsService';
import analyticsService from '../services/analyticsService';

function ms(v: number | null | undefined) {
  if (v == null) return '—';
  return `${v.toFixed(0)} ms`;
}

export default function AnalyticsPage() {
  const [selectedRunId, setSelectedRunId] = useState<string>('');

  // Load run list so user can pick which run to inspect
  const { data: runList, loading: runsLoading, error: runsError } = useAsync(
    () => runsService.listRuns({ page: 1, page_size: 100 }),
    [],
  );

  // Determine the run to show: user selection or latest
  const targetRunId = selectedRunId || runList?.runs[0]?.run_id;

  const {
    data: analytics, loading: analLoading, error: analError, refetch,
  } = useAsync(
    () => (targetRunId ? analyticsService.getForRun(targetRunId) : Promise.reject(new Error('No run'))),
    [targetRunId],
  );

  const loading = runsLoading || analLoading;

  if (loading) return <PageState loading />;

  if (runsError) return <PageState error={runsError} onRetry={refetch} />;

  if (!runList?.runs.length) {
    return (
      <PageState
        empty
        emptyMessage="No execution runs found. Run a test suite first to view analytics."
      />
    );
  }

  const health = analytics?.health;
  const rt    = analytics?.response_time;
  const ea    = analytics?.endpoint_analysis;
  const fa    = analytics?.failure_analysis;
  const trend = analytics?.trend;
  const reg   = analytics?.regression;

  return (
    <Box>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 3, flexWrap: 'wrap' }}>
        <Typography variant="h5" sx={{ flex: 1 }}>Analytics</Typography>

        <FormControl size="small" sx={{ minWidth: 300 }}>
          <InputLabel>Run</InputLabel>
          <Select
            value={selectedRunId || runList.runs[0]?.run_id || ''}
            label="Run"
            onChange={(e) => setSelectedRunId(e.target.value)}
          >
            {runList.runs.map((r) => (
              <MenuItem key={r.run_id} value={r.run_id}>
                {r.api_name} — {r.execution_timestamp
                  ? new Date(r.execution_timestamp).toLocaleDateString()
                  : r.run_id.slice(0, 13)}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
      </Box>

      {analError && (
        <Alert severity="error" sx={{ mb: 2 }}>{analError}</Alert>
      )}

      {!analytics ? (
        <PageState loading={analLoading} error={analError ?? undefined} onRetry={refetch} />
      ) : (
        <>
          {/* Top stat cards */}
          <Grid container spacing={2.5} sx={{ mb: 3 }}>
            <Grid item xs={6} sm={3}>
              <StatCard title="Health Score"  value={health ? `${health.score.toFixed(1)}` : '—'} subtitle={health?.rating} color="#1a73e8" />
            </Grid>
            <Grid item xs={6} sm={3}>
              <StatCard title="Mean RT"       value={ms(rt?.mean_ms)}   color="#fbbc04" />
            </Grid>
            <Grid item xs={6} sm={3}>
              <StatCard title="P95 RT"        value={ms(rt?.p95_ms)}    color="#ff9800" />
            </Grid>
            <Grid item xs={6} sm={3}>
              <StatCard title="SLA Compliance" value={rt ? `${rt.sla_compliance_pct.toFixed(1)}%` : '—'} color="#34a853" />
            </Grid>
          </Grid>

          {/* Health gauge + RT stats */}
          <Grid container spacing={2.5} sx={{ mb: 3 }}>
            {health && (
              <Grid item xs={12} md={4}>
                <SectionCard title="Health Score">
                  <HealthGauge score={health.score} rating={health.rating} />
                  <Box sx={{ mt: 1 }}>
                    {[
                      ['Pass Rate Score',      health.pass_rate_score],
                      ['Response Time Score',  health.response_time_score],
                      ['Stability Score',      health.stability_score],
                      ['Availability Score',   health.availability_score],
                    ].map(([label, val]) => (
                      <Box key={String(label)} sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
                        <Typography variant="caption" color="text.secondary">{label}</Typography>
                        <Typography variant="caption" fontWeight={600}>{Number(val).toFixed(1)}</Typography>
                      </Box>
                    ))}
                  </Box>
                </SectionCard>
              </Grid>
            )}

            {rt && (
              <Grid item xs={12} md={health ? 8 : 12}>
                <SectionCard title="Response Time Statistics">
                  <Grid container spacing={1.5}>
                    {[
                      ['Samples',   rt.sample_count],
                      ['Mean',      ms(rt.mean_ms)],
                      ['Median',    ms(rt.median_ms)],
                      ['Std Dev',   ms(rt.std_dev_ms)],
                      ['Min',       ms(rt.min_ms)],
                      ['Max',       ms(rt.max_ms)],
                      ['P95',       ms(rt.p95_ms)],
                      ['P99',       ms(rt.p99_ms)],
                      ['SLA Threshold', ms(rt.sla_threshold_ms)],
                      ['SLA Compliance', `${rt.sla_compliance_pct.toFixed(1)}%`],
                    ].map(([label, val]) => (
                      <Grid item xs={6} sm={4} key={String(label)}>
                        <Box sx={{ p: 1.5, bgcolor: '#f8f9fa', borderRadius: 1.5 }}>
                          <Typography variant="caption" color="text.secondary" display="block">{label}</Typography>
                          <Typography variant="subtitle2" fontWeight={700}>{val}</Typography>
                        </Box>
                      </Grid>
                    ))}
                  </Grid>
                </SectionCard>
              </Grid>
            )}
          </Grid>

          {/* Endpoint performance */}
          {ea && ea.all_stats.length > 0 && (
            <Box sx={{ mb: 3 }}>
              <SectionCard
                title="Endpoint Performance"
                subheader={`${ea.all_stats.length} endpoint(s)`}
              >
                <EndpointPassRateBar stats={ea.all_stats} />

                {/* Highlights */}
                <Grid container spacing={1.5} sx={{ mt: 1 }}>
                  {[
                    ['Most Executed',   ea.most_executed],
                    ['Least Executed',  ea.least_executed],
                    ['Most Failed',     ea.most_failed],
                    ['Most Successful', ea.most_successful],
                    ['Slowest',         ea.slowest],
                    ['Fastest',         ea.fastest],
                  ].filter(([, v]) => v).map(([label, val]) => (
                    <Grid item xs={12} sm={6} md={4} key={String(label)}>
                      <Box sx={{ p: 1.5, bgcolor: '#f8f9fa', borderRadius: 1.5 }}>
                        <Typography variant="caption" color="text.secondary" display="block">{label}</Typography>
                        <Typography variant="body2" fontWeight={600} sx={{ fontFamily: 'monospace', fontSize: '0.8rem' }}>{val}</Typography>
                      </Box>
                    </Grid>
                  ))}
                </Grid>

                {/* Detailed table */}
                <TableContainer sx={{ mt: 2 }}>
                  <Table size="small">
                    <TableHead>
                      <TableRow sx={{ '& th': { fontWeight: 600, bgcolor: '#f8f9fa' } }}>
                        <TableCell>Endpoint</TableCell>
                        <TableCell>Method</TableCell>
                        <TableCell align="right">Executions</TableCell>
                        <TableCell align="right">Passed</TableCell>
                        <TableCell align="right">Failed</TableCell>
                        <TableCell align="center">Pass Rate</TableCell>
                        <TableCell align="right">Avg RT</TableCell>
                        <TableCell align="right">P95</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {ea.all_stats.map((s) => (
                        <TableRow key={`${s.method}-${s.endpoint}`}>
                          <TableCell sx={{ fontFamily: 'monospace', fontSize: '0.8rem' }}>{s.endpoint}</TableCell>
                          <TableCell><Chip label={s.method} size="small" /></TableCell>
                          <TableCell align="right">{s.total_executions}</TableCell>
                          <TableCell align="right" sx={{ color: '#34a853' }}>{s.passed}</TableCell>
                          <TableCell align="right" sx={{ color: '#ea4335' }}>{s.failed}</TableCell>
                          <TableCell align="center"><StatusChip value={s.pass_rate} /></TableCell>
                          <TableCell align="right">{ms(s.avg_response_time_ms)}</TableCell>
                          <TableCell align="right">{ms(s.p95_response_time_ms)}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              </SectionCard>
            </Box>
          )}

          {/* Failure distribution */}
          {fa && fa.distribution.length > 0 && (
            <Box sx={{ mb: 3 }}>
              <SectionCard title="Failure Distribution" subheader={`${fa.total_failures} total failures`}>
                <FailureDistributionBar distribution={fa.distribution} />
              </SectionCard>
            </Box>
          )}

          {/* Trend */}
          {trend && trend.points.length > 1 && (
            <Box sx={{ mb: 3 }}>
              <SectionCard title={`Trend — ${trend.name}`} subheader={`Direction: ${trend.direction}`}>
                <ResponseTimeTrend points={trend.points} movingAvg={trend.moving_avg} />
              </SectionCard>
            </Box>
          )}

          {/* Regression */}
          {reg && (
            <Box sx={{ mb: 3 }}>
              <SectionCard
                title="Regression Summary"
                subheader={reg.verdict}
                action={
                  <Chip
                    label={reg.has_regression ? 'Regression Detected' : 'No Regression'}
                    color={reg.has_regression ? 'error' : 'success'}
                    size="small"
                  />
                }
              >
                <Grid container spacing={2}>
                  {[
                    { label: 'New Failures',       items: reg.new_failures,       color: '#ea4335' },
                    { label: 'Fixed Failures',      items: reg.fixed_failures,      color: '#34a853' },
                    { label: 'Unchanged Failures',  items: reg.unchanged_failures,  color: '#9e9e9e' },
                  ].map(({ label, items, color }) => (
                    <Grid item xs={12} md={4} key={label}>
                      <Typography variant="caption" color="text.secondary" fontWeight={600}>{label} ({items.length})</Typography>
                      {items.length === 0 ? (
                        <Typography variant="body2" color="text.disabled">None</Typography>
                      ) : (
                        <Box component="ul" sx={{ m: 0, pl: 2, mt: 0.5 }}>
                          {items.slice(0, 5).map((f, i) => (
                            <li key={i}><Typography variant="body2" sx={{ color, fontSize: '0.78rem' }}>{f}</Typography></li>
                          ))}
                          {items.length > 5 && (
                            <Typography variant="caption" color="text.secondary">+{items.length - 5} more</Typography>
                          )}
                        </Box>
                      )}
                    </Grid>
                  ))}
                </Grid>
                <Box sx={{ mt: 1.5, display: 'flex', gap: 3 }}>
                  <Typography variant="caption">
                    Pass Rate Δ: <strong>{reg.pass_rate_delta > 0 ? '+' : ''}{reg.pass_rate_delta.toFixed(2)}%</strong>
                  </Typography>
                  {reg.avg_rt_delta_ms != null && (
                    <Typography variant="caption">
                      Avg RT Δ: <strong>{reg.avg_rt_delta_ms > 0 ? '+' : ''}{reg.avg_rt_delta_ms.toFixed(0)} ms</strong>
                    </Typography>
                  )}
                </Box>
              </SectionCard>
            </Box>
          )}

          {/* Recommendations */}
          {health && health.recommendations.length > 0 && (
            <Box sx={{ mb: 3 }}>
              <SectionCard title="Recommendations">
                <Box component="ul" sx={{ m: 0, pl: 2.5 }}>
                  {health.recommendations.map((rec, i) => (
                    <li key={i}><Typography variant="body2" color="text.secondary">{rec}</Typography></li>
                  ))}
                </Box>
              </SectionCard>
            </Box>
          )}
        </>
      )}
    </Box>
  );
}
