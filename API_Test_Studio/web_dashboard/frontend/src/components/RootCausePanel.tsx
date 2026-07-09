/**
 * RootCausePanel
 * Automatically derives and displays the primary root cause of failures.
 * No new API calls — computed from analytics data already fetched.
 */
import { Box, Paper, Typography, Chip, Grid } from '@mui/material';
import BugReportIcon from '@mui/icons-material/BugReport';
import type { EndpointAnalysis, FailureAnalysis, ValidatorStat, RunSummary, HealthScore } from '../types/api';
import { priorityColor } from '../utils/colors';

interface Props {
  run: RunSummary;
  health?: HealthScore | null;
  ea?: EndpointAnalysis | null;
  fa?: FailureAnalysis | null;
  validators?: ValidatorStat[];
}

interface RootCause {
  priority: 'Critical' | 'High' | 'Medium' | 'Low';
  primaryIssue: string;
  likelyCause: string;
  recommendation: string;
  detail: string;
}

function deriveRootCauses(
  run: RunSummary,
  health: HealthScore | null | undefined,
  ea: EndpointAnalysis | null | undefined,
  fa: FailureAnalysis | null | undefined,
  validators: ValidatorStat[] | undefined,
): RootCause[] {
  const causes: RootCause[] = [];

  // 1. Execution errors → infrastructure issue
  const errPct = run.total_executed > 0 ? run.errors / run.total_executed * 100 : 0;
  if (errPct > 20) {
    causes.push({
      priority: 'Critical',
      primaryIssue: `${run.errors} execution errors (${errPct.toFixed(0)}% of tests)`,
      likelyCause: 'Connectivity, authentication, or environment misconfiguration',
      recommendation: 'Verify base URL, authentication credentials, SSL settings, and network connectivity before re-running.',
      detail: 'Execution errors occur before validation and indicate the API could not be reached or returned an unexpected transport-level error.',
    });
  }

  // 2. Most-failed endpoint
  if (ea?.most_failed) {
    const failedStats = ea.all_stats.find(s => `${s.method} ${s.endpoint}` === ea.most_failed || s.endpoint === ea.most_failed);
    const failCount   = failedStats?.failed ?? '?';
    causes.push({
      priority: failedStats && failedStats.pass_rate < 30 ? 'High' : 'Medium',
      primaryIssue: `${ea.most_failed} — ${failCount} validation failures`,
      likelyCause: 'Schema mismatch or incorrect implementation',
      recommendation: `Review the ${ea.most_failed} endpoint response against the OpenAPI specification.`,
      detail: 'This endpoint generated the highest number of validation failures. Start investigation here.',
    });
  }

  // 3. Schema failures
  if (fa && fa.schema_failures > 0) {
    const schemaPct = fa.total_failures > 0 ? (fa.schema_failures / fa.total_failures * 100).toFixed(0) : '?';
    causes.push({
      priority: fa.schema_failures > 50 ? 'High' : 'Medium',
      primaryIssue: `${fa.schema_failures} schema validation failures (${schemaPct}% of all failures)`,
      likelyCause: 'API response structure does not match the OpenAPI specification',
      recommendation: 'Compare actual API responses with the schema definitions in the specification file.',
      detail: 'Schema mismatches often indicate the API has been updated without updating the specification, or vice versa.',
    });
  }

  // 4. Most-failed validator
  if (validators && validators.length > 0) {
    const worst = [...validators].sort((a, b) => b.failed - a.failed)[0];
    if (worst.failed > 0) {
      causes.push({
        priority: worst.pass_rate < 40 ? 'High' : 'Medium',
        primaryIssue: `${worst.validator_name.replace('Validator', '')} Validator — ${worst.failed} failures (${(100 - worst.pass_rate).toFixed(0)}% fail rate)`,
        likelyCause: validatorCause(worst.validator_name),
        recommendation: validatorAction(worst.validator_name),
        detail: `This validator is failing the most assertions. Fixing these failures will have the biggest impact on the overall pass rate.`,
      });
    }
  }

  // 5. Low pass rate general
  if (run.pass_percentage < 30 && causes.length < 2) {
    causes.push({
      priority: 'High',
      primaryIssue: `Overall pass rate is ${run.pass_percentage.toFixed(1)}%`,
      likelyCause: 'Negative and boundary test cases exposing unimplemented validation',
      recommendation: 'Review whether the failing tests represent expected API behaviour or real defects.',
      detail: 'A large portion of generated negative test cases is failing. This is normal if the API has not implemented strict validation — review individually.',
    });
  }

  return causes.slice(0, 4); // max 4 root causes
}

function validatorCause(name: string): string {
  if (name.includes('StatusCode'))    return 'API returns unexpected HTTP status codes';
  if (name.includes('Schema'))        return 'Response body does not match the OpenAPI schema';
  if (name.includes('Header'))        return 'Required response headers are missing or incorrect';
  if (name.includes('ResponseTime'))  return 'Responses are exceeding the configured time threshold';
  if (name.includes('Json'))          return 'Response body is not valid JSON or missing expected fields';
  if (name.includes('Business'))      return 'Business rule constraints are not satisfied';
  if (name.includes('Exact'))         return 'Response values do not match expected values';
  return 'Validation assertions are not satisfied';
}

function validatorAction(name: string): string {
  if (name.includes('StatusCode'))   return 'Review expected status codes in the OpenAPI spec and compare with actual API behaviour.';
  if (name.includes('Schema'))       return 'Synchronize the OpenAPI specification with the actual API response structure.';
  if (name.includes('Header'))       return 'Ensure the API returns all required headers (e.g. Content-Type, Authorization).';
  if (name.includes('ResponseTime')) return 'Profile the slowest endpoints and optimize database queries or external calls.';
  if (name.includes('Json'))         return 'Ensure all API responses return valid JSON with the required field structure.';
  if (name.includes('Business'))     return 'Review business rule constraints and verify the API enforces them correctly.';
  return 'Review the validator configuration and compare expected vs actual response values.';
}

export default function RootCausePanel({ run, health, ea, fa, validators }: Props) {
  const causes = deriveRootCauses(run, health, ea, fa, validators);
  if (causes.length === 0) return null;

  return (
    <Paper elevation={0} sx={{ borderRadius: 3, border: '1px solid #e8eaed', overflow: 'hidden', mb: 3 }}>
      <Box sx={{ px: 3, py: 2, bgcolor: '#fff8f0', borderBottom: '1px solid #e8eaed', display: 'flex', alignItems: 'center', gap: 1.5 }}>
        <BugReportIcon sx={{ color: '#e65100' }} />
        <Box>
          <Typography variant="subtitle1" fontWeight={700}>Root Cause Analysis</Typography>
          <Typography variant="caption" color="text.secondary">
            Automatically identified issues — investigate in priority order
          </Typography>
        </Box>
      </Box>

      <Box sx={{ p: 2 }}>
        <Grid container spacing={2}>
          {causes.map((c, i) => {
            const pColor = priorityColor(c.priority);
            return (
              <Grid item xs={12} md={6} key={i}>
                <Box
                  sx={{
                    p: 2,
                    border: `1px solid ${pColor}33`,
                    borderRadius: 2,
                    borderLeft: `4px solid ${pColor}`,
                    height: '100%',
                  }}
                >
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                    <Chip
                      label={c.priority}
                      size="small"
                      sx={{ bgcolor: pColor, color: '#fff', fontWeight: 700, fontSize: '0.7rem' }}
                    />
                    <Typography variant="caption" color="text.secondary">Priority {i + 1}</Typography>
                  </Box>
                  <Typography variant="body2" fontWeight={700} sx={{ mb: 0.5 }}>
                    {c.primaryIssue}
                  </Typography>
                  <Typography variant="caption" color="text.secondary" display="block" sx={{ mb: 0.75 }}>
                    <strong>Likely cause:</strong> {c.likelyCause}
                  </Typography>
                  <Typography variant="caption" sx={{ color: '#1a73e8' }}>
                    <strong>Action:</strong> {c.recommendation}
                  </Typography>
                </Box>
              </Grid>
            );
          })}
        </Grid>
      </Box>
    </Paper>
  );
}
