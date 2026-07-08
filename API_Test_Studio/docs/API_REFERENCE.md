# API Reference — API Test Studio

Base URL: `http://localhost:8000`  
Interactive docs: [http://localhost:8000/docs](http://localhost:8000/docs)  
OpenAPI schema: [http://localhost:8000/openapi.json](http://localhost:8000/openapi.json)

All responses are JSON. All request bodies are JSON unless noted. Timestamps are ISO-8601 UTC.

---

## Table of Contents

- [Health](#health)
- [Specifications](#specifications)
- [Async Jobs](#async-jobs)
- [Runs (Synchronous)](#runs-synchronous)
- [Results](#results)
- [Analytics](#analytics)
- [Reports](#reports)
- [Status Codes](#status-codes)

---

## Health

### `GET /`

Service identity.

**Response 200**
```json
{
  "name": "API Test Studio",
  "version": "1.0.0",
  "status": "running",
  "docs_url": "http://localhost:8000/docs"
}
```

---

### `GET /api/health`

Component health probe. Used by Docker healthcheck.

**Response 200**
```json
{
  "status": "healthy",
  "framework_name": "API Test Studio",
  "framework_version": "1.0.0",
  "database": {
    "available": true,
    "detail": "Connected — api_test_studio.db (34176 KB)"
  },
  "analytics": {
    "available": true,
    "detail": "AnalyticsManager ready"
  },
  "reporting": {
    "available": true,
    "detail": "ReportManager ready"
  }
}
```

---

## Specifications

### `POST /api/specifications/upload`

Upload a Swagger or OpenAPI specification file.

**Content-Type:** `multipart/form-data`  
**Form field:** `file` (the spec file, `.json` / `.yaml` / `.yml`)

```bash
curl -X POST http://localhost:8000/api/specifications/upload \
  -F "file=@petstore.yaml"
```

**Response 201**
```json
{
  "status": "uploaded",
  "filename": "petstore.yaml",
  "detected_format": "OpenAPI 3.x",
  "file_size_bytes": 5781,
  "upload_path": "uploaded_specs/petstore.yaml"
}
```

**Error 400** — unsupported file type or empty file  
**Error 422** — validation error (missing form field)

---

### `GET /api/specifications`

List all uploaded specification files.

```bash
curl http://localhost:8000/api/specifications
```

**Response 200**
```json
{
  "total": 3,
  "specifications": [
    {
      "filename": "petstore.yaml",
      "detected_format": "OpenAPI 3.x",
      "file_size_bytes": 5781,
      "upload_timestamp": "2026-07-08T10:00:00Z",
      "supported": true
    }
  ]
}
```

---

### `GET /api/specifications/{filename}`

Parse a spec file and return its metadata.

```bash
curl http://localhost:8000/api/specifications/petstore.yaml
```

**Response 200**
```json
{
  "filename": "petstore.yaml",
  "title": "Petstore API",
  "version": "1.0.0",
  "format": "OpenAPI 3.x",
  "base_url": "https://petstore.example.com",
  "endpoint_count": 7,
  "endpoints": [
    {
      "path": "/pets",
      "method": "GET",
      "operation_id": "listPets",
      "summary": "List all pets"
    }
  ]
}
```

**Error 404** — file not found  
**Error 400** — parse failure

---

## Async Jobs

The recommended way to execute the pipeline. Returns immediately with a `job_id` for polling.

### `POST /api/jobs`

Submit a new async pipeline job.

**Request body**
```json
{
  "specification_filename": "petstore.yaml",
  "environment": "development",
  "base_url_override": "https://api.example.com",
  "timeout_seconds": 30,
  "verify_ssl": true,
  "generate_reports": true
}
```

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `specification_filename` | string | ✓ | — | Filename in `uploaded_specs/` |
| `environment` | string | ✓ | — | Key from `environments.yaml` |
| `base_url_override` | string | — | null | Override environment base URL |
| `timeout_seconds` | int | — | 30 | Per-request HTTP timeout (1–300) |
| `verify_ssl` | bool | — | true | Verify TLS certificates |
| `generate_reports` | bool | — | true | Run Phase 8 report generation |

**Response 202 Accepted**
```json
{
  "job_id": "a76a4063-2574-48e0-b3c4-9f1234567890",
  "status": "pending",
  "poll_url": "http://localhost:8000/api/jobs/a76a4063-2574-48e0-b3c4-9f1234567890",
  "message": "Job queued. Poll poll_url until status is 'completed' or 'failed'."
}
```

**Error 404** — spec file not found

---

### `GET /api/jobs/{job_id}`

Poll job status and progress. Call every 2–5 seconds until `status` is `completed` or `failed`.

```bash
curl http://localhost:8000/api/jobs/a76a4063-2574-48e0-b3c4-9f1234567890
```

**Response 200**
```json
{
  "job_id": "a76a4063-2574-48e0-b3c4-9f1234567890",
  "status": "running",
  "step": "Executing HTTP requests",
  "percent": 35,
  "run_id": null,
  "report_paths": [],
  "error": null,
  "created_at": "2026-07-08T10:00:00Z",
  "started_at": "2026-07-08T10:00:01Z",
  "completed_at": null,
  "elapsed_s": null,
  "spec_filename": "petstore.yaml",
  "environment": "development"
}
```

**Status values:**
- `pending` — queued, not yet started
- `running` — pipeline executing
- `completed` — done; `run_id` is populated
- `failed` — error; `error` field is populated

**Step labels (in order):**  
`Queued` → `Loading configuration` → `Parsing API specification` → `Generating test cases` → `Executing HTTP requests` → `Validating responses` → `Persisting results` → `Running analytics` → `Generating reports` → `Done`

**Error 404** — job not found

---

### `GET /api/jobs`

List all in-memory jobs. Jobs are pruned after 24 hours.

**Query parameters**

| Parameter | Type | Description |
|---|---|---|
| `status` | string | Filter: `pending` / `running` / `completed` / `failed` |
| `limit` | int | Max results (default 100, max 500) |

**Response 200**
```json
{
  "total": 2,
  "jobs": [ { /* JobStatusResponse */ } ]
}
```

---

### `DELETE /api/jobs/{job_id}`

Cancel a `pending` job or dismiss a `completed`/`failed` job.

**Response 200**
```json
{
  "job_id": "a76a4063...",
  "status": "cancelled",
  "message": "Job cancelled."
}
```

**Error 409 Conflict** — job is currently `running` and cannot be cancelled

---

## Runs (Synchronous)

### `POST /api/run`

Execute the full pipeline synchronously. Blocks until complete (~30–120 s).  
For non-blocking execution, use `POST /api/jobs` instead.

**Request body** — same schema as `POST /api/jobs`

**Response 200**
```json
{
  "run_id": "run_c22fd94b-dd2c-4c5c-891a-7b7e8e68dc23",
  "status": "completed",
  "api_name": "HTTPBin Verification API",
  "summary": { /* RunSummary */ },
  "report_paths": ["Execution_Report.html", "Execution_Report.pdf"],
  "error": null
}
```

---

### `GET /api/runs`

Paginated run history.

**Query parameters**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `page` | int | 1 | Page number (1-based) |
| `page_size` | int | 20 | Results per page (max 100) |
| `api_name` | string | — | Filter by API name (partial match) |
| `environment` | string | — | Filter by environment |

**Response 200**
```json
{
  "total": 5,
  "page": 1,
  "page_size": 20,
  "has_next": false,
  "runs": [
    {
      "run_id": "run_c22fd94b-dd2c-4c5c-891a-7b7e8e68dc23",
      "api_name": "HTTPBin Verification API",
      "api_version": "1.0.0",
      "environment": "Development",
      "execution_timestamp": "2026-07-08T10:00:00Z",
      "total_endpoints": 8,
      "total_test_cases": 155,
      "total_executed": 155,
      "passed": 8,
      "failed": 97,
      "skipped": 0,
      "errors": 50,
      "pass_percentage": 5.16,
      "avg_response_time_ms": 782.5,
      "total_execution_time_s": 45.2,
      "health_score": 75.8,
      "health_rating": "Needs Attention",
      "specification_file": "httpbin_verification.yaml",
      "framework_version": "1.0.0"
    }
  ]
}
```

---

### `GET /api/runs/{run_id}`

Full run detail including validation summary.

```bash
curl http://localhost:8000/api/runs/run_c22fd94b-dd2c-4c5c-891a-7b7e8e68dc23
```

**Response 200**
```json
{
  "run": { /* RunSummary */ },
  "validation_summary": {
    "validators": [
      {
        "validator_name": "StatusCodeValidator",
        "passed": 120,
        "failed": 35,
        "total": 155,
        "pass_rate": 77.4
      }
    ],
    "total_assertions": 620,
    "total_passed": 480,
    "total_failed": 140
  },
  "report_links": [
    "Execution_Report.html",
    "Execution_Report.pdf"
  ]
}
```

**Error 404** — run not found

---

## Results

### `GET /api/runs/{run_id}/results/summary`

Aggregated test-case breakdown — use this instead of fetching all rows when you only need counts.

**Response 200**
```json
{
  "run_id": "run_c22fd94b-...",
  "total_results": 155,
  "passed": 8,
  "failed": 97,
  "skipped": 0,
  "errors": 50,
  "pass_rate": 5.2,
  "by_endpoint": [
    {
      "endpoint": "/get",
      "http_method": "GET",
      "total": 20,
      "passed": 3,
      "failed": 14,
      "skipped": 0,
      "errors": 3,
      "pass_rate": 15.0,
      "avg_response_time_ms": 430.5
    }
  ],
  "by_category": [
    { "category": "positive", "total": 40, "passed": 8, "failed": 32, "pass_rate": 20.0 }
  ],
  "by_status": { "passed": 8, "failed": 97, "error": 50 },
  "by_http_method": { "GET": 97, "POST": 21, "PUT": 17 }
}
```

---

### `GET /api/runs/{run_id}/results`

Paginated, filterable individual test-case results.

**Query parameters**

| Parameter | Type | Description |
|---|---|---|
| `status` | string | `passed` / `failed` / `skipped` / `error` |
| `endpoint` | string | Partial path match |
| `operation_id` | string | Exact operation ID |
| `http_method` | string | `GET` / `POST` / `PUT` / `DELETE` / … |
| `category` | string | `positive` / `negative` / `boundary` / `security` |
| `page` | int | Page number (default 1) |
| `page_size` | int | Results per page (default 50, max 500) |
| `sort_by` | string | `executed_at` / `response_time_ms` / `validation_status` / `endpoint` |
| `sort_order` | string | `asc` / `desc` |

**Response 200**
```json
{
  "run_id": "run_c22fd94b-...",
  "total": 97,
  "page": 1,
  "page_size": 50,
  "has_next": true,
  "results": [
    {
      "result_id": "res_46771115-...",
      "run_id": "run_c22fd94b-...",
      "test_id": "tc_12345-...",
      "operation_id": "listPets",
      "endpoint": "/get",
      "http_method": "GET",
      "category": "positive",
      "request_url": "https://httpbin.org/get",
      "request_headers": { "Accept": "application/json" },
      "request_payload": null,
      "response_status_code": 200,
      "response_headers": { "Content-Type": "application/json" },
      "response_body": { "url": "https://httpbin.org/get" },
      "response_time_ms": 430.5,
      "validation_status": "failed",
      "failure_reason": "Schema validation: required field 'id' missing",
      "validation_time_ms": 2.1,
      "executed_at": "2026-07-08T10:01:00Z"
    }
  ]
}
```

---

### `GET /api/runs/{run_id}/results/{result_id}`

Full detail for one test-case result, including per-validator assertion breakdown.

**Response 200** — same as individual result above, plus:
```json
{
  "...": "all result fields",
  "validation_details": [
    {
      "validation_detail_id": "vd_abc123-...",
      "validator_name": "StatusCodeValidator",
      "status": "passed",
      "message": "Expected 200, got 200",
      "severity": "critical",
      "execution_time_ms": 0.1,
      "recorded_at": "2026-07-08T10:01:00Z"
    },
    {
      "validation_detail_id": "vd_def456-...",
      "validator_name": "JsonSchemaValidator",
      "status": "failed",
      "message": "Required field 'id' is missing",
      "severity": "high",
      "execution_time_ms": 1.9,
      "recorded_at": "2026-07-08T10:01:00Z"
    }
  ]
}
```

---

## Analytics

### `GET /api/analytics`

Analytics for the most recent run.

```bash
curl http://localhost:8000/api/analytics
```

---

### `GET /api/analytics/{run_id}`

Full `AnalyticsSummary` for a specific run.

```bash
curl http://localhost:8000/api/analytics/run_c22fd94b-dd2c-4c5c-891a-7b7e8e68dc23
```

**Response 200**
```json
{
  "run_id": "run_c22fd94b-...",
  "api_name": "HTTPBin Verification API",
  "total_runs": 3,
  "generated_at": "2026-07-08T10:05:00Z",
  "health": {
    "score": 75.8,
    "rating": "Needs Attention",
    "pass_rate_score": 5.2,
    "response_time_score": 90.0,
    "stability_score": 80.0,
    "availability_score": 100.0,
    "recommendations": [
      "Investigate 97 failed test cases in the negative category",
      "Review schema validation failures on /get endpoint"
    ]
  },
  "response_time": {
    "sample_count": 155,
    "mean_ms": 782.5,
    "median_ms": 430.0,
    "min_ms": 210.0,
    "max_ms": 28813.0,
    "std_dev_ms": 2100.0,
    "p95_ms": 3400.0,
    "p99_ms": 15000.0,
    "sla_threshold_ms": 5000,
    "sla_compliance_pct": 92.3
  },
  "endpoint_analysis": {
    "most_executed": "GET /get",
    "most_failed": "POST /post",
    "fastest": "GET /status/200",
    "slowest": "GET /delay/{seconds}",
    "all_stats": [ { "endpoint": "/get", "method": "GET", "..." : "..." } ]
  },
  "failure_analysis": {
    "total_failures": 147,
    "distribution": [
      { "category": "schema_validation", "count": 97, "percentage": 66.0, "sample_message": "Required field 'id' missing" }
    ]
  },
  "trend": {
    "name": "Pass Rate",
    "points": [ { "label": "Run 1", "value": 3.2 }, { "label": "Run 2", "value": 5.16 } ],
    "direction": "improving",
    "slope": 0.98,
    "moving_avg": [3.2, 4.2, 5.16]
  },
  "regression": {
    "run_id_baseline": "run_abc123-...",
    "run_id_current": "run_c22fd94b-...",
    "new_failures": ["POST /post — schema validation"],
    "fixed_failures": [],
    "pass_rate_delta": 1.96,
    "has_regression": false,
    "verdict": "No regression detected. Pass rate improved by 1.96%."
  }
}
```

**Error 404** — run not found

---

## Reports

### `GET /api/reports/{run_id}`

List all generated reports for a run.

**Response 200**
```json
{
  "run_id": "run_c22fd94b-...",
  "report_count": 7,
  "reports": [
    {
      "filename": "Execution_Report.html",
      "format": "html",
      "size_bytes": 4916428,
      "created_at": "2026-07-08T10:05:00Z",
      "download_url": "/api/reports/run_c22fd94b-.../download/Execution_Report.html"
    },
    {
      "filename": "Execution_Report.pdf",
      "format": "pdf",
      "size_bytes": 5432,
      "download_url": "/api/reports/run_c22fd94b-.../download/Execution_Report.pdf"
    }
  ]
}
```

---

### `GET /api/reports/{run_id}/download/{filename}`

Download a report file.

```bash
curl -O http://localhost:8000/api/reports/run_c22fd94b-.../download/Execution_Report.html
```

**Response 200** — file content with appropriate `Content-Type`  
**Error 404** — report file not found

---

## Status Codes

| Code | Meaning |
|---|---|
| 200 | OK — request succeeded |
| 201 | Created — resource created (file uploaded) |
| 202 | Accepted — async job queued |
| 400 | Bad Request — invalid input (unsupported file type, parse failure) |
| 404 | Not Found — resource does not exist |
| 409 | Conflict — action not permitted in current state (e.g. cancel running job) |
| 422 | Unprocessable Entity — Pydantic validation failure |
| 500 | Internal Server Error — unexpected backend error |
