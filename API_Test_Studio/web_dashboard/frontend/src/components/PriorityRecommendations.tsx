/**
 * PriorityRecommendations
 * Prioritized action cards replacing generic bullet-point recommendations.
 */
import { Box, Paper, Typography, Chip } from '@mui/material';
import LightbulbIcon from '@mui/icons-material/Lightbulb';
import type { HealthScore, EndpointAnalysis, FailureAnalysis, RunSummary } from '../types/api';
import { priorityColor } from '../utils/colors';

interface Recommendation {
  priority: number;
  level:    'Critical' | 'High' | 'Medium' | 'Low';
  title:    string;
  reason:   string;
  action:   string;
}

interface Props {
  health?: HealthScore | null;
  ea?: EndpointAnalysis | null;
  fa?: FailureAnalysis | null;
  run: RunSummary;
}

function buildRecommendations(
  health: HealthScore | null | undefined,
  ea: EndpointAnalysis | null | undefined,
  fa: FailureAnalysis | null | undefined,
  run: RunSummary,
): Recommendation[] {
  const recs: Recommendation[] = [];
  let prio = 1;

  // Execution errors first
  const errPct = run.total_executed > 0 ? run.errors / run.total_executed * 100 : 0;
  if (errPct > 5) {
    recs.push({
      priority: prio++,
      level:    errPct > 20 ? 'Critical' : 'High',
      title:    'Investigate execution errors',
      reason:   `${run.errors} execution errors (${errPct.toFixed(0)}%) indicate infrastructure issues preventing the API from being reached.`,
      action:   'Verify the base URL, authentication credentials, SSL certificate, and network connectivity. Execution errors are not validation failures.',
    });
  }

  // Most failed endpoint
  if (ea?.most_failed) {
    recs.push({
      priority: prio++,
      level:    'High',
      title:    `Review ${ea.most_failed}`,
      reason:   `This endpoint generated the highest number of validation failures in this run.`,
      action:   `Compare the actual response from ${ea.most_failed} against the schema definition in the specification file.`,
    });
  }

  // Schema failures
  if (fa && fa.schema_failures > 10) {
    recs.push({
      priority: prio++,
      level:    fa.schema_failures > 50 ? 'High' : 'Medium',
      title:    'Fix schema mismatches',
      reason:   `${fa.schema_failures} schema validation failures detected. The API response structure does not match the OpenAPI specification.`,
      action:   'Update the OpenAPI specification to match the current API contract, or fix the API implementation to return the specified schema.',
    });
  }

  // Health score recommendations from analytics engine
  if (health) {
    health.recommendations.slice(0, 3).forEach((rec) => {
      recs.push({
        priority: prio++,
        level:    'Medium',
        title:    rec.length > 60 ? rec.slice(0, 60) + '…' : rec,
        reason:   rec,
        action:   'See the full analytics section for details.',
      });
    });
  }

  // Regression recommendation
  recs.push({
    priority: prio++,
    level:    'Low',
    title:    'Re-run regression tests after fixes',
    reason:   'After addressing high-priority issues, re-run the full test suite to confirm regressions are resolved.',
    action:   'Use the Upload & Execute page to re-run the same specification and compare results.',
  });

  return recs.slice(0, 6);
}

export default function PriorityRecommendations({ health, ea, fa, run }: Props) {
  const recs = buildRecommendations(health, ea, fa, run);
  if (recs.length === 0) return null;

  return (
    <Paper elevation={0} sx={{ borderRadius: 3, border: '1px solid #e8eaed', overflow: 'hidden', mb: 3 }}>
      <Box sx={{ px: 3, py: 2, bgcolor: '#f8f9fa', borderBottom: '1px solid #e8eaed', display: 'flex', alignItems: 'center', gap: 1.5 }}>
        <LightbulbIcon sx={{ color: '#f57c00' }} />
        <Box>
          <Typography variant="subtitle1" fontWeight={700}>Recommendations</Typography>
          <Typography variant="caption" color="text.secondary">
            Prioritized actions — address in order
          </Typography>
        </Box>
      </Box>

      <Box sx={{ p: 2.5, display: 'flex', flexDirection: 'column', gap: 1.5 }}>
        {recs.map((r) => {
          const pColor = priorityColor(r.level);
          return (
            <Box
              key={r.priority}
              sx={{
                p: 2,
                border: '1px solid #e8eaed',
                borderRadius: 2,
                borderLeft: `4px solid ${pColor}`,
                bgcolor: '#fafafa',
              }}
            >
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.75 }}>
                <Box
                  sx={{
                    width: 24, height: 24, borderRadius: '50%',
                    bgcolor: pColor, color: '#fff',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontSize: '0.75rem', fontWeight: 800, flexShrink: 0,
                  }}
                >
                  {r.priority}
                </Box>
                <Typography variant="body2" fontWeight={700}>{r.title}</Typography>
                <Chip
                  label={r.level}
                  size="small"
                  sx={{ ml: 'auto', bgcolor: pColor + '20', color: pColor, fontWeight: 700, fontSize: '0.65rem', height: 18 }}
                />
              </Box>
              <Typography variant="caption" color="text.secondary" display="block" sx={{ mb: 0.5, pl: 4 }}>
                {r.reason}
              </Typography>
              <Typography variant="caption" sx={{ color: '#1a73e8', pl: 4 }}>
                → {r.action}
              </Typography>
            </Box>
          );
        })}
      </Box>
    </Paper>
  );
}
