/**
 * DeveloperDiagnostics
 * Answers developer questions: "Which endpoint failed? Why? What do I fix first?"
 * Groups failures by endpoint with validator status per endpoint.
 */
import { useState } from 'react';
import {
  Box, Paper, Typography, Chip, Grid, Collapse, IconButton,
  Table, TableBody, TableCell, TableRow,
} from '@mui/material';
import CodeIcon from '@mui/icons-material/Code';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import CancelIcon from '@mui/icons-material/Cancel';
import type { EndpointStats, ValidatorStat, FailureAnalysis } from '../types/api';
import { passRateColor, priorityColor } from '../utils/colors';

interface Props {
  endpointStats: EndpointStats[];
  validators?: ValidatorStat[];
  fa?: FailureAnalysis | null;
}

const VALIDATOR_PURPOSES: Record<string, string> = {
  StatusCodeValidator:    'HTTP status code matches expected',
  HeaderValidator:        'Required response headers present',
  ResponseTimeValidator:  'Response time within threshold',
  JsonValidator:          'Response body is valid JSON',
  JsonSchemaValidator:    'Response matches OpenAPI schema',
  ExactResponseValidator: 'Response values match expectations',
  BusinessRuleValidator:  'Business rules satisfied',
};

function endpointPriority(s: EndpointStats): string {
  if (s.pass_rate < 20) return 'Critical';
  if (s.pass_rate < 50) return 'High';
  if (s.pass_rate < 80) return 'Medium';
  return 'Low';
}

function mostCommonFailure(s: EndpointStats, fa: FailureAnalysis | null | undefined): string {
  if (!fa || fa.distribution.length === 0) {
    if (s.errors > s.failed) return 'Connectivity or authentication failure';
    if (s.pass_rate < 30)    return 'Schema mismatch — response structure incorrect';
    return 'Validation assertion failure';
  }
  const top = [...fa.distribution].sort((a, b) => b.count - a.count)[0];
  return top?.sample_message ?? top?.category ?? 'Multiple validation failures';
}

function recommendedAction(s: EndpointStats): string {
  if (s.errors > s.failed)   return `Verify connectivity and authentication for ${s.method} ${s.endpoint}.`;
  if (s.pass_rate === 0)     return `Endpoint ${s.method} ${s.endpoint} returned no valid responses — check implementation.`;
  if (s.pass_rate < 30)      return `Review ${s.method} ${s.endpoint} response schema against OpenAPI specification.`;
  if (s.pass_rate < 80)      return `Investigate failing test categories for ${s.method} ${s.endpoint} — run targeted negative tests.`;
  return `${s.method} ${s.endpoint} is mostly passing — monitor for regressions.`;
}

interface DiagCardProps {
  stat: EndpointStats;
  validators?: ValidatorStat[];
  fa?: FailureAnalysis | null;
  rank: number;
}

function DiagCard({ stat, validators, fa, rank }: DiagCardProps) {
  const [expanded, setExpanded] = useState(rank <= 1); // auto-expand worst
  const priority = endpointPriority(stat);
  const pColor   = priorityColor(priority);
  const failMsg  = mostCommonFailure(stat, fa);
  const action   = recommendedAction(stat);

  return (
    <Paper
      elevation={0}
      sx={{ border: '1px solid #e8eaed', borderRadius: 2, mb: 1.5, overflow: 'hidden' }}
    >
      {/* Header row */}
      <Box
        sx={{
          display: 'flex', alignItems: 'center', gap: 1.5, px: 2, py: 1.5,
          bgcolor: rank === 0 ? '#fff8f0' : '#fafafa',
          cursor: 'pointer',
          borderLeft: `4px solid ${pColor}`,
          '&:hover': { bgcolor: '#f5f5f5' },
        }}
        onClick={() => setExpanded(!expanded)}
      >
        <Chip
          label={priority}
          size="small"
          sx={{ bgcolor: pColor, color: '#fff', fontWeight: 700, fontSize: '0.68rem', flexShrink: 0 }}
        />
        <Chip
          label={stat.method}
          size="small"
          variant="outlined"
          sx={{ fontFamily: 'monospace', fontWeight: 700, fontSize: '0.7rem', flexShrink: 0 }}
        />
        <Typography
          variant="body2"
          fontWeight={600}
          sx={{ fontFamily: 'monospace', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
          title={stat.endpoint}
        >
          {stat.endpoint}
        </Typography>
        <Box sx={{ display: 'flex', gap: 2, flexShrink: 0 }}>
          <Box sx={{ textAlign: 'right' }}>
            <Typography variant="caption" color="text.secondary">Pass Rate</Typography>
            <Typography variant="body2" fontWeight={700} sx={{ color: passRateColor(stat.pass_rate) }}>
              {stat.pass_rate.toFixed(0)}%
            </Typography>
          </Box>
          <Box sx={{ textAlign: 'right' }}>
            <Typography variant="caption" color="text.secondary">Failures</Typography>
            <Typography variant="body2" fontWeight={700} sx={{ color: stat.failed > 0 ? '#e65100' : 'text.primary' }}>
              {stat.failed}
            </Typography>
          </Box>
        </Box>
        <IconButton size="small">
          {expanded ? <ExpandLessIcon fontSize="small" /> : <ExpandMoreIcon fontSize="small" />}
        </IconButton>
      </Box>

      {/* Detail */}
      <Collapse in={expanded}>
        <Box sx={{ px: 2.5, py: 2, borderTop: '1px solid #f0f0f0' }}>
          <Grid container spacing={2}>
            {/* Validator status */}
            <Grid item xs={12} md={5}>
              <Typography variant="caption" color="text.secondary" fontWeight={700} display="block" sx={{ mb: 1 }}>
                VALIDATOR STATUS
              </Typography>
              {validators && validators.length > 0 ? (
                <Table size="small" sx={{ '& td': { border: 0, py: 0.25 } }}>
                  <TableBody>
                    {validators.map((v) => (
                      <TableRow key={v.validator_name}>
                        <TableCell sx={{ width: 24, pr: 0.5 }}>
                          {v.failed === 0
                            ? <CheckCircleIcon sx={{ color: '#2e7d32', fontSize: 16 }} />
                            : <CancelIcon sx={{ color: '#c62828', fontSize: 16 }} />}
                        </TableCell>
                        <TableCell>
                          <Typography variant="caption">
                            {v.validator_name.replace('Validator', '')}
                          </Typography>
                        </TableCell>
                        <TableCell>
                          <Typography variant="caption" color="text.secondary">
                            {VALIDATOR_PURPOSES[v.validator_name] ?? ''}
                          </Typography>
                        </TableCell>
                        <TableCell align="right">
                          <Chip
                            label={v.failed === 0 ? 'PASSED' : 'FAILED'}
                            size="small"
                            sx={{
                              fontSize: '0.62rem',
                              height: 18,
                              bgcolor: v.failed === 0 ? '#e8f5e9' : '#fce4e4',
                              color:   v.failed === 0 ? '#2e7d32' : '#c62828',
                              fontWeight: 700,
                            }}
                          />
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              ) : (
                <Typography variant="caption" color="text.disabled">Validator details not available</Typography>
              )}
            </Grid>

            {/* Diagnostics */}
            <Grid item xs={12} md={7}>
              <Typography variant="caption" color="text.secondary" fontWeight={700} display="block" sx={{ mb: 1 }}>
                DIAGNOSTICS
              </Typography>
              {[
                { label: 'Most Common Failure', value: failMsg },
                { label: 'Recommended Action',  value: action,  highlight: '#1a73e8' },
                { label: 'Total Executions',     value: stat.total_executions },
                { label: 'Execution Errors',     value: stat.errors, highlight: stat.errors > 0 ? '#c62828' : undefined },
                { label: 'Avg Response Time',    value: stat.avg_response_time_ms != null ? `${stat.avg_response_time_ms.toFixed(0)} ms` : '—' },
              ].map(({ label, value, highlight }) => (
                <Box key={label} sx={{ display: 'flex', gap: 1, mb: 0.5 }}>
                  <Typography variant="caption" color="text.secondary" sx={{ minWidth: 160, flexShrink: 0 }}>{label}:</Typography>
                  <Typography variant="caption" fontWeight={600} sx={{ color: highlight ?? 'text.primary' }}>{value}</Typography>
                </Box>
              ))}
            </Grid>
          </Grid>
        </Box>
      </Collapse>
    </Paper>
  );
}

export default function DeveloperDiagnostics({ endpointStats, validators, fa }: Props) {
  // Sort by worst first
  const sorted = [...endpointStats].sort((a, b) => a.pass_rate - b.pass_rate).slice(0, 12);
  if (sorted.length === 0) return null;

  return (
    <Paper elevation={0} sx={{ borderRadius: 3, border: '1px solid #e8eaed', overflow: 'hidden', mb: 3 }}>
      <Box sx={{ px: 3, py: 2, bgcolor: '#f8f9fa', borderBottom: '1px solid #e8eaed', display: 'flex', alignItems: 'center', gap: 1.5 }}>
        <CodeIcon sx={{ color: '#1a73e8' }} />
        <Box>
          <Typography variant="subtitle1" fontWeight={700}>Developer Diagnostics</Typography>
          <Typography variant="caption" color="text.secondary">
            Endpoints grouped by failure severity — worst first
          </Typography>
        </Box>
      </Box>
      <Box sx={{ p: 2.5 }}>
        {sorted.map((s, i) => (
          <DiagCard key={`${s.method}-${s.endpoint}`} stat={s} validators={validators} fa={fa} rank={i} />
        ))}
      </Box>
    </Paper>
  );
}
