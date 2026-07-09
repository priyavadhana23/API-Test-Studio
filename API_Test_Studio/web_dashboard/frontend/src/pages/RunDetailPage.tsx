/**
 * RunDetailPage — Enterprise QA Dashboard view for a single execution run.
 *
 * Sections (in order):
 *  1. Executive Summary Card
 *  2. KPI stat cards
 *  3. Pass rate bar
 *  4. API Health Explanation Panel
 *  5. Root Cause Analysis
 *  6. Execution Timeline
 *  7. Tester Summary
 *  8. Charts row (Pass/Fail pie + Health gauge + Failure distribution)
 *  9. Endpoint Health Cards
 * 10. Developer Diagnostics
 * 11. Validator Breakdown (redesigned)
 * 12. Failure Analysis Table
 * 13. Priority Recommendations
 */
import { useParams, useNavigate } from 'react-router-dom';
import {
  Box, Grid, Typography, Button, Chip, LinearProgress,
  Alert,
} from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';

// Shared components
import StatCard from '../components/StatCard';
import StatusChip from '../components/StatusChip';
import PageState from '../components/PageState';
import MetricTooltip from '../components/MetricTooltip';
import SectionCard from '../components/SectionCard';

// New enterprise components
import ExecutionSummaryCard    from '../components/ExecutionSummaryCard';
import HealthExplanationPanel  from '../components/HealthExplanationPanel';
import RootCausePanel          from '../components/RootCausePanel';
import ExecutionTimeline       from '../components/ExecutionTimeline';
import TesterSummary           from '../components/TesterSummary';
import EndpointHealthCards     from '../components/EndpointHealthCards';
import DeveloperDiagnostics    from '../components/DeveloperDiagnostics';
import ValidatorBreakdownTable from '../components/ValidatorBreakdownTable';
import FailureAnalysisTable    from '../components/FailureAnalysisTable';
import PriorityRecommendations from '../components/PriorityRecommendations';

// Charts
import PassFailPie         from '../components/charts/PassFailPie';
import HealthGauge         from '../components/charts/HealthGauge';
import FailureDistributionBar from '../components/charts/FailureDistributionBar';

// Services
import { useAsync } from '../hooks/useAsync';
import runsService     from '../services/runsService';
import analyticsService from '../services/analyticsService';

const TOOLTIPS = {
  passRate:    'Percentage of generated test cases that completely passed all validations.',
  passed:      'Test cases where every validation assertion passed.',
  failed:      'Test cases where at least one validation assertion failed. These may indicate the API response does not match the specification.',
  errors:      'Execution failures such as network errors, invalid URLs, connection failures, or authentication problems. These are infrastructure issues, not API logic failures.',
  skipped:     'Test cases that were not executed, usually because a prerequisite step failed.',
  healthScore: 'A calculated 0–100 indicator based on pass rate (40%), response time (25%), stability (20%), and availability (15%).',
} as const;

export default function RunDetailPage() {
  const { runId } = useParams<{ runId: string }>();
  const navigate  = useNavigate();

  const {
    data: runDetail, loading: runLoading, error: runError, refetch: refetchRun,
  } = useAsync(() => runsService.getRun(runId!), [runId]);

  const {
    data: analytics, loading: analLoading, error: analError,
  } = useAsync(() => analyticsService.getForRun(runId!), [runId]);

  const loading = runLoading || analLoading;
  const error   = runError ?? analError;

  if (loading || (error && !runDetail)) {
    return (
      <PageState
        loading={loading}
        loadingMessage="Loading run details and analytics…"
        error={error ?? undefined}
        onRetry={refetchRun}
      />
    );
  }
  if (!runDetail) return <PageState empty emptyMessage="Run not found." />;

  const { run, validation_summary } = runDetail;
  const health    = analytics?.health;
  const rt        = analytics?.response_time;
  const ea        = analytics?.endpoint_analysis;
  const fa        = analytics?.failure_analysis;
  const validators = validation_summary?.validators ?? [];

  return (
    <Box>
      {/* ── Page header ───────────────────────────────────────────── */}
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

      {/* ── 1. Executive Summary Card ─────────────────────────────── */}
      <ExecutionSummaryCard run={run} health={health} />

      {/* ── 2. KPI stat cards ─────────────────────────────────────── */}
      <Grid container spacing={2} sx={{ mb: 3 }}>
        {[
          { title: 'Total Tests',          value: run.total_executed,  color: '#1a73e8', tooltip: 'Total test cases generated and executed against the API.' },
          { title: 'Passed Test Cases',     value: run.passed,          color: '#2e7d32', tooltip: TOOLTIPS.passed },
          { title: 'Validation Failures',   value: run.failed,          color: run.failed  > 0 ? '#e65100' : '#2e7d32', tooltip: TOOLTIPS.failed },
          { title: 'Execution Errors',      value: run.errors,          color: run.errors  > 0 ? '#c62828' : '#2e7d32', tooltip: TOOLTIPS.errors },
          { title: 'Skipped',               value: run.skipped,         color: '#757575',  tooltip: TOOLTIPS.skipped },
          { title: 'Endpoints',             value: run.total_endpoints, color: '#1a73e8',  tooltip: 'Number of unique API endpoint paths in the specification.' },
        ].map(({ title, value, color, tooltip }) => (
          <Grid item xs={6} sm={4} md={2} key={title}>
            <StatCard title={title} value={value} color={color} tooltip={tooltip} />
          </Grid>
        ))}
      </Grid>

      {/* ── 3. Pass rate bar ──────────────────────────────────────── */}
      <Box sx={{ mb: 3 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 0.5 }}>
          <Box sx={{ display: 'flex', alignItems: 'center' }}>
            <Typography variant="body2" color="text.secondary" fontWeight={500}>
              Overall Test Success Rate
            </Typography>
            <MetricTooltip text={TOOLTIPS.passRate} />
          </Box>
          <Typography variant="body2" fontWeight={800}>
            {run.pass_percentage.toFixed(1)}%
          </Typography>
        </Box>
        <LinearProgress
          variant="determinate"
          value={run.pass_percentage}
          color={run.pass_percentage >= 80 ? 'success' : run.pass_percentage >= 50 ? 'warning' : 'error'}
          sx={{ height: 10, borderRadius: 5 }}
        />
      </Box>

      {/* ── 4. API Health Explanation ─────────────────────────────── */}
      {health && <HealthExplanationPanel health={health} rt={rt} run={run} />}

      {/* ── 5. Root Cause Analysis ────────────────────────────────── */}
      <RootCausePanel run={run} health={health} ea={ea} fa={fa} validators={validators} />

      {/* ── 6. Execution Timeline ─────────────────────────────────── */}
      <ExecutionTimeline
        run={run}
        hasAnalytics={!!analytics}
        hasReports={runDetail.report_links.length > 0}
      />

      {/* ── 7. Tester Summary ─────────────────────────────────────── */}
      <TesterSummary run={run} reportCount={runDetail.report_links.length} />

      {/* ── 8. Charts row ─────────────────────────────────────────── */}
      <Grid container spacing={2.5} sx={{ mb: 3 }}>
        <Grid item xs={12} sm={6} md={4}>
          <SectionCard
            title="Pass vs Fail Distribution"
            subheader="Result breakdown across all test cases"
          >
            <PassFailPie
              passed={run.passed}
              failed={run.failed}
              skipped={run.skipped}
              errors={run.errors}
            />
            <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 1, textAlign: 'center' }}>
              {run.failed > 0
                ? `${run.failed} validation failures detected. Most failures originated from the ${ea?.most_failed ?? 'endpoint with lowest pass rate'}.`
                : 'All executed test cases passed validation.'}
              {run.errors > 0 && ` ${run.errors} execution errors indicate infrastructure issues.`}
            </Typography>
          </SectionCard>
        </Grid>

        {health && (
          <Grid item xs={12} sm={6} md={4}>
            <SectionCard
              title="Health Score"
              subheader="Composite quality indicator (0–100)"
            >
              <HealthGauge score={health.score} rating={health.rating} />
              <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 1, textAlign: 'center' }}>
                Weighted score: pass rate 40% · response time 25% · stability 20% · availability 15%.
                {health.score < 60 && ' Developer investigation recommended.'}
              </Typography>
            </SectionCard>
          </Grid>
        )}

        {fa && fa.distribution.length > 0 && (
          <Grid item xs={12} md={health ? 4 : 8}>
            <SectionCard
              title="Failure Distribution"
              subheader={`${fa.total_failures} total failures by validator category`}
            >
              <FailureDistributionBar distribution={fa.distribution} />
              <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 1, textAlign: 'center' }}>
                Shows which validators are responsible for the most failures. Schema and status-code failures indicate specification mismatches.
              </Typography>
            </SectionCard>
          </Grid>
        )}
      </Grid>

      {/* ── 9. Endpoint Health Cards ──────────────────────────────── */}
      {ea && ea.all_stats.length > 0 && (
        <Box sx={{ mb: 3 }}>
          <Box sx={{ mb: 1.5 }}>
            <Typography variant="subtitle1" fontWeight={700}>Endpoint Health</Typography>
            <Typography variant="caption" color="text.secondary">
              {ea.all_stats.length} endpoint(s) — sorted by pass rate ascending. Click a card to expand details.
            </Typography>
          </Box>
          <EndpointHealthCards stats={ea.all_stats} />
        </Box>
      )}

      {/* ── 10. Developer Diagnostics ─────────────────────────────── */}
      {ea && ea.all_stats.length > 0 && (
        <DeveloperDiagnostics
          endpointStats={ea.all_stats}
          validators={validators}
          fa={fa}
        />
      )}

      {/* ── 11. Validator Breakdown ───────────────────────────────── */}
      {validators.length > 0 && (
        <ValidatorBreakdownTable validators={validators} />
      )}

      {/* ── 12. Failure Analysis Table ────────────────────────────── */}
      {fa && fa.distribution.length > 0 && (
        <FailureAnalysisTable
          distribution={fa.distribution}
          totalFailures={fa.total_failures}
        />
      )}

      {/* ── 13. Priority Recommendations ─────────────────────────── */}
      <PriorityRecommendations run={run} health={health} ea={ea} fa={fa} />
    </Box>
  );
}
