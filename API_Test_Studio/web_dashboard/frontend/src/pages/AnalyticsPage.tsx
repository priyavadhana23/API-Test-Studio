import { useState } from 'react';
import {
  Box, Grid, Typography, MenuItem, Select, FormControl,
  InputLabel, Table, TableBody, TableCell, TableHead, TableRow,
  TableContainer, Chip, Alert,
} from '@mui/material';
import SectionCard from '../components/SectionCard';
import StatCard from '../components/StatCard';
import PageState from '../components/PageState';
import StatusChip from '../components/StatusChip';
import MetricTooltip from '../components/MetricTooltip';
import HealthGauge from '../components/charts/HealthGauge';
import EndpointPassRateBar from '../components/charts/EndpointPassRateBar';
import FailureDistributionBar from '../components/charts/FailureDistributionBar';
import ResponseTimeTrend from '../components/charts/ResponseTimeTrend';
import { useAsync } from '../hooks/useAsync';
import runsService from '../services/runsService';
import analyticsService from '../services/analyticsService';

const TOOLTIPS = {
  healthScore:  'A calculated 0–100 indicator based on pass rate (40%), response time (25%), stability (20%), and availability (15%).',
  meanRt:       'The arithmetic mean of all HTTP response times. Skewed by very slow requests — use median for a more representative view.',
  p95:          '95% of all requests completed within this response time. A high P95 may indicate occasional slow responses or timeout issues.',
  p99:          '99% of all requests completed within this response time. Reflects worst-case latency.',
  sla:          'Percentage of requests that completed within the configured SLA threshold. Below 100% means some requests exceeded acceptable response time.',
  passRate:     'Percentage of generated test cases that completely passed all validation assertions.',
  stability:    'Measures consistency of pass/fail results across test categories. High stability means results are predictable.',
  availability: 'Measures whether the API was reachable during testing. 100% means no connection failures.',
};

function ms(v: number | null | undefined) {
  if (v == null) return '—';
  return `${v.toFixed(0)} ms`;
}

export default function AnalyticsPage() {
  const [selectedRunId, setSelectedRunId] = useState<string>('');

  const { data: runList, loading: runsLoading, error: runsError } = useAsync(
    () => runsService.listRuns({ page: 1, page_size: 100 }),
    [],
  );

  const targetRunId = selectedRunId || runList?.runs[0]?.run_id;

  const {
    data: analytics, loading: analLoading, error: analError, refetch,
  } = useAsync(
    () => (targetRunId ? analyticsService.getForRun(targetRunId) : Promise.reject(new Error('No run'))),
    [targetRunId],
  );

  const loading = runsLoading || analLoading;

  if (loading) return <PageState loading loadingMessage="Loading analytics data…" />;
  if (runsError) return <PageState error={runsError} onRetry={refetch} />;

  if (!runList?.runs.length) {
    return (
      <PageState
        empty
        emptyMessage="No API executions found. Upload an OpenAPI specification to begin automated testing."
      />
    );
  }

  const health = analytics?.health;
  const rt     = analytics?.response_time;
  const ea     = analytics?.endpoint_analysis;
  const fa     = analytics?.failure_analysis;
  const trend  = analytics?.trend;
  const reg    = analytics?.regression;

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
          {/* Top stat cards with tooltips */}
          <Grid container spacing={2.5} sx={{ mb: 3 }}>
            <Grid item xs={6} sm={3}>
              <StatCard
                title="Health Score"
                value={health ? `${health.score.toFixed(1)}` : '—'}
                subtitle={health?.rating}
                color="#1a73e8"
                tooltip={TOOLTIPS.healthScore}
              />
            </Grid>
            <Grid item xs={6} sm={3}>
              <StatCard title="Mean Response Time" value={ms(rt?.mean_ms)} color="#e65100" tooltip={TOOLTIPS.meanRt} />
            </Grid>
            <Grid item xs={6} sm={3}>
              <StatCard title="P95 Response Time" value={ms(rt?.p95_ms)} color="#f57c00" tooltip={TOOLTIPS.p95} />
            </Grid>
            <Grid item xs={6} sm={3}>
              <StatCard title="SLA Compliance" value={rt ? `${rt.sla_compliance_pct.toFixed(1)}%` : '—'} color="#2e7d32" tooltip={TOOLTIPS.sla} />
            </Grid>
          </Grid>

          {/* Health gauge + RT stats */}
          <Grid container spacing={2.5} sx={{ mb: 3 }}>
            {health && (
              <Grid item xs={12} md={4}>
                <SectionCard
                  title="Health Score"
                  subheader="Composite quality indicator (0–100)"
                >
                  <HealthGauge score={health.score} rating={health.rating} />
                  <Typography variant="caption" color="text.secondary" display="block" sx={{ textAlign: 'center', mt: 1 }}>
                    Weighted score: pass rate 40%, response time 25%, stability 20%, availability 15%.
                  </Typography>
                  <Box sx={{ mt: 1.5 }}>
                    {[
                      { label: 'Pass Rate Score',      val: health.pass_rate_score,     tip: TOOLTIPS.passRate },
                      { label: 'Response Time Score',  val: health.response_time_score, tip: TOOLTIPS.meanRt },
                      { label: 'Stability Score',      val: health.stability_score,     tip: TOOLTIPS.stability },
                      { label: 'Availability Score',   val: health.availability_score,  tip: TOOLTIPS.availability },
                    ].map(({ label, val, tip }) => (
                      <Box key={label} sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 0.5 }}>
                        <Box sx={{ display: 'flex', alignItems: 'center' }}>
                          <Typography variant="caption" color="text.secondary">{label}</Typography>
                          <MetricTooltip text={tip} />
                        </Box>
                        <Typography variant="caption" fontWeight={700}>{Number(val).toFixed(1)}</Typography>
                      </Box>
                    ))}
                  </Box>
                </SectionCard>
              </Grid>
            )}

            {rt && (
              <Grid item xs={12} md={health ? 8 : 12}>
                <SectionCard
                  title="Response Time Statistics"
                  subheader={`${rt.sample_count} request samples`}
                >
                  <Grid container spacing={1.5}>
                    {[
                      { label: 'Mean',          val: ms(rt.mean_ms),                tip: TOOLTIPS.meanRt },
                      { label: 'Median',        val: ms(rt.median_ms),              tip: 'The middle value of all response times — less affected by outliers than the mean.' },
                      { label: 'Std Dev',       val: ms(rt.std_dev_ms),             tip: 'Standard deviation of response times. High values indicate inconsistent performance.' },
                      { label: 'Min',           val: ms(rt.min_ms) },
                      { label: 'Max',           val: ms(rt.max_ms) },
                      { label: 'P95',           val: ms(rt.p95_ms),                 tip: TOOLTIPS.p95 },
                      { label: 'P99',           val: ms(rt.p99_ms),                 tip: TOOLTIPS.p99 },
                      { label: 'SLA Threshold', val: ms(rt.sla_threshold_ms),       tip: 'The maximum acceptable response time. Set in the environment configuration.' },
                      { label: 'SLA Compliance',val: `${rt.sla_compliance_pct.toFixed(1)}%`, tip: TOOLTIPS.sla },
                      { label: 'Samples',       val: rt.sample_count },
                    ].map(({ label, val, tip }) => (
                      <Grid item xs={6} sm={4} key={label}>
                        <Box sx={{ p: 1.5, bgcolor: '#f8f9fa', borderRadius: 1.5 }}>
                          <Box sx={{ display: 'flex', alignItems: 'center' }}>
                            <Typography variant="caption" color="text.secondary" display="block">{label}</Typography>
                            {tip && <MetricTooltip text={tip} />}
                          </Box>
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
                subheader={`${ea.all_stats.length} endpoint(s) tested`}
              >
                <EndpointPassRateBar stats={ea.all_stats} />
                <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 1, textAlign: 'center' }}>
                  Sorted by pass rate ascending — endpoints with the most failures appear at the top.
                </Typography>

                <Grid container spacing={1.5} sx={{ mt: 1.5 }}>
                  {[
                    { label: 'Most Executed',    val: ea.most_executed,   desc: 'Endpoint with the highest number of generated test cases.' },
                    { label: 'Most Failed',      val: ea.most_failed,     desc: 'Endpoint with the highest number of failing test cases.' },
                    { label: 'Most Successful',  val: ea.most_successful, desc: 'Endpoint with the best pass rate.' },
                    { label: 'Slowest',          val: ea.slowest,         desc: 'Endpoint with the highest average response time.' },
                    { label: 'Fastest',          val: ea.fastest,         desc: 'Endpoint with the lowest average response time.' },
                    { label: 'Least Executed',   val: ea.least_executed,  desc: 'Endpoint with the fewest generated test cases.' },
                  ].filter(item => item.val).map(({ label, val, desc }) => (
                    <Grid item xs={12} sm={6} md={4} key={label}>
                      <Box sx={{ p: 1.5, bgcolor: '#f8f9fa', borderRadius: 1.5 }}>
                        <Box sx={{ display: 'flex', alignItems: 'center' }}>
                          <Typography variant="caption" color="text.secondary" display="block">{label}</Typography>
                          <MetricTooltip text={desc} />
                        </Box>
                        <Typography variant="body2" fontWeight={600} sx={{ fontFamily: 'monospace', fontSize: '0.8rem' }}>
                          {val}
                        </Typography>
                      </Box>
                    </Grid>
                  ))}
                </Grid>

                {/* Detailed endpoint table */}
                <TableContainer sx={{ mt: 2 }}>
                  <Table size="small">
                    <TableHead>
                      <TableRow sx={{ '& th': { fontWeight: 600, bgcolor: '#f8f9fa' } }}>
                        <TableCell>Endpoint</TableCell>
                        <TableCell>Method</TableCell>
                        <TableCell align="right">Executions</TableCell>
                        <TableCell align="right" sx={{ color: '#2e7d32' }}>Passed</TableCell>
                        <TableCell align="right" sx={{ color: '#e65100' }}>Failed</TableCell>
                        <TableCell align="center">Pass Rate</TableCell>
                        <TableCell align="right">Avg RT</TableCell>
                        <TableCell align="right">P95</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {ea.all_stats.map((s) => (
                        <TableRow key={`${s.method}-${s.endpoint}`} hover>
                          <TableCell sx={{ fontFamily: 'monospace', fontSize: '0.8rem' }}>{s.endpoint}</TableCell>
                          <TableCell><Chip label={s.method} size="small" /></TableCell>
                          <TableCell align="right">{s.total_executions}</TableCell>
                          <TableCell align="right" sx={{ color: '#2e7d32', fontWeight: 600 }}>{s.passed}</TableCell>
                          <TableCell align="right" sx={{ color: s.failed > 0 ? '#e65100' : 'text.secondary', fontWeight: s.failed > 0 ? 600 : 400 }}>{s.failed}</TableCell>
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
              <SectionCard
                title="Failure Distribution"
                subheader={`${fa.total_failures} total failures across all test cases`}
              >
                <FailureDistributionBar distribution={fa.distribution} />
                <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 1, textAlign: 'center' }}>
                  Shows which validation categories are responsible for the most failures. Schema and status-code failures typically indicate specification mismatches.
                </Typography>
              </SectionCard>
            </Box>
          )}

          {/* Trend */}
          {trend && trend.points.length > 1 && (
            <Box sx={{ mb: 3 }}>
              <SectionCard
                title={`Trend — ${trend.name}`}
                subheader={`Direction: ${trend.direction} · ${trend.points.length} data points`}
              >
                <ResponseTimeTrend points={trend.points} movingAvg={trend.moving_avg} />
                <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 1, textAlign: 'center' }}>
                  The dotted line shows the moving average, which smooths short-term fluctuations to reveal the overall direction.
                </Typography>
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
                    sx={{ fontWeight: 700 }}
                  />
                }
              >
                <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                  Compares this run against the baseline run to identify which failures are new, which were fixed, and which remain unchanged.
                </Typography>
                <Grid container spacing={2}>
                  {[
                    { label: 'New Failures',      items: reg.new_failures,       color: '#c62828', desc: 'These failures did not appear in the baseline run.' },
                    { label: 'Fixed Failures',     items: reg.fixed_failures,     color: '#2e7d32', desc: 'These failures from the baseline run are now passing.' },
                    { label: 'Unchanged Failures', items: reg.unchanged_failures, color: '#757575', desc: 'These failures existed in the baseline and are still failing.' },
                  ].map(({ label, items, color, desc }) => (
                    <Grid item xs={12} md={4} key={label}>
                      <Box sx={{ display: 'flex', alignItems: 'center', mb: 0.5 }}>
                        <Typography variant="caption" color="text.secondary" fontWeight={700}>
                          {label} ({items.length})
                        </Typography>
                        <MetricTooltip text={desc} />
                      </Box>
                      {items.length === 0 ? (
                        <Typography variant="body2" color="text.disabled">None</Typography>
                      ) : (
                        <Box component="ul" sx={{ m: 0, pl: 2, mt: 0.5 }}>
                          {items.slice(0, 5).map((f, i) => (
                            <li key={i}>
                              <Typography variant="body2" sx={{ color, fontSize: '0.78rem' }}>{f}</Typography>
                            </li>
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
                    Pass Rate Δ:&nbsp;
                    <strong style={{ color: reg.pass_rate_delta >= 0 ? '#2e7d32' : '#c62828' }}>
                      {reg.pass_rate_delta > 0 ? '+' : ''}{reg.pass_rate_delta.toFixed(2)}%
                    </strong>
                  </Typography>
                  {reg.avg_rt_delta_ms != null && (
                    <Typography variant="caption">
                      Avg RT Δ:&nbsp;
                      <strong style={{ color: reg.avg_rt_delta_ms <= 0 ? '#2e7d32' : '#e65100' }}>
                        {reg.avg_rt_delta_ms > 0 ? '+' : ''}{reg.avg_rt_delta_ms.toFixed(0)} ms
                      </strong>
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
                <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                  These recommendations are generated by the analytics engine based on this run's results.
                </Typography>
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
                  {health.recommendations.map((rec, i) => (
                    <Box
                      key={i}
                      sx={{
                        p: 1.5,
                        bgcolor: '#f8f9fa',
                        borderRadius: 2,
                        borderLeft: '3px solid #1a73e8',
                      }}
                    >
                      <Typography variant="body2" color="text.secondary">{rec}</Typography>
                    </Box>
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
