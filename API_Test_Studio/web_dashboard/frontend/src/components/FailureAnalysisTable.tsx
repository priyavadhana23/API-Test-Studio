/**
 * FailureAnalysisTable
 * Structured failure breakdown with count, percentage, priority, and likely cause.
 * Replaces the chart-only view with an actionable table.
 */
import { Box, Paper, Typography, Chip, Table, TableBody, TableCell, TableHead, TableRow, TableContainer } from '@mui/material';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline';
import type { FailureEntry } from '../types/api';
import { priorityColor } from '../utils/colors';

interface Props {
  distribution: FailureEntry[];
  totalFailures: number;
}

const CATEGORY_META: Record<string, { priority: string; cause: string }> = {
  schema_validation:  { priority: 'High',     cause: 'API response structure does not match the OpenAPI schema' },
  schema:             { priority: 'High',     cause: 'API response structure does not match the OpenAPI schema' },
  status_code:        { priority: 'Medium',   cause: 'API returned an unexpected HTTP status code' },
  authentication:     { priority: 'Critical', cause: 'Invalid or expired authentication credentials' },
  auth:               { priority: 'Critical', cause: 'Invalid or expired authentication credentials' },
  timeout:            { priority: 'High',     cause: 'API response exceeded the configured timeout threshold' },
  header:             { priority: 'Medium',   cause: 'Required response headers are missing or incorrect' },
  json:               { priority: 'Medium',   cause: 'Response body is not valid JSON or missing required fields' },
  business_rule:      { priority: 'High',     cause: 'Business rule constraint not satisfied by API response' },
  execution_error:    { priority: 'Critical', cause: 'Could not reach the API — check connectivity and configuration' },
  exact_match:        { priority: 'Low',      cause: 'Response field values do not match expected values' },
};

function getMeta(category: string): { priority: string; cause: string } {
  const lower = category.toLowerCase().replace(/[^a-z_]/g, '_');
  return (
    CATEGORY_META[lower] ??
    CATEGORY_META[lower.split('_')[0]] ??
    { priority: 'Medium', cause: 'Validation assertion not satisfied' }
  );
}

function formatCategory(cat: string): string {
  return cat
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

export default function FailureAnalysisTable({ distribution, totalFailures }: Props) {
  if (distribution.length === 0) return null;
  const sorted = [...distribution].sort((a, b) => b.count - a.count);

  return (
    <Paper elevation={0} sx={{ borderRadius: 3, border: '1px solid #e8eaed', overflow: 'hidden', mb: 3 }}>
      <Box sx={{ px: 3, py: 2, bgcolor: '#fff8f0', borderBottom: '1px solid #e8eaed', display: 'flex', alignItems: 'center', gap: 1.5 }}>
        <ErrorOutlineIcon sx={{ color: '#e65100' }} />
        <Box>
          <Typography variant="subtitle1" fontWeight={700}>Failure Analysis</Typography>
          <Typography variant="caption" color="text.secondary">
            {totalFailures} total failures — by category with priority and likely cause
          </Typography>
        </Box>
      </Box>

      <TableContainer>
        <Table size="small">
          <TableHead>
            <TableRow sx={{ '& th': { fontWeight: 700, bgcolor: '#f8f9fa', fontSize: '0.75rem' } }}>
              <TableCell>Failure Type</TableCell>
              <TableCell align="right">Count</TableCell>
              <TableCell align="right">%</TableCell>
              <TableCell align="center">Priority</TableCell>
              <TableCell>Likely Cause</TableCell>
              <TableCell sx={{ minWidth: 180 }}>Sample Message</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {sorted.map((entry) => {
              const meta   = getMeta(entry.category);
              const pColor = priorityColor(meta.priority);
              return (
                <TableRow key={entry.category} hover>
                  <TableCell sx={{ fontWeight: 600, fontSize: '0.82rem' }}>
                    {formatCategory(entry.category)}
                  </TableCell>
                  <TableCell align="right" sx={{ fontWeight: 700 }}>
                    {entry.count}
                  </TableCell>
                  <TableCell align="right">
                    <Typography variant="body2" sx={{ color: entry.percentage >= 30 ? '#e65100' : 'text.primary' }}>
                      {entry.percentage.toFixed(1)}%
                    </Typography>
                  </TableCell>
                  <TableCell align="center">
                    <Chip
                      label={meta.priority}
                      size="small"
                      sx={{ bgcolor: pColor, color: '#fff', fontWeight: 700, fontSize: '0.65rem', height: 20 }}
                    />
                  </TableCell>
                  <TableCell sx={{ fontSize: '0.78rem', color: 'text.secondary', maxWidth: 220 }}>
                    {meta.cause}
                  </TableCell>
                  <TableCell sx={{ fontSize: '0.73rem', color: 'text.disabled', maxWidth: 200 }}>
                    <Box sx={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={entry.sample_message ?? ''}>
                      {entry.sample_message ?? '—'}
                    </Box>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </TableContainer>
    </Paper>
  );
}
