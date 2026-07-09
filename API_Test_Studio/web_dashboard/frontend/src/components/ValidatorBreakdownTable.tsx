/**
 * ValidatorBreakdownTable
 * Redesigned validator section with purpose, impact, result, and suggested action per validator.
 */
import { Box, Paper, Typography, Chip, Table, TableBody, TableCell, TableHead, TableRow, TableContainer, LinearProgress } from '@mui/material';
import VerifiedIcon from '@mui/icons-material/Verified';
import type { ValidatorStat } from '../types/api';
import StatusChip from './StatusChip';

interface Props {
  validators: ValidatorStat[];
}

interface ValidatorMeta {
  purpose:  string;
  impact:   'Critical' | 'High' | 'Medium' | 'Low';
  action:   string;
}

const VALIDATOR_META: Record<string, ValidatorMeta> = {
  StatusCodeValidator: {
    purpose: 'Ensures the API returns the expected HTTP status code for each test scenario.',
    impact:  'High',
    action:  'Review expected vs actual status codes. Check that success/error paths return the correct codes.',
  },
  HeaderValidator: {
    purpose: 'Verifies required response headers (e.g. Content-Type, Cache-Control) are present and correct.',
    impact:  'Medium',
    action:  'Ensure the API consistently returns all headers defined in the specification.',
  },
  ResponseTimeValidator: {
    purpose: 'Checks that each response was received within the configured SLA time threshold.',
    impact:  'Medium',
    action:  'Profile slow endpoints. Consider caching, query optimisation, or increasing the timeout threshold.',
  },
  JsonValidator: {
    purpose: 'Validates that the response body is parseable JSON and contains required top-level fields.',
    impact:  'High',
    action:  'Ensure all endpoints return valid JSON. Check error responses for non-JSON fallback bodies.',
  },
  JsonSchemaValidator: {
    purpose: 'Validates the complete response body structure against the JSON Schema defined in the OpenAPI spec.',
    impact:  'Critical',
    action:  'Synchronize the OpenAPI specification with the actual API response structure.',
  },
  ExactResponseValidator: {
    purpose: 'Verifies specific field values in the response body match expected values defined in the test case.',
    impact:  'Medium',
    action:  'Compare expected vs actual field values. Update tests or fix the API implementation.',
  },
  BusinessRuleValidator: {
    purpose: 'Checks domain-specific business rules such as field constraints, enum values, and conditional logic.',
    impact:  'High',
    action:  'Review business rule definitions and verify the API enforces them correctly.',
  },
};

const IMPACT_COLORS: Record<string, string> = {
  Critical: '#b71c1c',
  High:     '#e65100',
  Medium:   '#f57c00',
  Low:      '#1a73e8',
};

export default function ValidatorBreakdownTable({ validators }: Props) {
  if (validators.length === 0) return null;

  return (
    <Paper elevation={0} sx={{ borderRadius: 3, border: '1px solid #e8eaed', overflow: 'hidden', mb: 3 }}>
      <Box sx={{ px: 3, py: 2, bgcolor: '#f8f9fa', borderBottom: '1px solid #e8eaed', display: 'flex', alignItems: 'center', gap: 1.5 }}>
        <VerifiedIcon sx={{ color: '#1a73e8' }} />
        <Box>
          <Typography variant="subtitle1" fontWeight={700}>Validation Breakdown</Typography>
          <Typography variant="caption" color="text.secondary">
            Per-validator purpose, result, and recommended action
          </Typography>
        </Box>
      </Box>

      {/* Card-per-validator layout for easy scanning */}
      <Box sx={{ p: 2.5, display: 'flex', flexDirection: 'column', gap: 2 }}>
        {[...validators].sort((a, b) => b.failed - a.failed).map((v) => {
          const meta    = VALIDATOR_META[v.validator_name];
          const impact  = meta?.impact ?? 'Medium';
          const iColor  = IMPACT_COLORS[impact] ?? '#546e7a';
          const passing = v.failed === 0;

          return (
            <Box
              key={v.validator_name}
              sx={{
                p: 2,
                border: '1px solid #e8eaed',
                borderRadius: 2,
                borderLeft: `4px solid ${passing ? '#2e7d32' : iColor}`,
                bgcolor: passing ? '#fafffe' : '#fffbf8',
              }}
            >
              <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1.5, flexWrap: 'wrap' }}>
                <Box sx={{ flex: 1, minWidth: 200 }}>
                  {/* Name + impact */}
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
                    <Typography variant="body2" fontWeight={700}>
                      {v.validator_name.replace('Validator', '')} Validator
                    </Typography>
                    <Chip
                      label={`Impact: ${impact}`}
                      size="small"
                      sx={{ bgcolor: iColor + '20', color: iColor, fontWeight: 600, fontSize: '0.65rem', height: 18 }}
                    />
                  </Box>

                  {/* Purpose */}
                  <Typography variant="caption" color="text.secondary" display="block" sx={{ mb: 0.75 }}>
                    <strong>Purpose:</strong> {meta?.purpose ?? 'Validates API response assertions.'}
                  </Typography>

                  {/* Progress bar */}
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
                    <LinearProgress
                      variant="determinate"
                      value={v.pass_rate}
                      sx={{
                        flex: 1, height: 6, borderRadius: 3,
                        bgcolor: '#f0f0f0',
                        '& .MuiLinearProgress-bar': {
                          bgcolor: v.pass_rate >= 80 ? '#2e7d32' : v.pass_rate >= 50 ? '#e65100' : '#c62828',
                          borderRadius: 3,
                        },
                      }}
                    />
                    <Typography variant="caption" fontWeight={700} sx={{ minWidth: 36, textAlign: 'right' }}>
                      {v.pass_rate.toFixed(0)}%
                    </Typography>
                  </Box>

                  {/* Action */}
                  {!passing && meta?.action && (
                    <Typography variant="caption" sx={{ color: '#1a73e8' }}>
                      <strong>Action:</strong> {meta.action}
                    </Typography>
                  )}
                </Box>

                {/* Stats */}
                <Box sx={{ display: 'flex', gap: 2, flexShrink: 0 }}>
                  {[
                    { label: 'Total',  value: v.total,  color: 'text.primary' },
                    { label: 'Passed', value: v.passed, color: '#2e7d32' },
                    { label: 'Failed', value: v.failed, color: v.failed > 0 ? '#c62828' : 'text.secondary' },
                  ].map(({ label, value, color }) => (
                    <Box key={label} sx={{ textAlign: 'center' }}>
                      <Typography variant="caption" color="text.secondary" display="block">{label}</Typography>
                      <Typography variant="body2" fontWeight={700} sx={{ color }}>{value}</Typography>
                    </Box>
                  ))}
                  <Box sx={{ textAlign: 'center' }}>
                    <Typography variant="caption" color="text.secondary" display="block">Result</Typography>
                    <StatusChip value={v.pass_rate} />
                  </Box>
                </Box>
              </Box>
            </Box>
          );
        })}
      </Box>
    </Paper>
  );
}
