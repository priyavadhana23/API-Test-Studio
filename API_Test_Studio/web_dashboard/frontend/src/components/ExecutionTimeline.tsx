/**
 * ExecutionTimeline
 * Visual representation of pipeline stages that completed for this run.
 */
import { Box, Paper, Typography } from '@mui/material';
import TimelineIcon from '@mui/icons-material/Timeline';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import type { RunSummary } from '../types/api';

interface Stage {
  label:       string;
  sublabel:    string;
  completed:   boolean;
}

interface Props {
  run: RunSummary;
  hasAnalytics: boolean;
  hasReports:   boolean;
}

export default function ExecutionTimeline({ run, hasAnalytics, hasReports }: Props) {
  const stages: Stage[] = [
    {
      label:     'Specification Uploaded',
      sublabel:  run.specification_file ?? 'API spec file',
      completed: true,
    },
    {
      label:     'Parser Completed',
      sublabel:  `${run.total_endpoints} endpoint${run.total_endpoints !== 1 ? 's' : ''} discovered`,
      completed: run.total_endpoints > 0,
    },
    {
      label:     'Test Cases Generated',
      sublabel:  `${run.total_test_cases} test cases created`,
      completed: run.total_test_cases > 0,
    },
    {
      label:     'API Execution Completed',
      sublabel:  `${run.total_executed} requests sent`,
      completed: run.total_executed > 0,
    },
    {
      label:     'Validation Completed',
      sublabel:  `${run.passed} passed · ${run.failed} failed · ${run.errors} errors`,
      completed: run.total_executed > 0,
    },
    {
      label:     'Results Persisted',
      sublabel:  `Run ID ${run.run_id.slice(0, 12)}…`,
      completed: true,
    },
    {
      label:     'Analytics Generated',
      sublabel:  `Health score computed`,
      completed: hasAnalytics,
    },
    {
      label:     'Reports Generated',
      sublabel:  hasReports ? 'HTML, PDF, CSV, JSON available' : 'Skipped',
      completed: hasReports,
    },
  ];

  return (
    <Paper elevation={0} sx={{ borderRadius: 3, border: '1px solid #e8eaed', overflow: 'hidden', mb: 3 }}>
      <Box sx={{ px: 3, py: 2, bgcolor: '#f8f9fa', borderBottom: '1px solid #e8eaed', display: 'flex', alignItems: 'center', gap: 1.5 }}>
        <TimelineIcon sx={{ color: '#1a73e8' }} />
        <Box>
          <Typography variant="subtitle1" fontWeight={700}>Execution Timeline</Typography>
          <Typography variant="caption" color="text.secondary">Pipeline stages completed for this run</Typography>
        </Box>
      </Box>

      <Box sx={{ px: 3, py: 2.5 }}>
        {stages.map((stage, i) => (
          <Box key={stage.label} sx={{ display: 'flex', alignItems: 'flex-start', gap: 2, mb: i < stages.length - 1 ? 0 : 0 }}>
            {/* Left: icon + connector */}
            <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', flexShrink: 0 }}>
              <CheckCircleIcon
                sx={{
                  fontSize: 22,
                  color: stage.completed ? '#2e7d32' : '#e0e0e0',
                  bgcolor: '#fff',
                  borderRadius: '50%',
                }}
              />
              {i < stages.length - 1 && (
                <Box sx={{ width: 2, flex: 1, bgcolor: stage.completed ? '#2e7d3266' : '#e0e0e0', minHeight: 28, my: 0.25 }} />
              )}
            </Box>
            {/* Right: text */}
            <Box sx={{ pb: i < stages.length - 1 ? 1 : 0 }}>
              <Typography
                variant="body2"
                fontWeight={600}
                sx={{ color: stage.completed ? 'text.primary' : 'text.disabled' }}
              >
                {stage.label}
              </Typography>
              <Typography
                variant="caption"
                sx={{ color: stage.completed ? 'text.secondary' : 'text.disabled' }}
              >
                {stage.sublabel}
              </Typography>
            </Box>
          </Box>
        ))}
      </Box>
    </Paper>
  );
}
