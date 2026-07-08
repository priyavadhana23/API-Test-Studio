// src/types/api.ts
// TypeScript interfaces that mirror the FastAPI backend Pydantic schemas exactly.
// Do NOT add computed fields here — all values come from the API.

// ─────────────────────────────────────────────
// Health
// ─────────────────────────────────────────────

export interface ComponentStatus {
  available: boolean;
  detail: string;
}

export interface HealthResponse {
  status: string;
  framework_name: string;
  framework_version: string;
  database: ComponentStatus;
  analytics: ComponentStatus;
  reporting: ComponentStatus;
}

// ─────────────────────────────────────────────
// Runs
// ─────────────────────────────────────────────

export interface RunSummary {
  run_id: string;
  api_name: string;
  api_version: string | null;
  environment: string | null;
  execution_timestamp: string | null;
  total_endpoints: number;
  total_test_cases: number;
  total_executed: number;
  passed: number;
  failed: number;
  skipped: number;
  errors: number;
  pass_percentage: number;
  avg_response_time_ms: number | null;
  total_execution_time_s: number | null;
  health_score: number | null;
  health_rating: string | null;
  specification_file: string | null;
  framework_version: string | null;
}

export interface RunListResponse {
  total: number;
  page: number;
  page_size: number;
  has_next: boolean;
  runs: RunSummary[];
}

export interface ValidatorStat {
  validator_name: string;
  passed: number;
  failed: number;
  total: number;
  pass_rate: number;
}

export interface ValidationSummary {
  validators: ValidatorStat[];
  total_assertions: number;
  total_passed: number;
  total_failed: number;
}

export interface RunDetailResponse {
  run: RunSummary;
  validation_summary: ValidationSummary | null;
  report_links: string[];
}

// ─────────────────────────────────────────────
// Analytics
// ─────────────────────────────────────────────

export interface TrendPoint {
  label: string;
  value: number;
  run_count: number;
}

export interface TrendResult {
  name: string;
  points: TrendPoint[];
  slope: number;
  direction: string;
  moving_avg: number[];
}

export interface EndpointStats {
  endpoint: string;
  method: string;
  total_executions: number;
  passed: number;
  failed: number;
  errors: number;
  pass_rate: number;
  avg_response_time_ms: number | null;
  min_response_time_ms: number | null;
  max_response_time_ms: number | null;
  p95_response_time_ms: number | null;
}

export interface EndpointAnalysis {
  most_executed: string | null;
  least_executed: string | null;
  most_failed: string | null;
  most_successful: string | null;
  slowest: string | null;
  fastest: string | null;
  avg_execution_count: number;
  all_stats: EndpointStats[];
}

export interface ResponseTimeStats {
  sample_count: number;
  mean_ms: number | null;
  median_ms: number | null;
  min_ms: number | null;
  max_ms: number | null;
  std_dev_ms: number | null;
  p95_ms: number | null;
  p99_ms: number | null;
  sla_threshold_ms: number;
  sla_compliance_pct: number;
}

export interface FailureEntry {
  category: string;
  count: number;
  percentage: number;
  sample_message: string | null;
}

export interface FailureAnalysis {
  total_failures: number;
  validation_failures: number;
  execution_errors: number;
  timeout_failures: number;
  auth_failures: number;
  schema_failures: number;
  business_rule_failures: number;
  top_failures: FailureEntry[];
  distribution: FailureEntry[];
}

export interface RegressionSummary {
  run_id_baseline: string;
  run_id_current: string;
  api_name: string;
  new_failures: string[];
  fixed_failures: string[];
  unchanged_failures: string[];
  pass_rate_delta: number;
  avg_rt_delta_ms: number | null;
  has_regression: boolean;
  verdict: string;
}

export interface HealthScore {
  score: number;
  rating: string;
  pass_rate_score: number;
  response_time_score: number;
  stability_score: number;
  availability_score: number;
  recommendations: string[];
}

export interface AnalyticsSummary {
  run_id: string;
  api_name: string;
  total_runs: number;
  generated_at: string;
  trend: TrendResult | null;
  endpoint_analysis: EndpointAnalysis | null;
  response_time: ResponseTimeStats | null;
  failure_analysis: FailureAnalysis | null;
  regression: RegressionSummary | null;
  health: HealthScore | null;
}

// ─────────────────────────────────────────────
// Results
// ─────────────────────────────────────────────

export interface EndpointSummaryRow {
  endpoint: string;
  http_method: string;
  total: number;
  passed: number;
  failed: number;
  skipped: number;
  errors: number;
  pass_rate: number;
  avg_response_time_ms: number | null;
}

export interface CategorySummaryRow {
  category: string;
  total: number;
  passed: number;
  failed: number;
  pass_rate: number;
}

export interface ResultsSummary {
  run_id: string;
  total_results: number;
  passed: number;
  failed: number;
  skipped: number;
  errors: number;
  pass_rate: number;
  by_endpoint: EndpointSummaryRow[];
  by_category: CategorySummaryRow[];
  by_status: Record<string, number>;
  by_http_method: Record<string, number>;
}
