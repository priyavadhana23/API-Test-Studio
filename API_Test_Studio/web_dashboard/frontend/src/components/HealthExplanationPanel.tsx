/**
 * HealthExplanationPanel
 * "Instead of showing only Health Score 63.2, show WHY."
 * Displays health rating, numeric score, positive/negative factors, and overall assessment.
 */
import { Box, Paper, Typography, Divider, LinearProgress } from '@mui/material';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import CancelIcon from '@mui/icons-material/Cancel';
import type { HealthScore, ResponseTimeStats, RunSummary } from '../types/api';
import { healthColorByRating, healthBgByRating } from '../utils/colors';

interface Props {
  health: HealthScore;
  rt?: ResponseTimeStats | null;
  run: RunSummary;
}

interface Factor { good: boolean; text: string }

function deriveFactors(h: HealthScore, rt: ResponseTimeStats | null | undefined, run: RunSummary): Factor[] {
  const factors: Factor[] = [];

  // Availability
  factors.push({ good: true,  text: 'API is reachable and accepting connections' });

  // Response time
  if (rt) {
    const slaOk = rt.sla_compliance_pct >= 95;
    factors.push({ good: slaOk, text: slaOk
      ? `Excellent response time — SLA compliance ${rt.sla_compliance_pct.toFixed(1)}%`
      : `SLA compliance is ${rt.sla_compliance_pct.toFixed(1)}% — some requests are slow` });
  }

  // Validation failures
  if (run.pass_percentage < 50) {
    factors.push({ good: false, text: `High validation failure count — ${run.failed} failures (${(100 - run.pass_percentage).toFixed(0)}% of tests)` });
  } else if (run.pass_percentage < 80) {
    factors.push({ good: false, text: `Moderate validation failures — pass rate ${run.pass_percentage.toFixed(1)}%` });
  } else {
    factors.push({ good: true,  text: `Low failure rate — ${run.pass_percentage.toFixed(1)}% of tests passed` });
  }

  // Execution errors
  if (run.errors > 0) {
    const errPct = run.total_executed > 0 ? run.errors / run.total_executed * 100 : 0;
    factors.push({ good: errPct < 5, text: errPct >= 5
      ? `${run.errors} execution errors (${errPct.toFixed(0)}% of tests) — connectivity or auth issues`
      : `${run.errors} minor execution errors detected` });
  }

  // Schema / stability
  if (h.stability_score < 50) {
    factors.push({ good: false, text: 'Schema mismatches detected — API responses may not match the specification' });
  } else if (h.stability_score >= 80) {
    factors.push({ good: true,  text: 'Response schema is consistent with the OpenAPI specification' });
  }

  return factors;
}

function overallAssessment(h: HealthScore, run: RunSummary): string {
  const r = h.rating.toLowerCase();
  if (r === 'excellent') return 'API is fully operational and production-ready. All validations pass.';
  if (r === 'good')      return 'API is operational with minor issues. Safe for production with monitoring.';
  if (r.includes('attention')) {
    if (run.errors > run.failed) {
      return 'API is reachable but functionally unstable. Execution errors suggest infrastructure or configuration issues rather than logic failures.';
    }
    return `API is operational but functionally unstable. ${run.failed} validation failures require investigation before release.`;
  }
  return 'API is in a critical state. Multiple validation failures and/or execution errors detected. Release is not recommended.';
}

export default function HealthExplanationPanel({ health, rt, run }: Props) {
  const color  = healthColorByRating(health.rating);
  const bgColor = healthBgByRating(health.rating);
  const factors = deriveFactors(health, rt, run);

  const scoreComponents = [
    { label: 'Pass Rate',      score: health.pass_rate_score,      weight: '40%' },
    { label: 'Response Time',  score: health.response_time_score,  weight: '25%' },
    { label: 'Stability',      score: health.stability_score,      weight: '20%' },
    { label: 'Availability',   score: health.availability_score,   weight: '15%' },
  ];

  return (
    <Paper elevation={0} sx={{ borderRadius: 3, border: `1px solid ${color}44`, overflow: 'hidden', mb: 3 }}>
      {/* Header */}
      <Box sx={{ px: 3, py: 2, bgcolor: bgColor, borderBottom: `1px solid ${color}33` }}>
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 1 }}>
          <Box>
            <Typography variant="overline" sx={{ color, fontWeight: 700, letterSpacing: '0.1em' }}>
              API Health
            </Typography>
            <Typography variant="h4" sx={{ color, fontWeight: 800, lineHeight: 1.1 }}>
              {health.rating}
            </Typography>
          </Box>
          <Box sx={{ textAlign: 'right' }}>
            <Typography variant="caption" color="text.secondary">Health Score</Typography>
            <Typography variant="h3" sx={{ color, fontWeight: 800, lineHeight: 1 }}>
              {health.score.toFixed(1)}
              <Typography component="span" variant="h6" sx={{ color: 'text.secondary', ml: 0.5 }}>/ 100</Typography>
            </Typography>
          </Box>
        </Box>
      </Box>

      {/* Score breakdown */}
      <Box sx={{ px: 3, py: 2, borderBottom: '1px solid #f0f0f0' }}>
        <Typography variant="caption" color="text.secondary" fontWeight={700} display="block" sx={{ mb: 1.5 }}>
          SCORE BREAKDOWN
        </Typography>
        <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: 1.5 }}>
          {scoreComponents.map(({ label, score, weight }) => (
            <Box key={label}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
                <Typography variant="caption" color="text.secondary">{label} <span style={{ opacity: 0.5 }}>({weight})</span></Typography>
                <Typography variant="caption" fontWeight={700} sx={{ color: score >= 70 ? '#2e7d32' : score >= 40 ? '#e65100' : '#c62828' }}>
                  {score.toFixed(0)}
                </Typography>
              </Box>
              <LinearProgress
                variant="determinate"
                value={score}
                sx={{
                  height: 5,
                  borderRadius: 3,
                  bgcolor: '#f0f0f0',
                  '& .MuiLinearProgress-bar': {
                    bgcolor: score >= 70 ? '#2e7d32' : score >= 40 ? '#e65100' : '#c62828',
                    borderRadius: 3,
                  },
                }}
              />
            </Box>
          ))}
        </Box>
      </Box>

      {/* Positive / negative factors */}
      <Box sx={{ px: 3, py: 2, borderBottom: '1px solid #f0f0f0' }}>
        <Typography variant="caption" color="text.secondary" fontWeight={700} display="block" sx={{ mb: 1 }}>
          HEALTH FACTORS
        </Typography>
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.75 }}>
          {factors.map((f, i) => (
            <Box key={i} sx={{ display: 'flex', alignItems: 'flex-start', gap: 1 }}>
              {f.good
                ? <CheckCircleIcon sx={{ color: '#2e7d32', fontSize: 16, mt: '2px', flexShrink: 0 }} />
                : <CancelIcon      sx={{ color: '#c62828', fontSize: 16, mt: '2px', flexShrink: 0 }} />}
              <Typography variant="body2" sx={{ color: f.good ? 'text.primary' : '#c62828' }}>
                {f.text}
              </Typography>
            </Box>
          ))}
        </Box>
      </Box>

      {/* Overall assessment */}
      <Box sx={{ px: 3, py: 2, bgcolor: '#fafafa' }}>
        <Typography variant="caption" color="text.secondary" fontWeight={700} display="block" sx={{ mb: 0.5 }}>
          OVERALL ASSESSMENT
        </Typography>
        <Typography variant="body2" fontWeight={500}>
          {overallAssessment(health, run)}
        </Typography>
      </Box>
    </Paper>
  );
}
