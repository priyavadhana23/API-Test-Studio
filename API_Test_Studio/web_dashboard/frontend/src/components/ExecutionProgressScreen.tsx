// src/components/ExecutionProgressScreen.tsx
// Shown while the job is pending / running. Polls /api/jobs/{job_id}.
import { useEffect, useRef, useCallback } from 'react';
import {
  Box, Typography, LinearProgress, CircularProgress,
  Paper, Chip, Stepper, Step, StepLabel, StepContent,
} from '@mui/material';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import type { JobStatusResponse } from '../types/upload';

// The ordered pipeline stages displayed to the user.
const STAGES = [
  { step: 'Uploading',              match: (s: string) => s.toLowerCase().includes('upload') },
  { step: 'Loading configuration',  match: (s: string) => s.toLowerCase().includes('config') },
  { step: 'Parsing API specification', match: (s: string) => s.toLowerCase().includes('pars') },
  { step: 'Generating test cases',  match: (s: string) => s.toLowerCase().includes('generat') },
  { step: 'Executing HTTP requests',match: (s: string) => s.toLowerCase().includes('execut') },
  { step: 'Validating responses',   match: (s: string) => s.toLowerCase().includes('valid') },
  { step: 'Persisting results',     match: (s: string) => s.toLowerCase().includes('persist') },
  { step: 'Running analytics',      match: (s: string) => s.toLowerCase().includes('analytic') },
  { step: 'Generating reports',     match: (s: string) => s.toLowerCase().includes('report') },
  { step: 'Completed',              match: (s: string) => s.toLowerCase().includes('done') || s.toLowerCase().includes('complet') },
];

function activeStageIndex(step: string): number {
  const idx = STAGES.findIndex(s => s.match(step));
  return idx >= 0 ? idx : 0;
}

interface Props {
  jobStatus: JobStatusResponse | null;
  phase: 'uploading' | 'executing';
  uploadPercent: number;
}

export default function ExecutionProgressScreen({ jobStatus, phase, uploadPercent }: Props) {
  const currentStep = phase === 'uploading' ? 'Uploading' : (jobStatus?.step ?? 'Starting pipeline');
  const percent     = phase === 'uploading' ? uploadPercent : (jobStatus?.percent ?? 0);
  const activeIdx   = phase === 'uploading' ? 0 : activeStageIndex(currentStep);

  return (
    <Box sx={{ maxWidth: 600, mx: 'auto', mt: 4 }}>
      <Paper sx={{ p: 4, borderRadius: 3 }}>
        {/* Header */}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 3 }}>
          <CircularProgress size={32} thickness={4} />
          <Box>
            <Typography variant="h6">Running Pipeline</Typography>
            <Typography variant="body2" color="text.secondary">
              {jobStatus
                ? `Job ${jobStatus.job_id.slice(0, 8)}… — ${jobStatus.environment}`
                : 'Preparing…'}
            </Typography>
          </Box>
          <Chip
            label={`${percent}%`}
            color="primary"
            size="small"
            sx={{ ml: 'auto', fontWeight: 700 }}
          />
        </Box>

        {/* Overall progress bar */}
        <LinearProgress
          variant="determinate"
          value={percent}
          sx={{ height: 8, borderRadius: 4, mb: 3 }}
        />

        {/* Stage stepper */}
        <Stepper activeStep={activeIdx} orientation="vertical" nonLinear>
          {STAGES.map((stage, idx) => {
            const done = idx < activeIdx;
            const active = idx === activeIdx;
            return (
              <Step key={stage.step} completed={done}>
                <StepLabel
                  StepIconComponent={done ? () => (
                    <CheckCircleIcon sx={{ color: 'success.main', fontSize: 20 }} />
                  ) : undefined}
                  sx={{
                    '& .MuiStepLabel-label': {
                      fontWeight: active ? 700 : 400,
                      color: active ? 'primary.main' : done ? 'text.secondary' : 'text.disabled',
                    },
                  }}
                >
                  {stage.step}
                </StepLabel>
                {active && (
                  <StepContent>
                    <Typography variant="caption" color="text.secondary">
                      {currentStep}
                    </Typography>
                  </StepContent>
                )}
              </Step>
            );
          })}
        </Stepper>

        {/* Elapsed time */}
        {jobStatus?.started_at && (
          <Typography variant="caption" color="text.disabled" sx={{ display: 'block', mt: 2, textAlign: 'right' }}>
            Started {new Date(jobStatus.started_at).toLocaleTimeString()}
          </Typography>
        )}
      </Paper>
    </Box>
  );
}

// ── Polling hook ──────────────────────────────────────────────────────────

export function useJobPoller(
  jobId: string | null,
  onUpdate: (status: JobStatusResponse) => void,
  intervalMs = 2500,
) {
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stop = useCallback(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  useEffect(() => {
    if (!jobId) return;
    import('../services/jobsService').then(({ default: jobsService }) => {
      const poll = async () => {
        try {
          const status = await jobsService.getStatus(jobId);
          onUpdate(status);
          if (status.status === 'completed' || status.status === 'failed') {
            stop();
          }
        } catch {
          // swallow transient network errors; let the component handle state
        }
      };
      poll(); // immediate first poll
      timerRef.current = setInterval(poll, intervalMs);
    });
    return stop;
  }, [jobId, intervalMs, onUpdate, stop]);

  return stop;
}
