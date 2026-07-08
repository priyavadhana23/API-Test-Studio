// src/types/upload.ts
// Types for upload, execution, and job-polling workflows (Phase 9.6)

// ── Spec upload ────────────────────────────────────────────────────────────

export interface UploadResponse {
  status: string;
  filename: string;
  detected_format: string;
  file_size_bytes: number;
  upload_path: string;
}

export interface SpecSummary {
  filename: string;
  detected_format: string;
  file_size_bytes: number;
  upload_timestamp: string;
  supported: boolean;
}

export interface SpecListResponse {
  total: number;
  specifications: SpecSummary[];
}

// ── Execute request (POST /api/jobs) ──────────────────────────────────────

export interface ExecuteRequest {
  specification_filename: string;
  environment: string;
  base_url_override?: string;
  timeout_seconds: number;
  verify_ssl: boolean;
  generate_reports: boolean;
}

// ── Job status (GET /api/jobs/{job_id}) ───────────────────────────────────

export type JobStatus = 'pending' | 'running' | 'completed' | 'failed';

export interface JobStatusResponse {
  job_id: string;
  status: JobStatus;
  step: string;
  percent: number;
  run_id: string | null;
  report_paths: string[];
  error: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  elapsed_s: number | null;
  spec_filename: string;
  environment: string;
}

export interface JobSubmitResponse {
  job_id: string;
  status: string;
  poll_url: string;
  message: string;
}

// ── Upload workflow state machine ─────────────────────────────────────────

export type WorkflowPhase =
  | 'form'          // user filling in the form
  | 'uploading'     // file being sent to /api/specifications/upload
  | 'executing'     // job submitted, polling /api/jobs/{job_id}
  | 'completed'     // job status === 'completed'
  | 'failed';       // any error at any stage

// ── Environments (from environments.yaml, static for now) ─────────────────

export interface Environment {
  key: string;        // e.g. "development"
  label: string;      // e.g. "Development"
}
