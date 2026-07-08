// src/pages/UploadPage.tsx
// Upload + execute workflow. Phases: form → uploading → executing → completed | failed
import { useState, useRef, useCallback } from 'react';
import {
  Box, Typography, Paper, Button, Grid, TextField, MenuItem,
  Select, FormControl, InputLabel, FormGroup, FormControlLabel,
  Checkbox, Divider, Alert, Chip, IconButton, LinearProgress,
  Tooltip, Stack,
} from '@mui/material';
import CloudUploadIcon from '@mui/icons-material/CloudUpload';
import DeleteIcon from '@mui/icons-material/Delete';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import InsertDriveFileIcon from '@mui/icons-material/InsertDriveFile';
import specsService from '../services/specsService';
import jobsService from '../services/jobsService';
import runsService from '../services/runsService';
import ExecutionProgressScreen, { useJobPoller } from '../components/ExecutionProgressScreen';
import ExecutionCompleteScreen from '../components/ExecutionCompleteScreen';
import type { WorkflowPhase, JobStatusResponse, Environment } from '../types/upload';
import type { RunSummary } from '../types/api';

// ── Static environment list (from environments.yaml) ─────────────────────
const ENVIRONMENTS: Environment[] = [
  { key: 'development', label: 'Development' },
  { key: 'staging',     label: 'Staging' },
  { key: 'production',  label: 'Production' },
];

const ACCEPTED = '.json,.yaml,.yml';

function formatBytes(n: number) {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(2)} MB`;
}

// ── Execution options ─────────────────────────────────────────────────────
interface ExecOptions {
  generate_reports: boolean;
  verify_ssl: boolean;
  timeout_seconds: number;
}

export default function UploadPage() {
  // ── File selection ─────────────────────────────────────────────────
  const [file, setFile]           = useState<File | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // ── Form values ────────────────────────────────────────────────────
  const [environment, setEnvironment]       = useState('development');
  const [baseUrlOverride, setBaseUrlOverride] = useState('');
  const [execOptions, setExecOptions]       = useState<ExecOptions>({
    generate_reports: true,
    verify_ssl: true,
    timeout_seconds: 30,
  });

  // ── Workflow state ─────────────────────────────────────────────────
  const [phase, setPhase]               = useState<WorkflowPhase>('form');
  const [uploadPercent, setUploadPct]   = useState(0);
  const [jobId, setJobId]               = useState<string | null>(null);
  const [jobStatus, setJobStatus]       = useState<JobStatusResponse | null>(null);
  const [completedRun, setCompletedRun] = useState<RunSummary | null>(null);
  const [error, setError]               = useState<string | null>(null);

  // ── Polling ────────────────────────────────────────────────────────
  const handleJobUpdate = useCallback(async (status: JobStatusResponse) => {
    setJobStatus(status);
    if (status.status === 'completed') {
      setPhase('completed');
      // Load the run summary for the completion screen
      if (status.run_id) {
        try {
          const detail = await runsService.getRun(status.run_id);
          setCompletedRun(detail.run);
        } catch {
          // non-fatal — completion screen still shows job data
        }
      }
    } else if (status.status === 'failed') {
      setPhase('failed');
      setError(status.error ?? 'Pipeline execution failed.');
    }
  }, []);

  useJobPoller(
    phase === 'executing' ? jobId : null,
    handleJobUpdate,
    2500,
  );

  // ── File picker handlers ───────────────────────────────────────────
  function validateFile(f: File): string | null {
    const ext = f.name.split('.').pop()?.toLowerCase();
    if (!['json', 'yaml', 'yml'].includes(ext ?? '')) {
      return `Unsupported file type ".${ext}". Please select a .json, .yaml, or .yml file.`;
    }
    if (f.size === 0) return 'The selected file is empty.';
    if (f.size > 16 * 1024 * 1024) return 'File size exceeds 16 MB limit.';
    return null;
  }

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    setFileError(null);
    const selected = e.target.files?.[0] ?? null;
    if (!selected) return;
    const err = validateFile(selected);
    if (err) { setFileError(err); return; }
    setFile(selected);
  }

  function handleDrop(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setFileError(null);
    const dropped = e.dataTransfer.files[0];
    if (!dropped) return;
    const err = validateFile(dropped);
    if (err) { setFileError(err); return; }
    setFile(dropped);
  }

  function clearFile() {
    setFile(null);
    setFileError(null);
    if (inputRef.current) inputRef.current.value = '';
  }

  // ── Execute ────────────────────────────────────────────────────────
  async function handleExecute() {
    if (!file) { setFileError('Please select a specification file.'); return; }
    setError(null);
    setUploadPct(0);

    try {
      // Step 1 — Upload
      setPhase('uploading');
      const uploadResp = await specsService.upload(file, setUploadPct);

      // Step 2 — Submit async job
      setPhase('executing');
      const jobResp = await jobsService.submit({
        specification_filename: uploadResp.filename,
        environment,
        base_url_override: baseUrlOverride.trim() || undefined,
        timeout_seconds: execOptions.timeout_seconds,
        verify_ssl: execOptions.verify_ssl,
        generate_reports: execOptions.generate_reports,
      });
      setJobId(jobResp.job_id);
      // Polling starts automatically via useJobPoller
    } catch (err) {
      setPhase('failed');
      setError(err instanceof Error ? err.message : 'An unexpected error occurred.');
    }
  }

  // ── Reset to form ─────────────────────────────────────────────────
  function reset() {
    setPhase('form');
    setFile(null);
    setFileError(null);
    setJobId(null);
    setJobStatus(null);
    setCompletedRun(null);
    setError(null);
    setUploadPct(0);
    if (inputRef.current) inputRef.current.value = '';
  }

  // ── Render: progress / complete / failed ──────────────────────────
  if (phase === 'uploading' || phase === 'executing') {
    return (
      <>
        <Typography variant="h5" gutterBottom>Upload &amp; Execute</Typography>
        <ExecutionProgressScreen
          jobStatus={jobStatus}
          phase={phase}
          uploadPercent={uploadPercent}
        />
      </>
    );
  }

  if (phase === 'completed' && jobStatus) {
    return (
      <>
        <Typography variant="h5" gutterBottom>Upload &amp; Execute</Typography>
        <ExecutionCompleteScreen
          job={jobStatus}
          run={completedRun}
          onRunAnother={reset}
        />
      </>
    );
  }

  if (phase === 'failed') {
    return (
      <>
        <Typography variant="h5" gutterBottom>Upload &amp; Execute</Typography>
        <Box sx={{ maxWidth: 600, mx: 'auto', mt: 4 }}>
          <Alert
            severity="error"
            action={
              <Button color="inherit" size="small" onClick={reset}>
                Try Again
              </Button>
            }
            sx={{ mb: 2 }}
          >
            {error}
          </Alert>
        </Box>
      </>
    );
  }

  // ── Render: main form ─────────────────────────────────────────────
  return (
    <Box>
      <Typography variant="h5" gutterBottom>Upload &amp; Execute</Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
        Upload a Swagger / OpenAPI specification and run the full test pipeline.
      </Typography>

      <Grid container spacing={3} sx={{ maxWidth: 900 }}>
        {/* Left column — file + environment */}
        <Grid item xs={12} md={7}>
          {/* ── File drop zone ────────────────────────────────────── */}
          <Paper sx={{ p: 3, mb: 3 }}>
            <Typography variant="subtitle1" gutterBottom>Specification File</Typography>
            <Divider sx={{ mb: 2 }} />

            {/* Hidden input */}
            <input
              ref={inputRef}
              type="file"
              accept={ACCEPTED}
              style={{ display: 'none' }}
              onChange={handleFileChange}
            />

            {!file ? (
              <Box
                onDragOver={(e) => e.preventDefault()}
                onDrop={handleDrop}
                onClick={() => inputRef.current?.click()}
                sx={{
                  border: '2px dashed',
                  borderColor: fileError ? 'error.main' : 'divider',
                  borderRadius: 2,
                  p: 5,
                  textAlign: 'center',
                  cursor: 'pointer',
                  transition: 'border-color 0.2s, background 0.2s',
                  '&:hover': { borderColor: 'primary.main', bgcolor: 'primary.main' + '08' },
                }}
              >
                <CloudUploadIcon sx={{ fontSize: 48, color: 'text.disabled', mb: 1 }} />
                <Typography variant="body1" fontWeight={500}>
                  Click to browse or drag &amp; drop
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  Accepted formats: .json, .yaml, .yml &nbsp;·&nbsp; Max 16 MB
                </Typography>
                {fileError && (
                  <Typography variant="caption" color="error" display="block" sx={{ mt: 1 }}>
                    {fileError}
                  </Typography>
                )}
              </Box>
            ) : (
              <Box
                sx={{
                  display: 'flex', alignItems: 'center', gap: 2,
                  p: 2, bgcolor: '#f0f7ff', borderRadius: 2,
                  border: '1px solid', borderColor: 'primary.light',
                }}
              >
                <InsertDriveFileIcon sx={{ color: 'primary.main', fontSize: 36 }} />
                <Box sx={{ flex: 1, minWidth: 0 }}>
                  <Typography variant="body2" fontWeight={600} noWrap>{file.name}</Typography>
                  <Typography variant="caption" color="text.secondary">
                    {formatBytes(file.size)} &nbsp;·&nbsp;
                    {file.name.split('.').pop()?.toUpperCase()}
                  </Typography>
                </Box>
                <Chip label="Ready" color="success" size="small" />
                <Tooltip title="Remove file">
                  <IconButton size="small" onClick={clearFile}>
                    <DeleteIcon fontSize="small" />
                  </IconButton>
                </Tooltip>
              </Box>
            )}
          </Paper>

          {/* ── Environment selection ─────────────────────────────── */}
          <Paper sx={{ p: 3, mb: 3 }}>
            <Typography variant="subtitle1" gutterBottom>Environment</Typography>
            <Divider sx={{ mb: 2 }} />
            <FormControl fullWidth size="small" sx={{ mb: 2 }}>
              <InputLabel>Environment</InputLabel>
              <Select
                value={environment}
                label="Environment"
                onChange={(e) => setEnvironment(e.target.value)}
              >
                {ENVIRONMENTS.map((env) => (
                  <MenuItem key={env.key} value={env.key}>
                    {env.label}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            <TextField
              fullWidth
              size="small"
              label="Base URL Override (optional)"
              placeholder="e.g. https://httpbin.org"
              value={baseUrlOverride}
              onChange={(e) => setBaseUrlOverride(e.target.value)}
              helperText="Overrides the environment base URL for this run only."
            />
          </Paper>
        </Grid>

        {/* Right column — execution options */}
        <Grid item xs={12} md={5}>
          <Paper sx={{ p: 3, mb: 3 }}>
            <Typography variant="subtitle1" gutterBottom>Execution Options</Typography>
            <Divider sx={{ mb: 2 }} />
            <FormGroup>
              {[
                { label: 'Generate Test Cases',   checked: true,  disabled: true, tooltip: 'Always enabled' },
                { label: 'Execute Tests',          checked: true,  disabled: true, tooltip: 'Always enabled' },
                { label: 'Validate Responses',     checked: true,  disabled: true, tooltip: 'Always enabled' },
                { label: 'Persist Results',        checked: true,  disabled: true, tooltip: 'Always enabled' },
              ].map(({ label, checked, disabled, tooltip }) => (
                <Tooltip key={label} title={tooltip} placement="right">
                  <FormControlLabel
                    control={<Checkbox checked={checked} disabled={disabled} size="small" />}
                    label={<Typography variant="body2">{label}</Typography>}
                  />
                </Tooltip>
              ))}
              <FormControlLabel
                control={
                  <Checkbox
                    checked={execOptions.generate_reports}
                    size="small"
                    onChange={(e) =>
                      setExecOptions((o) => ({ ...o, generate_reports: e.target.checked }))
                    }
                  />
                }
                label={<Typography variant="body2">Generate Reports</Typography>}
              />
              <FormControlLabel
                control={
                  <Checkbox
                    checked={execOptions.verify_ssl}
                    size="small"
                    onChange={(e) =>
                      setExecOptions((o) => ({ ...o, verify_ssl: e.target.checked }))
                    }
                  />
                }
                label={<Typography variant="body2">Verify SSL Certificates</Typography>}
              />
            </FormGroup>

            <Divider sx={{ my: 2 }} />

            <TextField
              fullWidth
              size="small"
              type="number"
              label="Timeout (seconds)"
              value={execOptions.timeout_seconds}
              onChange={(e) => {
                const v = Math.max(1, Math.min(300, parseInt(e.target.value, 10) || 30));
                setExecOptions((o) => ({ ...o, timeout_seconds: v }));
              }}
              inputProps={{ min: 1, max: 300 }}
              helperText="Per-request HTTP timeout (1–300 s)"
            />
          </Paper>

          {/* Summary before executing */}
          {file && (
            <Paper sx={{ p: 2.5, mb: 3, bgcolor: '#f8f9fa' }}>
              <Typography variant="caption" color="text.secondary" fontWeight={600} display="block" gutterBottom>
                READY TO EXECUTE
              </Typography>
              <Stack spacing={0.5}>
                {[
                  ['File',        file.name],
                  ['Environment', ENVIRONMENTS.find(e => e.key === environment)?.label ?? environment],
                  ['Timeout',     `${execOptions.timeout_seconds} s`],
                  ['Reports',     execOptions.generate_reports ? 'Yes' : 'No'],
                ].map(([label, val]) => (
                  <Box key={label} sx={{ display: 'flex', justifyContent: 'space-between' }}>
                    <Typography variant="caption" color="text.secondary">{label}</Typography>
                    <Typography variant="caption" fontWeight={600}>{val}</Typography>
                  </Box>
                ))}
              </Stack>
            </Paper>
          )}

          <Button
            variant="contained"
            size="large"
            fullWidth
            startIcon={<PlayArrowIcon />}
            onClick={handleExecute}
            disabled={!file}
            sx={{ py: 1.5, fontWeight: 700, fontSize: '1rem' }}
          >
            Execute Pipeline
          </Button>
        </Grid>
      </Grid>
    </Box>
  );
}
